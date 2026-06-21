"""
ml_pipeline/predict_event.py

Given a new (real or hypothetical) event's known-at-report-time context,
predicts its expected duration and severity using the REAL-data-trained
ensemble from train_event_model.py.

This answers the hackathon theme's core question directly: "How can
historical and real-time data be used to forecast event-related traffic
impact?" -- by forecasting impact (duration_minutes, severity_score) from
historical patterns in the real ASTRAM dataset for similar past events
(same event_cause, corridor, zone, time-of-day).

Run standalone:
    python -m ml_pipeline.predict_event.py --event_cause construction \
        --corridor "Mysore Road" --zone "West Zone 1" --hour 10 \
        --day_of_week 2 --is_planned 1
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MODELS_DIR = THIS_DIR / "models"
EVENT_MODEL_META_PATH = MODELS_DIR / "event_model_meta.json"

from ml_pipeline.train_event_model import CATEGORICAL_COLUMNS, NUMERIC_FEATURE_COLUMNS


def load_event_models() -> dict:
    if not EVENT_MODEL_META_PATH.exists():
        raise FileNotFoundError(f"{EVENT_MODEL_META_PATH} not found. Run train_event_model.py first.")
    with open(EVENT_MODEL_META_PATH) as f:
        meta = json.load(f)

    duration_models = {}
    for name in meta["duration_model"]["weights"].keys():
        path = MODELS_DIR / f"event_duration_{name}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                duration_models[name] = pickle.load(f)

    severity_models = {}
    for name in meta["severity_model"]["weights"].keys():
        path = MODELS_DIR / f"event_severity_{name}.pkl"
        if path.exists():
            with open(path, "rb") as f:
                severity_models[name] = pickle.load(f)

    return {"meta": meta, "duration_models": duration_models, "severity_models": severity_models}


def _encode_input(
    event_cause: str, corridor: str, zone: str, hour: int, day_of_week: int, is_planned: int, encodings: dict, target_key: str
) -> pd.DataFrame:
    is_weekend = int(day_of_week in (5, 6))
    is_peak_hour = int(hour in (7, 8, 9, 17, 18, 19))

    row = {
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_peak_hour": is_peak_hour,
        "is_planned": is_planned,
    }
    raw_values = {"event_cause": event_cause, "corridor": corridor, "zone": zone}
    for col in CATEGORICAL_COLUMNS:
        enc = encodings[col]
        means = enc["means"]
        global_mean = enc["global_mean"]
        row[f"{col}_mean_encoded_{target_key}"] = means.get(raw_values[col], global_mean)

    feature_cols = NUMERIC_FEATURE_COLUMNS + [f"{c}_mean_encoded_{target_key}" for c in CATEGORICAL_COLUMNS]
    return pd.DataFrame([row])[feature_cols]


def _blend_predict(models: dict, weights: dict, X: pd.DataFrame) -> float:
    available = {name: w for name, w in weights.items() if name in models}
    total = sum(available.values())
    normalized = {name: w / total for name, w in available.items()} if total > 0 else {
        name: 1.0 / len(models) for name in models
    }
    pred = 0.0
    for name, model in models.items():
        pred += normalized[name] * model.predict(X)[0]
    return float(pred)


def predict_event(
    event_cause: str, corridor: str, zone: str, hour: int, day_of_week: int, is_planned: int = 1
) -> dict:
    bundle = load_event_models()
    meta = bundle["meta"]

    dur_X = _encode_input(
        event_cause, corridor, zone, hour, day_of_week, is_planned,
        meta["duration_model"]["encodings"], target_key="duration_minutes",
    )
    dur_pred_log = _blend_predict(bundle["duration_models"], meta["duration_model"]["weights"], dur_X)
    duration_minutes = float(np.clip(np.expm1(dur_pred_log), 1, None))

    sev_X = _encode_input(
        event_cause, corridor, zone, hour, day_of_week, is_planned,
        meta["severity_model"]["encodings"], target_key="severity_score",
    )
    severity_score = float(np.clip(_blend_predict(bundle["severity_models"], meta["severity_model"]["weights"], sev_X), 0, 1))

    if severity_score >= 0.7:
        impact_level = "HIGH"
    elif severity_score >= 0.4:
        impact_level = "MEDIUM"
    else:
        impact_level = "LOW"

    rare_category_flag = event_cause in {"protest", "vip_movement", "tree_fall", "road_conditions"}

    return {
        "event_cause": event_cause,
        "corridor": corridor,
        "zone": zone,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_planned": bool(is_planned),
        "predicted_duration_minutes": round(duration_minutes, 1),
        "predicted_duration_human": _humanize_minutes(duration_minutes),
        "predicted_severity_score": round(severity_score, 3),
        "impact_level": impact_level,
        "model_rmse_minutes": round(meta["duration_model"]["rmse_minutes"], 1),
        "model_r2_duration": round(meta["duration_model"]["r2"], 3),
        "model_r2_severity": round(meta["severity_model"]["r2"], 3),
        "rare_category_low_confidence": rare_category_flag,
        "data_provenance": "real_historical_astram_event_log",
    }


def _humanize_minutes(minutes: float) -> str:
    if minutes < 60:
        return f"{minutes:.0f} min"
    hours = minutes / 60.0
    return f"{hours:.1f} hr"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--event_cause", type=str, default="construction")
    parser.add_argument("--corridor", type=str, default="Mysore Road")
    parser.add_argument("--zone", type=str, default="West Zone 1")
    parser.add_argument("--hour", type=int, default=10)
    parser.add_argument("--day_of_week", type=int, default=2)
    parser.add_argument("--is_planned", type=int, default=1, choices=[0, 1])
    args = parser.parse_args()

    result = predict_event(
        args.event_cause, args.corridor, args.zone, args.hour, args.day_of_week, args.is_planned
    )
    print(json.dumps(result, indent=2))
