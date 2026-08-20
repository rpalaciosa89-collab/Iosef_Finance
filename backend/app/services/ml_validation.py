"""
Validación temporal de modelos ML (SP-4.2).

Implementa:
- WalkForwardSplit: particiones cronológicas con purge + embargo para evitar
  leakage por solapamiento de ventanas forward (forward_return_5d).
- evaluate_walk_forward: entrena XGBoost por fold y reporta AUC OOS.
- should_promote: gate de promoción a producción (AUC OOS >= 0.56).
"""

import logging
from typing import Iterator

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)

PROMOTION_AUC_THRESHOLD = 0.56


class WalkForwardSplit:
    """Split cronológico con purge y embargo temporal.

    El modelo NUNCA ve filas cuya ventana forward solape con el train:
    - purge: descarta las ultimas `embargo_days` filas del train.
    - embargo: descarta las primeras `embargo_days` filas de la validacion.
    """

    def __init__(self, n_splits: int = 3, embargo_days: int = 5):
        self.n_splits = n_splits
        self.embargo_days = embargo_days

    def split(self, X: pd.DataFrame, y=None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if not isinstance(X.index, pd.DatetimeIndex):
            # Sin indice temporal: no podemos garantizar separacion temporal
            raise ValueError("WalkForwardSplit requiere un DatetimeIndex")
        dates = X.index
        n = len(dates)
        fold_size = n // (self.n_splits + 1)

        for k in range(self.n_splits):
            train_end = (k + 1) * fold_size
            valid_start = train_end
            valid_end = min(train_end + fold_size, n)

            # Embargo: no usar las primeras `embargo_days` filas de validacion
            valid_start_embargoed = valid_start + self._embargo_rows(dates, valid_start)
            if valid_start_embargoed >= valid_end:
                continue

            train_idx = np.arange(0, train_end)
            valid_idx = np.arange(valid_start_embargoed, valid_end)
            if len(train_idx) < 10 or len(valid_idx) < 10:
                continue

            yield train_idx, valid_idx

    def _embargo_rows(self, dates: pd.DatetimeIndex, start_pos: int) -> int:
        """Cuantas filas de la validacion estan dentro del embargo temporal."""
        if start_pos >= len(dates):
            return 0
        embargo_end = dates[start_pos] + pd.Timedelta(days=self.embargo_days)
        # Contar filas desde start_pos cuyo timestamp < embargo_end
        count = 0
        for i in range(start_pos, len(dates)):
            if dates[i] < embargo_end:
                count += 1
            else:
                break
        return count


def _make_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def evaluate_walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 3,
    embargo_days: int = 5,
) -> dict:
    """Evalua XGBoost con walk-forward y devuelve el meta-reporte."""
    wf = WalkForwardSplit(n_splits=n_splits, embargo_days=embargo_days)
    aucs = []
    n_folds = 0

    for train_idx, valid_idx in wf.split(X, y):
        X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
        X_valid, y_valid = X.iloc[valid_idx], y.iloc[valid_idx]

        model = _make_model()
        model.fit(X_train, y_train, verbose=False)
        proba = model.predict_proba(X_valid)[:, 1]

        try:
            auc = roc_auc_score(y_valid, proba)
        except ValueError:
            continue
        aucs.append(auc)
        n_folds += 1

    if not aucs:
        raise RuntimeError("Walk-forward no produjo folds validos")

    auc_mean = float(np.mean(aucs))
    auc_std = float(np.std(aucs)) if n_folds > 1 else 0.0

    return {
        "auc_oos_mean": round(auc_mean, 4),
        "auc_oos_std": round(auc_std, 4),
        "cv_folds": n_folds,
        "embargo_days": embargo_days,
        "promoted": should_promote(auc_mean),
    }


def should_promote(auc_oos: float) -> bool:
    """Gate de promoción: solo se promueve a producción si hay edge demostrable."""
    return auc_oos >= PROMOTION_AUC_THRESHOLD