"""Everything about the saved model: loading it, predicting, and retraining it on new loans."""

from __future__ import annotations

import io
import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).parent
MODEL_FILE = HERE / "best_model.pkl"
TRAIN_FILE = HERE / "data" / "train_rows.csv.gz"
TEST_FILE = HERE / "data" / "test_rows.csv.gz"
ARCHIVE = HERE / "model_archive"
HISTORY_FILE = HERE / "data" / "retrain_history.json"

TARGET = "loan_amount"
MAX_TERM = 60
MAX_GROUP = 50
# The new model may be at most 1% worse than the old one on the shared test rows.
ALLOWED_SLOWDOWN = 1.01


class LoanModel:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._load()

    # ----- loading -------------------------------------------------------------------------------
    def _load(self) -> None:
        self.bundle = joblib.load(MODEL_FILE)
        self.train_rows = pd.read_csv(TRAIN_FILE)
        self.test_rows = pd.read_csv(TEST_FILE)
        self.features = self.bundle["features"]
        self._lower = {
            field: {value.lower(): value for value in values}
            for field, values in self.bundle["choices"].items()
        }
        self._spread = self._range_on(self.test_rows)

    def _range_on(self, rows: pd.DataFrame) -> tuple[float, float]:
        """Half of the test loans fall between these two multiples of the estimate."""
        ratio = rows[TARGET].to_numpy() / self.bundle["model"].predict(rows[self.features])
        return float(np.quantile(ratio, 0.25)), float(np.quantile(ratio, 0.75))

    # ----- inputs --------------------------------------------------------------------------------
    def choices(self, field: str) -> list[str]:
        return self.bundle["choices"][field]

    def exact_spelling(self, field: str, value: str) -> str | None:
        return self._lower[field].get(value.strip().lower())

    # ----- prediction ----------------------------------------------------------------------------
    def predict_loan_size(self, applicant: dict) -> float:
        """Same as predict_loan_size() in the notebook: one applicant in, dollars out."""
        row = pd.DataFrame([applicant], columns=self.features)
        return float(self.bundle["model"].predict(row)[0])

    def describe(self, applicant: dict, estimate: float) -> dict:
        low, high = self._spread
        return {
            "estimated_loan_usd": round(estimate, 0),
            "likely_range_usd": [round(estimate * low, 0), round(estimate * high, 0)],
            "sector": self.bundle["sector_of_activity"].get(applicant["activity"], "Unknown"),
            "model": self.bundle["model_name"],
            "model_version": self.bundle["version"],
        }

    def summary(self) -> dict:
        b = self.bundle
        return {
            "model": b["model_name"],
            "version": b["version"],
            "trained_on_rows": int(len(self.train_rows)),
            "test_rows": int(len(self.test_rows)),
            "test_metrics": b["test_metrics"],
            "baseline_mse": b["baseline_mse"],
            "deployment_rule": b["rule"],
        }

    # ----- retraining ----------------------------------------------------------------------------
    def retrain(self, csv_bytes: bytes) -> dict:
        new_rows, cleaning = self.clean_upload(csv_bytes)
        if len(new_rows) < 10:
            return {"accepted": False, "reason": f"Only {len(new_rows)} usable rows after cleaning (need at least 10).",
                    "cleaning": cleaning}

        with self.lock:
            extra_train, extra_test = train_test_split(new_rows, test_size=0.2, random_state=7)
            all_train = pd.concat([self.train_rows, extra_train], ignore_index=True)
            all_test = pd.concat([self.test_rows, extra_test], ignore_index=True)

            old_model = self.bundle["model"]
            y_log = np.log1p(all_test[TARGET])
            old_mse = mean_squared_error(y_log, np.log1p(old_model.predict(all_test[self.features])))

            inner = old_model.regressor_.steps[-1][1]
            if isinstance(inner, SGDRegressor):
                # A gradient-descent model keeps learning from where it stopped.
                new_model = deepcopy(old_model)
                encoder = new_model.regressor_.steps[0][1]
                sgd = new_model.regressor_.steps[-1][1]
                x_new = encoder.transform(extra_train[self.features])
                for _ in range(5):
                    sgd.partial_fit(x_new, np.log1p(extra_train[TARGET]).to_numpy())
                how = "continued SGD training with partial_fit on the new rows"
            else:
                # Other models are fitted again from the start on the original rows plus the new rows.
                new_model = clone(old_model).fit(all_train[self.features], all_train[TARGET])
                how = f"refitted {self.bundle['model_name']} on {len(self.train_rows):,} original + {len(extra_train):,} new rows"

            pred_log = np.log1p(new_model.predict(all_test[self.features]))
            new_mse = mean_squared_error(y_log, pred_log)
            new_r2 = r2_score(y_log, pred_log)
            baseline = mean_squared_error(y_log, np.full(len(y_log), np.log1p(all_train[TARGET]).mean()))
            rule = self.bundle["rule"]
            checks = {
                "no_worse_than_current_model": bool(new_mse <= old_mse * ALLOWED_SLOWDOWN),
                f"r2_at_least_{rule['min_r2']}": bool(new_r2 >= rule["min_r2"]),
                "mse_at_most_half_of_baseline": bool(new_mse <= rule["max_ratio_to_baseline"] * baseline),
            }
            outcome = {
                "cleaning": cleaning,
                "method": how,
                "compared_on_test_rows": int(len(all_test)),
                "current_model": {"version": self.bundle["version"], "test_mse": round(float(old_mse), 5)},
                "new_model": {"test_mse": round(float(new_mse), 5), "test_r2": round(float(new_r2), 4)},
                "checks": checks,
            }

            if not all(checks.values()):
                outcome.update(accepted=False, reason="The new model did not pass every check, so the current model stays.")
                self._remember(outcome)
                return outcome

            ARCHIVE.mkdir(exist_ok=True)
            joblib.dump(self.bundle, ARCHIVE / f"model_v{self.bundle['version']}.pkl", compress=3)

            ratio_err = np.abs(np.expm1(pred_log) - all_test[TARGET].to_numpy()) / all_test[TARGET].to_numpy()
            fresh = {**self.bundle, "model": new_model, "version": self.bundle["version"] + 1,
                     "baseline_mse": float(baseline),
                     "test_metrics": {**self.bundle["test_metrics"], "test MSE": float(new_mse), "test R2": float(new_r2),
                                      "median error %": float(np.median(ratio_err) * 100)}}
            joblib.dump(fresh, MODEL_FILE, compress=3)
            all_train.to_csv(TRAIN_FILE, index=False)
            all_test.to_csv(TEST_FILE, index=False)
            self._load()

            outcome.update(accepted=True, reason="All checks passed. /predict now uses the new model.",
                           new_version=self.bundle["version"])
            self._remember(outcome)
            return outcome

    def clean_upload(self, csv_bytes: bytes) -> tuple[pd.DataFrame, dict]:
        """Applies the notebook's cleaning to a CSV in the Kiva format."""
        try:
            frame = pd.read_csv(io.BytesIO(csv_bytes))
        except Exception as error:
            raise ValueError(f"The file is not a readable CSV: {error}") from error
        frame.columns = [c.strip() for c in frame.columns]

        if "borrower_count" not in frame.columns:
            if "borrower_genders" not in frame.columns:
                raise ValueError("The CSV needs either a borrower_genders column (Kiva format) or a borrower_count column.")
            genders = frame["borrower_genders"].fillna("").astype(str)
            women, men = genders.str.count(r"\bfemale\b"), genders.str.count(r"\bmale\b")
            frame = frame[(women > 0) & (men == 0)].copy()
            frame["borrower_count"] = women[frame.index]
        if "repeat_borrower" not in frame.columns:
            tags = frame["tags"] if "tags" in frame.columns else pd.Series("", index=frame.index)
            frame["repeat_borrower"] = tags.fillna("").astype(str).str.contains("#Repeat Borrower").astype(int)

        needed = self.features + [TARGET]
        missing = [c for c in needed if c not in frame.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}. Use the same columns as the Kiva training data.")

        report = {"rows_received": int(len(pd.read_csv(io.BytesIO(csv_bytes)))), "women_led_rows": int(len(frame))}
        frame[TARGET] = pd.to_numeric(frame[TARGET], errors="coerce")
        frame["term_in_months"] = pd.to_numeric(frame["term_in_months"], errors="coerce")
        frame["borrower_count"] = pd.to_numeric(frame["borrower_count"], errors="coerce")

        for column in ["country", "activity"]:
            frame[column] = frame[column].map(
                lambda v: self.exact_spelling(column, str(v)) if pd.notna(v) else None)
        frame["repayment_interval"] = frame["repayment_interval"].astype(str).str.strip().str.lower()

        keep = (frame[TARGET] > 0) & frame["term_in_months"].between(1, MAX_TERM) & frame["borrower_count"].between(1, MAX_GROUP)
        keep &= frame["country"].notna() & frame["activity"].notna()
        keep &= frame["repayment_interval"].isin(self.choices("repayment_interval"))
        report["rows_removed_by_cleaning"] = int((~keep).sum())
        frame = frame[keep]
        report["rows_used"] = int(len(frame))
        return frame[needed].reset_index(drop=True), report

    def _remember(self, outcome: dict) -> None:
        try:
            history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
            history.append({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **outcome})
            HISTORY_FILE.write_text(json.dumps(history, indent=2))
        except OSError:
            pass


MODEL = LoanModel()
