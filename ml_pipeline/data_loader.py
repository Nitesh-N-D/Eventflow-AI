"""
ml_pipeline/data_loader.py

Loads the REAL ASTRAM traffic event dataset (Bengaluru traffic incident log,
8,173 events, Nov 2023 - Apr 2024) and turns it into a clean, regular
corridor x hour-bucket incident table that the forecaster trains on.

This is genuinely real data, not synthetic. There is no historical
"vehicle demand" column in the source data because the source data is an
INCIDENT LOG (breakdowns, potholes, accidents, water-logging, construction,
etc.), not a volume-count sensor feed. Module 3 is therefore framed honestly
as an INCIDENT-RISK / DISRUPTION-LIKELIHOOD forecaster, not a raw vehicle
volume forecaster -- see README.md "Round 1 -> Round 2" section for the
full rationale.

Pipeline:
    raw CSV (event-level, irregular timestamps)
        -> clean / normalize categorical noise
        -> bucket into (corridor, date, hour) cells
        -> count incidents per cell -> target variable `incident_count`
        -> fill ALL corridor x hour x date combinations with zero-count
           rows so the table is a REGULAR grid (required for lag/rolling
           features -- you cannot lag a sparse, irregular table correctly)
        -> attach corridor centroid lat/lon (mean of all incidents
           ever logged in that corridor) for downstream geo use in
           Module 2's O-D matrix and heatmap

Run standalone:
    python -m ml_pipeline.data_loader.py
will print a summary and write the cleaned table to
    ml_pipeline/data/processed/corridor_hourly.parquet
    ml_pipeline/data/processed/corridor_hourly.csv
    ml_pipeline/data/processed/corridor_centroids.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (all relative to this file, so the repo runs from any clone location)
# ---------------------------------------------------------------------------
THIS_DIR = Path(__file__).resolve().parent
RAW_CSV_PATH = THIS_DIR / "data" / "raw" / "astram_event_data.csv"
PROCESSED_DIR = THIS_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CORRIDOR_HOURLY_PARQUET = PROCESSED_DIR / "corridor_hourly.parquet"
CORRIDOR_HOURLY_CSV = PROCESSED_DIR / "corridor_hourly.csv"
CORRIDOR_CENTROIDS_JSON = PROCESSED_DIR / "corridor_centroids.json"

# ---------------------------------------------------------------------------
# Cleaning lookup tables
# ---------------------------------------------------------------------------

# event_cause has inconsistent casing/duplicates in the raw export
# (observed directly in the uploaded file: 'Debris' vs 'debris',
# 'Fog / Low Visibility' as its own oddly-capitalized category).
# Normalize everything to a single lowercase snake_case vocabulary.
EVENT_CAUSE_NORMALIZATION = {
    "debris": "debris",
    "Debris": "debris",
    "Fog / Low Visibility": "fog_low_visibility",
    "vehicle_breakdown": "vehicle_breakdown",
    "pot_holes": "pot_holes",
    "construction": "construction",
    "water_logging": "water_logging",
    "accident": "accident",
    "tree_fall": "tree_fall",
    "road_conditions": "road_conditions",
    "congestion": "congestion",
    "public_event": "public_event",
    "procession": "procession",
    "vip_movement": "vip_movement",
    "protest": "protest",
    "test_demo": "test_demo",
    "others": "others",
}

# Causes that are direct, severe, road-blocking disruptions vs minor /
# informational ones. Used to build a severity-weighted risk score in
# addition to the raw incident count.
HIGH_SEVERITY_CAUSES = {
    "accident",
    "tree_fall",
    "water_logging",
    "vehicle_breakdown",
    "road_conditions",
    "debris",
}
LOW_SEVERITY_CAUSES = {
    "congestion",
    "public_event",
    "procession",
    "vip_movement",
    "protest",
    "others",
    "fog_low_visibility",
    "construction",
    "pot_holes",
    "test_demo",
}

# test_demo rows are explicitly test/demo records inserted by the platform
# operators, not real traffic incidents. Excluding them keeps the model
# honest -- training on fake test rows would quietly corrupt real signal.
EXCLUDE_CAUSES = {"test_demo"}


def _normalize_event_cause(series: pd.Series) -> pd.Series:
    return series.map(lambda x: EVENT_CAUSE_NORMALIZATION.get(x, "others") if pd.notna(x) else "others")


def load_raw_events(csv_path: Path = RAW_CSV_PATH) -> pd.DataFrame:
    """Load the raw ASTRAM CSV and apply minimal, well-justified cleaning.

    Every cleaning decision here is documented inline because this is real
    operational data with real data-entry noise -- silent cleaning would
    make the pipeline unauditable.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Raw ASTRAM event CSV not found at {csv_path}. "
            f"Place the dataset at ml_pipeline/data/raw/astram_event_data.csv "
            f"before running the forecaster pipeline."
        )

    df = pd.read_csv(csv_path, low_memory=False)

    # --- Parse timestamps -------------------------------------------------
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)

    # 116 rows in the source file have an unparseable/missing start_datetime.
    # An incident with no known time cannot be placed in an hour bucket, so
    # these rows are dropped (logged below for transparency, never silently).
    n_before = len(df)
    df = df.dropna(subset=["start_datetime"]).copy()
    n_dropped_no_time = n_before - len(df)

    # --- Normalize corridor -------------------------------------------------
    # 20 rows have a null corridor; bucket them into "Non-corridor" rather
    # than dropping them, since "no specific corridor" is itself meaningful
    # (it's the single largest category in the real data: 3,124 events).
    df["corridor"] = df["corridor"].fillna("Non-corridor")

    # --- Normalize event_cause ----------------------------------------------
    df["event_cause_clean"] = _normalize_event_cause(df["event_cause"])
    n_before_exclude = len(df)
    df = df[~df["event_cause_clean"].isin(EXCLUDE_CAUSES)].copy()
    n_dropped_test_demo = n_before_exclude - len(df)

    # --- Severity flag --------------------------------------------------
    df["is_high_severity"] = df["event_cause_clean"].isin(HIGH_SEVERITY_CAUSES)

    # --- Normalize priority / closure flags -------------------------------
    df["priority"] = df["priority"].fillna("Low")
    df["requires_road_closure"] = df["requires_road_closure"].astype(str).str.upper().eq("TRUE")

    # --- Time features on the raw event (used later for centroid / EDA) ---
    df["event_date"] = df["start_datetime"].dt.date
    df["event_hour"] = df["start_datetime"].dt.hour
    df["event_dow"] = df["start_datetime"].dt.dayofweek  # 0=Mon

    print(
        f"[data_loader] Loaded {n_before} raw rows -> "
        f"{n_dropped_no_time} dropped (unparseable start_datetime), "
        f"{n_dropped_test_demo} dropped (test_demo records), "
        f"{len(df)} usable real incident rows remain."
    )
    return df


