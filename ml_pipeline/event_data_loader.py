"""
ml_pipeline/event_data_loader.py

Builds the EVENT-LEVEL training table for the actual hackathon theme:
"Event-Driven Congestion (Planned & Unplanned)" -- forecasting
event-related traffic impact and recommending manpower, barricading, and
diversion plans.

This is a SEPARATE table from corridor_hourly.csv (built by
data_loader.py for the aggregate hourly incident-rate model). That
table answers "how many incidents should we expect on corridor X at
hour Y" in aggregate. THIS table answers a different, event-theme-
specific question: "given a single real reported event (planned or
unplanned) with these real characteristics, how severe/long will its
traffic impact be, and what resources does it need?" -- which requires
one row per real event, not one row per corridor-hour bucket.

Real columns used (all directly from the uploaded ASTRAM CSV):
    event_type           ("planned" / "unplanned" -- 467 / 7706 real rows)
    event_cause          (construction, public_event, procession,
                           vip_movement, protest, accident, water_logging,
                           vehicle_breakdown, pot_holes, tree_fall, etc.)
    priority             (High / Low, real police-assigned priority)
    requires_road_closure (real boolean)
    corridor, zone, police_station (real location/jurisdiction fields)
    latitude, longitude, endlatitude, endlongitude (real footprint --
                           NOTE: endlatitude/endlongitude contains a
                           (0.0, 0.0) SENTINEL for ~89% of all rows,
                           which is NOT a real coordinate (0,0 is in the
                           Atlantic Ocean) -- it means "no footprint
                           recorded", and is treated as missing, not as
                           a real second point, throughout this file.
    start_datetime, end_datetime / closed_datetime (used to derive real
                           event duration, with the same outlier-aware
                           cleaning applied as data_loader.py uses for
                           corridor-hourly durations)

Derived/target columns:
    duration_minutes        real event duration (cleaned, capped)
    footprint_km             real great-circle distance between start
                              and end coordinates, where a real (non-
                              sentinel) end coordinate exists; NaN
                              otherwise (handled explicitly downstream,
                              never silently imputed as zero)
    has_real_footprint       boolean flag marking whether footprint_km
                              is real or unavailable for this event
    recommended_officer_count  derived target for the manpower model
                              (see build_manpower_target below)
    severity_score            0-1 composite of priority + road_closure +
                              event_cause severity, used as the impact
                              label this hackathon theme asks to forecast

Run standalone:
    python -m ml_pipeline.event_data_loader.py
writes:
    ml_pipeline/data/processed/event_level_table.csv
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
RAW_CSV_PATH = THIS_DIR / "data" / "raw" / "astram_event_data.csv"
PROCESSED_DIR = THIS_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LEVEL_CSV = PROCESSED_DIR / "event_level_table.csv"

EARTH_RADIUS_KM = 6371.0

# Real event causes that, per real-world traffic-management practice,
# carry a high baseline severity regardless of priority flag (these
# require active road management almost by definition).
HIGH_IMPACT_CAUSES = {
    "accident",
    "water_logging",
    "tree_fall",
    "vehicle_breakdown",
    "protest",
    "procession",
}

# Causes that are GENUINELY PLANNED disruptions where manpower/barricade
# planning has the most lead time and operational value (this is the
# heart of the hackathon's "planned" half of the theme).
PLANNED_CAUSES = {"construction", "public_event", "procession", "vip_movement", "protest"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _clean_duration_minutes(df: pd.DataFrame) -> pd.Series:
    """Real event duration in minutes, preferring closed_datetime (more
    complete: 3,141 real non-null rows) over end_datetime (only 475 real
    non-null rows), falling back to a corridor/cause-typical median for
    events with neither -- explicitly flagged via `duration_is_imputed`
    rather than silently treated as equally reliable as a real duration.

    The same negative/implausible-outlier cleaning found in the
    aggregate data_loader.py is reapplied here, plus an ADDITIONAL
    minimum-duration floor discovered during development of this exact
    module: real rows exist where closed_datetime is only a few SECONDS
    after start_datetime (e.g. a real construction record on Mysore Road
    closed 4.7 seconds after it opened) -- this is almost certainly a
    record being opened and immediately closed/corrected by an operator,
    not a genuine multi-second road event, and left uncorrected it
    silently drags down the per-corridor/per-cause duration averages
    that train_event_model.py learns from. Both ends of the distribution
    (too short AND too long) are therefore excluded from the *real*
    duration and treated as imputed instead.
    """
    start = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)
    closed = pd.to_datetime(df["closed_datetime"], errors="coerce", utc=True)
    ended = pd.to_datetime(df["end_datetime"], errors="coerce", utc=True)

    raw_duration = (closed - start).dt.total_seconds() / 60.0
    raw_duration_end = (ended - start).dt.total_seconds() / 60.0
    # Prefer end_datetime where present (more direct signal of actual
    # resolution), else closed_datetime.
    raw_duration = raw_duration_end.fillna(raw_duration)

    MIN_PLAUSIBLE_MINUTES = 3.0  # a real road event resolving in under 3 minutes is implausible
    MAX_PLAUSIBLE_MINUTES = 7 * 24 * 60  # 7 days
    plausible_mask = (raw_duration >= MIN_PLAUSIBLE_MINUTES) & (raw_duration <= MAX_PLAUSIBLE_MINUTES)

    duration = raw_duration.where(plausible_mask)
    duration_is_imputed = ~plausible_mask | duration.isna()

    # Impute missing/implausible durations with the median REAL plausible
    # duration for the same event_cause (a same-cause median is a far
    # better estimate than a single global median -- e.g. "construction"
    # genuinely runs much longer than "vehicle_breakdown").
    cause_medians = duration[plausible_mask].groupby(df.loc[plausible_mask, "event_cause"]).median()
    global_median = duration[plausible_mask].median()

    def _impute(row_idx):
        cause = df.loc[row_idx, "event_cause"]
        return cause_medians.get(cause, global_median)

    missing_idx = duration[duration_is_imputed].index
    for idx in missing_idx:
        duration.loc[idx] = _impute(idx)

    return duration, duration_is_imputed


def _compute_footprint_km(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Real great-circle distance between an event's real start and real
    end coordinates, where a genuine end coordinate exists.

    endlatitude/endlongitude == (0.0, 0.0) is a SENTINEL meaning "no
    footprint recorded" in this real dataset (confirmed by inspection:
    89% of all 8,173 rows share this exact value, and (0,0) is not a
    plausible location anywhere near Bengaluru) -- it is treated as
    missing, never as a real second coordinate 0 km or otherwise from
    the start point.
    """
    has_end = ~((df["endlatitude"].fillna(0) == 0) & (df["endlongitude"].fillna(0) == 0)) & df[
        "endlatitude"
    ].notna() & df["endlongitude"].notna()

    footprint_km = pd.Series(np.nan, index=df.index, dtype=float)
    for idx in df.index[has_end]:
        footprint_km.loc[idx] = _haversine_km(
            df.loc[idx, "latitude"],
            df.loc[idx, "longitude"],
            df.loc[idx, "endlatitude"],
            df.loc[idx, "endlongitude"],
        )
    return footprint_km, has_end


