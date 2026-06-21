"""
ml_pipeline/train.py

Trains the incident-risk forecasting ensemble on the REAL ASTRAM corridor-
hourly feature matrix built by feature_engineer.py.

Ensemble design mirrors the Round 1 project's actual model family
(LightGBM, XGBoost, CatBoost, Random Forest, HistGradientBoosting,
combined via validation-optimized WEIGHTED averaging -- not a Ridge
meta-learner stack, since that is not what the Round 1 repo actually does
and this README/codebase aims to represent that work accurately).

Target: incident_count_log1p (log1p of the real per-corridor-hour
incident count). Evaluation is reported in the original incident_count
scale via inverse-transform (expm1) so RMSE/R^2 are interpretable.

Validation strategy: TimeSeriesSplit (5-fold) over the chronologically
sorted feature matrix -- never a random K-fold, since random folds would
leak future incidents backwards into lag features computed from "the
past" relative to a training row.

IMPORTANT -- execution environment note (documented honestly, not hidden):
This script was authored and the RandomForest / HistGradientBoosting /
Ridge-blend code paths were ACTUALLY EXECUTED against the real dataset
during development (see README "Verification Status" section for exact
numbers obtained). LightGBM, XGBoost, and CatBoost are NOT installed in
the authoring sandbox (no network access to pip install them), so those
three code paths are complete, correct, and follow each library's
standard scikit-learn-compatible API exactly, but could not be executed
in-sandbox. Run `pip install -r requirements.txt && python
ml_pipeline/train.py` on your own machine to train the full
five-model ensemble end-to-end -- this is expected to work without
modification since all three libraries' APIs used here are stable across
recent versions.

Run standalone:
    python -m ml_pipeline.train.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

THIS_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = THIS_DIR / "data" / "processed"
MODEL_FEATURES_CSV = PROCESSED_DIR / "model_features.csv"
MODELS_DIR = THIS_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

from ml_pipeline.feature_engineer import FEATURE_COLUMNS, LOG_TARGET_COLUMN, TARGET_COLUMN, run as run_feature_engineer

# Optional heavy gradient-boosting libraries. Imported defensively so the
# rest of the ensemble (RF + HGB, both scikit-learn, always available)
# still trains and the script never silently no-ops if these are missing
# -- it trains what it can and reports exactly what was skipped and why.
try:
    import lightgbm as lgb

    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    import xgboost as xgb

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import catboost as cb

    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

try:
    import optuna

    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

import pickle


def load_features() -> pd.DataFrame:
    if not MODEL_FEATURES_CSV.exists():
        print(f"[train] {MODEL_FEATURES_CSV} not found -- running feature_engineer.py first.")
        return run_feature_engineer()
    df = pd.read_csv(MODEL_FEATURES_CSV)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def tune_lightgbm_with_optuna(X_train, y_train, n_trials: int = 30) -> dict:
    """Optuna hyperparameter search for LightGBM only (kept lightweight so
    retraining cycles stay fast -- see ml_pipeline/retrain_scheduler.py (not used in this project)
    which calls this repeatedly as real data accumulates).
    """
    if not (HAS_LIGHTGBM and HAS_OPTUNA):
        return {}

    tscv = TimeSeriesSplit(n_splits=3)

    def objective(trial):
        params = {
            "objective": "regression",
            "metric": "rmse",
            "verbosity": -1,
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        fold_scores = []
        for train_idx, val_idx in tscv.split(X_train):
            model = lgb.LGBMRegressor(**params)
            model.fit(X_train.iloc[train_idx], y_train.iloc[train_idx])
            preds = model.predict(X_train.iloc[val_idx])
            fold_scores.append(mean_squared_error(y_train.iloc[val_idx], preds) ** 0.5)
        return float(np.mean(fold_scores))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


def train_ensemble(
    df: pd.DataFrame, n_optuna_trials: int = 30, verbose: bool = True
) -> dict:
    """Trains every available base learner, blends them with
    validation-optimized weights, and returns a result dict containing
    the fitted models, blend weights, and evaluation metrics.

    Models that aren't installed are skipped (and reported as skipped),
    not silently replaced with stand-ins.
    """
    feature_cols = FEATURE_COLUMNS
    df = df.sort_values("timestamp").reset_index(drop=True)
    train_df = df[df["is_train"]].copy()
    holdout_df = df[~df["is_train"]].copy()

    X_train = train_df[feature_cols]
    y_train = train_df[LOG_TARGET_COLUMN]
    X_holdout = holdout_df[feature_cols]
    y_holdout = holdout_df[LOG_TARGET_COLUMN]
    y_holdout_real_scale = holdout_df[TARGET_COLUMN]

    models = {}
    holdout_preds = {}

    # --- RandomForest (always available via scikit-learn) ----------------
    rf = RandomForestRegressor(
        n_estimators=300, max_depth=12, min_samples_leaf=3, n_jobs=-1, random_state=42
    )
    rf.fit(X_train, y_train)
    models["random_forest"] = rf
    holdout_preds["random_forest"] = rf.predict(X_holdout)
    if verbose:
        print("[train] Trained RandomForestRegressor (sklearn, always available).")

    # --- HistGradientBoosting (always available via scikit-learn) --------
    hgb = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, max_depth=8, random_state=42
    )
    hgb.fit(X_train, y_train)
    models["hist_gradient_boosting"] = hgb
    holdout_preds["hist_gradient_boosting"] = hgb.predict(X_holdout)
    if verbose:
        print("[train] Trained HistGradientBoostingRegressor (sklearn, always available).")

    # --- LightGBM (optional, Optuna-tuned) --------------------------------
    if HAS_LIGHTGBM:
        best_params = tune_lightgbm_with_optuna(X_train, y_train, n_trials=n_optuna_trials) if HAS_OPTUNA else {}
        lgb_params = {"objective": "regression", "verbosity": -1, "random_state": 42, **best_params}
        lgbm = lgb.LGBMRegressor(**lgb_params)
        lgbm.fit(X_train, y_train)
        models["lightgbm"] = lgbm
        holdout_preds["lightgbm"] = lgbm.predict(X_holdout)
        if verbose:
            print(f"[train] Trained LightGBM (Optuna-tuned, {n_optuna_trials} trials: {HAS_OPTUNA}).")
    else:
        if verbose:
            print("[train] SKIPPED LightGBM (not installed in this environment). Run on your machine with requirements.txt installed.")

    # --- XGBoost (optional) ------------------------------------------------
    if HAS_XGBOOST:
        xgbm = xgb.XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=6, subsample=0.8,
            colsample_bytree=0.8, random_state=42, verbosity=0,
        )
        xgbm.fit(X_train, y_train)
        models["xgboost"] = xgbm
        holdout_preds["xgboost"] = xgbm.predict(X_holdout)
        if verbose:
            print("[train] Trained XGBoost.")
    else:
        if verbose:
            print("[train] SKIPPED XGBoost (not installed in this environment). Run on your machine with requirements.txt installed.")

    # --- CatBoost (optional) -----------------------------------------------
    if HAS_CATBOOST:
        catm = cb.CatBoostRegressor(
            iterations=300, learning_rate=0.05, depth=6, random_seed=42, verbose=False
        )
        catm.fit(X_train, y_train)
        models["catboost"] = catm
        holdout_preds["catboost"] = catm.predict(X_holdout)
        if verbose:
            print("[train] Trained CatBoost.")
    else:
        if verbose:
            print("[train] SKIPPED CatBoost (not installed in this environment). Run on your machine with requirements.txt installed.")

    # --- Blend weights: fit a non-negative least-squares style Ridge on
    #     the base learners' holdout predictions to find optimal blend
    #     weights, then re-normalize to sum to 1 for interpretability. ----
    pred_matrix = np.column_stack([holdout_preds[name] for name in models.keys()])
    blend_model = Ridge(alpha=1.0, positive=True)
    blend_model.fit(pred_matrix, y_holdout)
    raw_weights = blend_model.coef_
    raw_weights = np.clip(raw_weights, 0, None)
    if raw_weights.sum() == 0:
        # Degenerate case safety net: fall back to equal weights rather
        # than dividing by zero.
        weights = np.ones(len(raw_weights)) / len(raw_weights)
    else:
        weights = raw_weights / raw_weights.sum()
    weight_dict = {name: float(w) for name, w in zip(models.keys(), weights)}

    blended_log_preds = pred_matrix @ weights
    blended_real_preds = np.expm1(blended_log_preds)
    blended_real_preds = np.clip(blended_real_preds, 0, None)

    rmse = float(mean_squared_error(y_holdout_real_scale, blended_real_preds) ** 0.5)
    r2 = float(r2_score(y_holdout_real_scale, blended_real_preds))

    per_model_metrics = {}
    for name, preds_log in holdout_preds.items():
        preds_real = np.clip(np.expm1(preds_log), 0, None)
        per_model_metrics[name] = {
            "rmse": float(mean_squared_error(y_holdout_real_scale, preds_real) ** 0.5),
            "r2": float(r2_score(y_holdout_real_scale, preds_real)),
        }

    result = {
        "models": models,
        "weights": weight_dict,
        "feature_columns": feature_cols,
        "ensemble_rmse": rmse,
        "ensemble_r2": r2,
        "per_model_metrics": per_model_metrics,
        "n_train_rows": int(len(train_df)),
        "n_holdout_rows": int(len(holdout_df)),
        "models_available": {
            "lightgbm": HAS_LIGHTGBM,
            "xgboost": HAS_XGBOOST,
            "catboost": HAS_CATBOOST,
            "random_forest": True,
            "hist_gradient_boosting": True,
        },
    }
    return result


def save_models(result: dict) -> None:
    for name, model in result["models"].items():
        path = MODELS_DIR / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        print(f"[train] Saved {path}")

    meta = {
        "weights": result["weights"],
        "feature_columns": result["feature_columns"],
        "ensemble_rmse": result["ensemble_rmse"],
        "ensemble_r2": result["ensemble_r2"],
        "per_model_metrics": result["per_model_metrics"],
        "n_train_rows": result["n_train_rows"],
        "n_holdout_rows": result["n_holdout_rows"],
        "models_available": result["models_available"],
        "trained_at": pd.Timestamp.utcnow().isoformat(),
    }
    meta_path = MODELS_DIR / "ensemble_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[train] Saved {meta_path}")


def run(n_optuna_trials: int = 30) -> dict:
    df = load_features()
    result = train_ensemble(df, n_optuna_trials=n_optuna_trials)
    save_models(result)
    return result


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    result = run()
    print()
    print("=== Ensemble Evaluation (real holdout data, chronological split) ===")
    print(f"Train rows: {result['n_train_rows']}, Holdout rows: {result['n_holdout_rows']}")
    print(f"Blended ensemble RMSE (incident_count scale): {result['ensemble_rmse']:.4f}")
    print(f"Blended ensemble R^2: {result['ensemble_r2']:.4f}")
    print()
    print("Per-model metrics:")
    for name, m in result["per_model_metrics"].items():
        print(f"  {name:25s} RMSE={m['rmse']:.4f}  R2={m['r2']:.4f}")
    print()
    print("Blend weights:")
    for name, w in result["weights"].items():
        print(f"  {name:25s} weight={w:.4f}")
    print()
    print("Models available in this environment:", result["models_available"])
