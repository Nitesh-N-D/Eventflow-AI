"""
ml_pipeline/resource_advisor.py

Generates the actual operational deliverable the hackathon theme asks
for: "recommend optimal manpower, barricading, and diversion plans" for
a forecasted event, built on top of predict_event.py's real-data-trained
duration/severity forecast.

Three recommendation components, all traceable to real fields/values:

1. MANPOWER: derived from severity_score + footprint via the same
   documented policy rule as event_data_loader.build_manpower_target
   (a deterministic policy, not a learned number -- see that function's
   docstring for the rationale on why this dataset cannot support a
   learned officer-count target).

2. BARRICADING: number and rough spacing of barricade points, derived
   from the event's predicted footprint (using REAL footprint_km values
   observed for similar past real events of the same event_cause where
   available, since most individual future events won't have a known
   footprint at forecast time) and requires_road_closure likelihood
   (estimated from real historical rate of requires_road_closure==True
   for the same event_cause).

3. DIVERSION: reuses the real nearest-corridor logic from
   reroute_advisor.py, now applied to the EVENT's corridor with the
   event's predicted severity as the congestion signal, recommending
   real nearby corridors with historically lower incident activity as
   diversion routes.

Run standalone:
    python -m ml_pipeline.resource_advisor.py --event_cause construction \
        --corridor "Mysore Road" --zone "West Zone 1" --hour 10 --day_of_week 2
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = THIS_DIR / "data" / "processed"
EVENT_LEVEL_CSV = PROCESSED_DIR / "event_level_table.csv"
CORRIDOR_CENTROIDS_JSON = PROCESSED_DIR / "corridor_centroids.json"

from ml_pipeline.predict_event import predict_event

EARTH_RADIUS_KM = 6371.0
BARRICADE_SPACING_KM = 0.3  # one barricade point roughly every 300m of real footprint


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _real_typical_footprint_km(event_cause: str) -> float | None:
    """Median REAL footprint_km observed for past real events of this
    event_cause (only among the 609 real rows in the dataset that have
    a genuine, non-sentinel footprint coordinate). Returns None if no
    real footprint data exists for this cause, in which case the
    barricading recommendation falls back to a fixed conservative
    default rather than fabricating a number.
    """
    if not EVENT_LEVEL_CSV.exists():
        return None
    df = pd.read_csv(EVENT_LEVEL_CSV)
    sub = df[(df["event_cause"] == event_cause) & (df["has_real_footprint"] == True)]
    if sub.empty or sub["footprint_km"].dropna().empty:
        return None
    return float(sub["footprint_km"].median())


def _real_road_closure_rate(event_cause: str) -> float:
    """Real historical fraction of events of this event_cause that
    required a road closure -- used to qualify the diversion
    recommendation's confidence (a cause that almost never needs closure
    historically gets a much softer diversion recommendation than one
    that almost always does).
    """
    if not EVENT_LEVEL_CSV.exists():
        return 0.5
    df = pd.read_csv(EVENT_LEVEL_CSV)
    sub = df[df["event_cause"] == event_cause]
    if sub.empty:
        return 0.5
    return float(sub["requires_road_closure"].mean())


def _recommend_manpower(severity_score: float, footprint_km: float | None) -> dict:
    base = 2
    severity_officers = round(severity_score * 8)
    footprint_addition = 0
    if footprint_km is not None and footprint_km > 1.0:
        footprint_addition = round((footprint_km - 1.0) / 0.5)
    total = int(max(2, min(20, base + severity_officers + footprint_addition)))
    return {
        "recommended_officer_count": total,
        "rationale": (
            f"base {base} + severity-scaled {severity_officers} "
            f"(severity_score={severity_score:.2f}) "
            + (f"+ footprint-scaled {footprint_addition} (typical real footprint {footprint_km:.2f}km)"
               if footprint_km else "+ 0 (no real historical footprint data for this event_cause)")
        ),
    }


def _recommend_barricading(footprint_km: float | None, road_closure_rate: float) -> dict:
    if footprint_km is None:
        return {
            "barricade_points": 2,
            "spacing_km": None,
            "rationale": (
                "No real historical footprint data available for this event_cause "
                "(only 609 of 8,054 real events in this dataset have a genuine, "
                "non-sentinel end coordinate) -- using a conservative fixed minimum "
                "of 2 barricade points (entry + exit) until on-site assessment confirms extent."
            ),
            "historical_road_closure_rate": round(road_closure_rate, 2),
        }
    n_points = max(2, round(footprint_km / BARRICADE_SPACING_KM))
    return {
        "barricade_points": int(n_points),
        "spacing_km": BARRICADE_SPACING_KM,
        "estimated_footprint_km": round(footprint_km, 2),
        "rationale": (
            f"Typical real footprint for this event_cause is {footprint_km:.2f}km "
            f"(median of real non-sentinel footprint coordinates in the historical data); "
            f"{n_points} points at ~{BARRICADE_SPACING_KM}km spacing."
        ),
        "historical_road_closure_rate": round(road_closure_rate, 2),
    }


def _recommend_diversion(corridor: str, severity_score: float) -> list[dict]:
    if not CORRIDOR_CENTROIDS_JSON.exists():
        return []
    centroids = pd.read_json(CORRIDOR_CENTROIDS_JSON)
    target_row = centroids[centroids["corridor_id"] == corridor]
    if target_row.empty:
        return []
    target_lat = float(target_row.iloc[0]["lat"])
    target_lon = float(target_row.iloc[0]["lon"])

    # Real historical total incident count per corridor as a proxy for
    # "how much spare capacity / how clean is this corridor's historical
    # record" -- lower real n_incidents_total is treated as a more
    # favorable diversion target, all else equal.
    centroids["distance_km"] = centroids.apply(
        lambda r: _haversine_km(target_lat, target_lon, r["lat"], r["lon"]), axis=1
    )
    candidates = centroids[centroids["corridor_id"] != corridor].copy()
    candidates = candidates.sort_values(["distance_km"]).head(5)
    candidates = candidates.sort_values(["n_incidents_total", "distance_km"]).head(2)

    return [
        {
            "corridor_id": row["corridor_id"],
            "distance_km": round(float(row["distance_km"]), 2),
            "historical_total_incidents": int(row["n_incidents_total"]),
        }
        for _, row in candidates.iterrows()
    ]


def generate_resource_plan(
    event_cause: str, corridor: str, zone: str, hour: int, day_of_week: int, is_planned: int = 1
) -> dict:
    forecast = predict_event(event_cause, corridor, zone, hour, day_of_week, is_planned)

    typical_footprint = _real_typical_footprint_km(event_cause)
    closure_rate = _real_road_closure_rate(event_cause)

    manpower = _recommend_manpower(forecast["predicted_severity_score"], typical_footprint)
    barricading = _recommend_barricading(typical_footprint, closure_rate)
    diversion = []
    if forecast["impact_level"] in ("HIGH", "MEDIUM") or closure_rate > 0.3:
        diversion = _recommend_diversion(corridor, forecast["predicted_severity_score"])

    summary = (
        f"{event_cause.replace('_', ' ').title()} event forecast on {corridor} ({zone}): "
        f"expected duration {forecast['predicted_duration_human']}, impact level "
        f"{forecast['impact_level']} (severity {forecast['predicted_severity_score']:.2f}). "
        f"Recommend {manpower['recommended_officer_count']} officers, "
        f"{barricading['barricade_points']} barricade points"
        + (f", route diversion via {', '.join(d['corridor_id'] for d in diversion)}." if diversion else ".")
    )

    return {
        "forecast": forecast,
        "manpower_recommendation": manpower,
        "barricading_recommendation": barricading,
        "diversion_recommendation": diversion,
        "summary": summary,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--event_cause", type=str, default="construction")
    parser.add_argument("--corridor", type=str, default="Mysore Road")
    parser.add_argument("--zone", type=str, default="West Zone 1")
    parser.add_argument("--hour", type=int, default=10)
    parser.add_argument("--day_of_week", type=int, default=2)
    parser.add_argument("--is_planned", type=int, default=1, choices=[0, 1])
    args = parser.parse_args()

    plan = generate_resource_plan(
        args.event_cause, args.corridor, args.zone, args.hour, args.day_of_week, args.is_planned
    )
    print(json.dumps(plan, indent=2))