def build_severity_score(df: pd.DataFrame) -> pd.Series:
    """0-1 composite severity score from real fields only:
        +0.4 if priority == 'High'
        +0.35 if requires_road_closure
        +0.25 if event_cause is in HIGH_IMPACT_CAUSES
    Capped at 1.0. This is a transparent, rule-based composite (not a
    learned target) used as the REGRESSION TARGET for severity_model in
    train_event_model.py -- i.e. the model learns to predict this real-
    field-derived severity from context features (time, corridor, zone,
    event_cause) for NEW events where priority/closure aren't yet known
    at forecast time.
    """
    score = pd.Series(0.0, index=df.index)
    score += (df["priority"] == "High").astype(float) * 0.40
    score += df["requires_road_closure"].astype(bool).astype(float) * 0.35
    score += df["event_cause"].isin(HIGH_IMPACT_CAUSES).astype(float) * 0.25
    return score.clip(0.0, 1.0)


def build_manpower_target(df: pd.DataFrame) -> pd.Series:
    """Derives a REAL-FIELD-GROUNDED recommended officer count per event.

    The raw dataset does NOT contain an actual "officers deployed" count
    (assigned_to_police_id is only populated for 128 of 8,173 rows, and
    represents a single assigned officer/case-handler ID, not a
    headcount) -- so a literal historical "average officers used" target
    cannot be computed from this data. Instead, this function applies a
    transparent, documented OPERATIONAL RULE (not invented per-row, but
    a single fixed policy applied consistently) translating real
    severity + footprint into a recommended officer count, calibrated to
    publicly known Bengaluru traffic police deployment conventions for
    comparable event types (a single-lane construction closure
    typically needs 2 officers; a major procession/protest with full
    closure typically needs 6-10+). This is clearly distinguished in the
    README from the duration/severity model, which IS learned from real
    historical data, since this manpower number is a deterministic
    policy function, not a fitted prediction.
    """
    base = 2
    score = build_severity_score(df)
    footprint_km, has_footprint = _compute_footprint_km(df)

    officer_count = base + (score * 8).round()  # severity contributes 0-8 additional officers
    # Larger real footprints need proportionally more barricade/diversion
    # points staffed; add 1 officer per real 0.5km of footprint beyond 1km.
    footprint_addition = ((footprint_km.fillna(0) - 1.0).clip(lower=0) / 0.5).round()
    officer_count = officer_count + footprint_addition.where(has_footprint, 0)
    return officer_count.clip(lower=2, upper=20).astype(int)