def compute_corridor_centroids(df: pd.DataFrame) -> pd.DataFrame:
    """Mean lat/lon per corridor, computed from real incident locations.

    Used by Module 2 (od_matrix.py, density_heatmap.py) as the
    representative point for each corridor on the map, since the raw
    dataset has no single canonical corridor-centroid column.
    """
    centroids = (
        df.groupby("corridor")
        .agg(
            lat=("latitude", "mean"),
            lon=("longitude", "mean"),
            n_incidents_total=("id", "count"),
        )
        .reset_index()
        .rename(columns={"corridor": "corridor_id"})
    )
    return centroids


def build_corridor_hourly_table(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate event-level rows into a REGULAR (corridor x date x hour) grid.

    This is the single most important correctness step in the whole
    forecaster: lag/rolling features are meaningless on a sparse table
    where missing rows mean "no data" rather than "zero incidents". We
    therefore explicitly construct the full cartesian product of
    (corridor, date, hour) and left-join real counts onto it, filling
    true gaps with 0.
    """
    corridors = sorted(df["corridor"].unique())
    date_min = df["event_date"].min()
    date_max = df["event_date"].max()
    full_dates = pd.date_range(date_min, date_max, freq="D").date
    hours = list(range(24))

    # Real aggregated counts per (corridor, date, hour)
    grouped = (
        df.groupby(["corridor", "event_date", "event_hour"])
        .agg(
            incident_count=("id", "count"),
            high_severity_count=("is_high_severity", "sum"),
            high_priority_count=("priority", lambda s: (s == "High").sum()),
            road_closure_count=("requires_road_closure", "sum"),
        )
        .reset_index()
        .rename(columns={"corridor": "corridor_id", "event_date": "date", "event_hour": "hour"})
    )

    # Full regular grid
    grid = pd.MultiIndex.from_product(
        [corridors, full_dates, hours], names=["corridor_id", "date", "hour"]
    ).to_frame(index=False)

    table = grid.merge(grouped, on=["corridor_id", "date", "hour"], how="left")
    for col in ["incident_count", "high_severity_count", "high_priority_count", "road_closure_count"]:
        table[col] = table[col].fillna(0).astype(int)

    table["date"] = pd.to_datetime(table["date"])
    table["timestamp"] = table["date"] + pd.to_timedelta(table["hour"], unit="h")
    table["day_of_week"] = table["timestamp"].dt.dayofweek
    table["is_weekend"] = table["day_of_week"].isin([5, 6]).astype(int)
    table["is_peak_hour"] = table["hour"].isin([7, 8, 9, 17, 18, 19]).astype(int)

    table = table.sort_values(["corridor_id", "timestamp"]).reset_index(drop=True)

    # --- Known data-quality artifact: bulk-import spikes ------------------
    # Inspection of the real data found a handful of corridor-hour cells
    # with implausibly large incident_count (e.g. 56 "accident" rows
    # logged in the same hour on "Non-corridor" with no description and no
    # corridor assignment -- almost certainly a batch data-seeding or
    # anonymization artifact in the source export, not 56 simultaneous
    # real accidents). Only the genuinely extreme tail is capped (a fixed,
    # generously high threshold chosen by inspecting the real distribution
    # directly, not a blanket percentile rule) -- legitimate multi-incident
    # hours (e.g. 4-10 incidents during a real flooding event) are left
    # untouched.
    HARD_CAP = 15  # genuine real corridor-hours observed in this data top out around 8-12
    n_capped = int((table["incident_count"] > HARD_CAP).sum())
    if n_capped > 0:
        capped_examples = table.loc[table["incident_count"] > HARD_CAP, ["corridor_id", "timestamp", "incident_count"]]
        print(
            f"[data_loader] Winsorizing {n_capped} corridor-hour cells with incident_count > "
            f"{HARD_CAP} -- likely bulk-import/data-entry artifacts (e.g. a same-hour batch of "
            f"identical accident rows with no description/corridor), not real simultaneous "
            f"incidents. Examples:\n{capped_examples.to_string(index=False)}"
        )
        table["incident_count"] = table["incident_count"].clip(upper=HARD_CAP)

    print(
        f"[data_loader] Built regular grid: {len(corridors)} corridors x "
        f"{len(full_dates)} days x 24 hours = {len(table)} rows "
        f"({grouped.shape[0]} of those cells had >=1 real incident, "
        f"{(table['incident_count'] > 0).sum()} after grid fill)."
    )
    return table


def run(csv_path: Path = RAW_CSV_PATH) -> pd.DataFrame:
    """Full load -> clean -> aggregate pipeline. Returns the corridor-hourly table."""
    raw = load_raw_events(csv_path)
    centroids = compute_corridor_centroids(raw)
    table = build_corridor_hourly_table(raw)

    # Attach centroid lat/lon onto every row (needed for geohash encoding
    # in feature_engineer.py and for Module 2's geo outputs)
    table = table.merge(centroids[["corridor_id", "lat", "lon"]], on="corridor_id", how="left")

    table.to_csv(CORRIDOR_HOURLY_CSV, index=False)
    print(f"[data_loader] Wrote {CORRIDOR_HOURLY_CSV}")

    # Parquet is preferred in production (faster, typed, smaller) but
    # requires pyarrow/fastparquet. Fall back gracefully if unavailable
    # rather than crashing the whole pipeline -- CSV is the source of
    # truth either way since it's written unconditionally above.
    try:
        table.to_parquet(CORRIDOR_HOURLY_PARQUET, index=False)
        print(f"[data_loader] Wrote {CORRIDOR_HOURLY_PARQUET}")
    except ImportError:
        print(
            f"[data_loader] Skipped parquet output (pyarrow/fastparquet not installed). "
            f"Install via 'pip install pyarrow' for faster downstream loads. "
            f"CSV output at {CORRIDOR_HOURLY_CSV} is fully sufficient and is what "
            f"feature_engineer.py reads by default."
        )

    centroids.to_json(CORRIDOR_CENTROIDS_JSON, orient="records", indent=2)
    print(f"[data_loader] Wrote {CORRIDOR_CENTROIDS_JSON}")
    return table


if __name__ == "__main__":
    table = run()
    print()
    print("=== Summary ===")
    print(table[["corridor_id", "timestamp", "incident_count", "high_severity_count"]].head(10))
    print()
    print("Incident count distribution:")
    print(table["incident_count"].value_counts().sort_index().head(10))
    print()
    print("Top 10 corridors by total real incidents:")
    print(
        table.groupby("corridor_id")["incident_count"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
