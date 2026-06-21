"""
ml_pipeline/reroute_advisor.py

Generates human-readable rerouting/mitigation recommendations based on
the REAL incident-risk forecasts produced by predict.py.

Logic: if a corridor's +60min predicted_incidents crosses HIGH_THRESHOLD
(see predict.py), find the nearest-by-geography corridors (using real
corridor centroid lat/lon, Haversine distance) that currently have a
LOWER predicted incident risk, and recommend them as alternates.

This module does NOT invent traffic-volume percentages ("94% capacity")
since the real dataset has no capacity/volume figures -- only real
incident counts. Recommendations are phrased honestly in terms of
predicted incident risk, which is what the data actually supports.

Run standalone:
    python -m ml_pipeline.reroute_advisor.py --corridor "Mysore Road"
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = THIS_DIR / "data" / "processed"
CORRIDOR_CENTROIDS_JSON = PROCESSED_DIR / "corridor_centroids.json"

from ml_pipeline.predict import HIGH_THRESHOLD, predict_all_corridors, predict_corridor

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _load_centroids() -> pd.DataFrame:
    if not CORRIDOR_CENTROIDS_JSON.exists():
        raise FileNotFoundError(
            f"{CORRIDOR_CENTROIDS_JSON} not found. Run data_loader.py first."
        )
    return pd.read_json(CORRIDOR_CENTROIDS_JSON)


def find_nearest_lower_risk_corridors(
    target_corridor: str, all_predictions: list[dict], n: int = 2
) -> list[dict]:
    """Real geographic nearest-neighbor search among corridors with a
    real-data-derived predicted incident risk LOWER than the target.
    """
    centroids = _load_centroids()
    target_row = centroids[centroids["corridor_id"] == target_corridor]
    if target_row.empty:
        return []
    target_lat = float(target_row.iloc[0]["lat"])
    target_lon = float(target_row.iloc[0]["lon"])

    target_pred = next((p for p in all_predictions if p["corridor_id"] == target_corridor), None)
    if target_pred is None:
        return []
    target_risk = target_pred["forecast_windows"][1]["predicted_incidents"]

    candidates = []
    for pred in all_predictions:
        cid = pred["corridor_id"]
        if cid == target_corridor:
            continue
        risk = pred["forecast_windows"][1]["predicted_incidents"]
        if risk >= target_risk:
            continue
        row = centroids[centroids["corridor_id"] == cid]
        if row.empty:
            continue
        dist_km = _haversine_km(target_lat, target_lon, float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"]))
        candidates.append(
            {
                "corridor_id": cid,
                "predicted_incidents": risk,
                "distance_km": round(dist_km, 2),
                "congestion_level": pred["congestion_level"],
            }
        )

    candidates.sort(key=lambda c: c["distance_km"])
    return candidates[:n]


def generate_advice(corridor_id: str, as_of=None) -> dict:
    target_pred = predict_corridor(corridor_id, as_of=as_of)
    all_predictions = predict_all_corridors(as_of=as_of)

    congestion_level = target_pred["congestion_level"]
    pred_60 = target_pred["forecast_windows"][1]["predicted_incidents"]

    recommendations = []
    advice_text = (
        f"{corridor_id} shows {congestion_level.lower()} predicted incident risk "
        f"({pred_60:.2f} expected incidents in the next hour, based on real historical "
        f"ASTRAM incident patterns). No rerouting action needed."
    )

    if congestion_level in ("HIGH", "MEDIUM"):
        alternates = find_nearest_lower_risk_corridors(corridor_id, all_predictions, n=2)
        recommendations = alternates
        if alternates:
            alt_descriptions = ", ".join(
                f"{alt['corridor_id']} ({alt['distance_km']}km away, "
                f"predicted {alt['predicted_incidents']:.2f} incidents/hr, {alt['congestion_level']})"
                for alt in alternates
            )
            advice_text = (
                f"Elevated risk on {corridor_id} -- predicted {pred_60:.2f} incidents in the "
                f"next hour ({congestion_level}), based on real historical ASTRAM incident "
                f"patterns for this corridor and time. Consider routing traffic via: "
                f"{alt_descriptions}."
            )
        else:
            advice_text = (
                f"Elevated risk on {corridor_id} -- predicted {pred_60:.2f} incidents in the "
                f"next hour ({congestion_level}). No nearby lower-risk corridor identified at "
                f"this time; monitor closely."
            )

    return {
        "corridor_id": corridor_id,
        "congestion_level": congestion_level,
        "predicted_incidents_next_hour": pred_60,
        "mitigation_required": congestion_level in ("HIGH", "MEDIUM"),
        "advice": advice_text,
        "alternate_corridors": recommendations,
        "data_provenance": target_pred["data_provenance"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate rerouting advice for a corridor.")
    parser.add_argument("--corridor", type=str, default="Mysore Road")
    args = parser.parse_args()
    advice = generate_advice(args.corridor)
    print(json.dumps(advice, indent=2))