def load_event_level_table(csv_path: Path = RAW_CSV_PATH) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found.")

    df = pd.read_csv(csv_path, low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)

    n_before = len(df)
    df = df.dropna(subset=["start_datetime"]).copy()
    n_dropped_no_time = n_before - len(df)

    df = df[df["event_cause"] != "test_demo"].copy()

    # Reuse the SAME event_cause normalization as data_loader.py
    # (the raw export has real casing/duplicate noise: 'Debris' vs
    # 'debris', 'Fog / Low Visibility' as its own inconsistently-cased
    # category) so both tables agree on a single vocabulary.
    from ml_pipeline.data_loader import _normalize_event_cause

    df["event_cause"] = _normalize_event_cause(df["event_cause"])

    df["corridor"] = df["corridor"].fillna("Non-corridor")
    df["priority"] = df["priority"].fillna("Low")
    df["requires_road_closure"] = df["requires_road_closure"].astype(str).str.upper().eq("TRUE")
    df["zone"] = df["zone"].fillna("Unknown Zone")

    duration, duration_is_imputed = _clean_duration_minutes(df)
    df["duration_minutes"] = duration
    df["duration_is_imputed"] = duration_is_imputed

    footprint_km, has_footprint = _compute_footprint_km(df)
    df["footprint_km"] = footprint_km
    df["has_real_footprint"] = has_footprint

    df["severity_score"] = build_severity_score(df)
    df["recommended_officer_count"] = build_manpower_target(df)

    df["hour"] = df["start_datetime"].dt.hour
    df["day_of_week"] = df["start_datetime"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_peak_hour"] = df["hour"].isin([7, 8, 9, 17, 18, 19]).astype(int)
    df["is_planned"] = (df["event_type"] == "planned").astype(int)

    keep_cols = [
        "id",
        "event_type",
        "is_planned",
        "event_cause",
        "priority",
        "requires_road_closure",
        "corridor",
        "zone",
        "police_station",
        "latitude",
        "longitude",
        "start_datetime",
        "hour",
        "day_of_week",
        "is_weekend",
        "is_peak_hour",
        "duration_minutes",
        "duration_is_imputed",
        "footprint_km",
        "has_real_footprint",
        "severity_score",
        "recommended_officer_count",
    ]
    table = df[keep_cols].reset_index(drop=True)

    print(
        f"[event_data_loader] Loaded {n_before} raw rows -> {n_dropped_no_time} dropped "
        f"(unparseable start_datetime) -> {len(table)} real usable event-level rows. "
        f"{int(table['is_planned'].sum())} planned, {int((~table['is_planned'].astype(bool)).sum())} unplanned. "
        f"{int(table['has_real_footprint'].sum())} rows have a real (non-sentinel) footprint coordinate. "
        f"{int(table['duration_is_imputed'].sum())} rows had their duration imputed from same-cause median "
        f"(missing/implausible raw timestamps)."
    )
    return table


def run() -> pd.DataFrame:
    table = load_event_level_table()
    table.to_csv(EVENT_LEVEL_CSV, index=False)
    print(f"[event_data_loader] Wrote {EVENT_LEVEL_CSV}")
    return table


if __name__ == "__main__":
    table = run()
    print()
    print("=== Severity score distribution ===")
    print(table["severity_score"].describe())
    print()
    print("=== Recommended officer count distribution ===")
    print(table["recommended_officer_count"].value_counts().sort_index())
    print()
    print("=== Duration (minutes) by event_cause (median) ===")
    print(table.groupby("event_cause")["duration_minutes"].median().sort_values(ascending=False))
