# DEPRECATED — 2026-06-10 (Ola 6)
# Este script usa datos sintéticos (np.random).
# Para entrenar con datos reales de mercado, usar:
#   python scripts/train_xgboost_real.py
#
# Este archivo se conserva por referencia histórica.

import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score
import joblib
import logging
from pathlib import Path

import warnings
warnings.warn(
    "train_xgboost.py usa datos sintéticos. Usa train_xgboost_real.py para datos reales de mercado.",
    DeprecationWarning,
    stacklevel=2,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Rutas
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "xgboost_signal_scorer.pkl"

def generate_synthetic_dataset(samples=5000):
    """
    Temporalmente genera un dataset sintético para el arranque (Bootstrapping).
    En producción (Fase viva), este dataset vendrá de trades.db y data_pipeline.py.
    """
    logger.info("Generando dataset sintético de bootstrapping...")
    np.random.seed(42)
    
    # Features
    log_return = np.random.normal(0, 0.01, samples)
    volatility = np.random.uniform(0.005, 0.03, samples)
    momentum = np.random.normal(0, 0.05, samples)
    rsi_14 = np.random.uniform(20, 80, samples)
    macd_hist = np.random.normal(0, 0.5, samples)
    
    # Label: 1 si el precio subió en los siguientes 5 periodos, 0 si no.
    # Lógica sintética: alto momentum y RSI bajo aumenta la probabilidad.
    prob_success = 1 / (1 + np.exp(- (momentum*10 + (50 - rsi_14)/10 + log_return*5)))
    y = np.random.binomial(1, prob_success)
    
    X = pd.DataFrame({
        'log_return': log_return,
        'volatility_20': volatility,
        'momentum_10': momentum,
        'rsi_14': rsi_14,
        'macd_hist': macd_hist
    })
    return X, pd.Series(y)

def train_model():
    """
    Entrena el modelo XGBoost y lo guarda para inferencia en tiempo real.
    """
    logger.info("Iniciando Pipeline de Entrenamiento XGBoost (Machine Learning Alive)")
    
    # 1. Obtener datos (Usamos sintético hasta que la base de datos se llene)
    X, y = generate_synthetic_dataset(10000)
    
    # 2. Split train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 3. Inicializar y Entrenar
    # XGBoost (Licencia Apache 2.0)
    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )
    
    logger.info("Ajustando modelo...")
    model.fit(X_train, y_train)
    
    # 4. Evaluación
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    logger.info(f"Métricas de Evaluación:")
    logger.info(f"Accuracy:  {acc:.4f}")
    logger.info(f"Precision: {prec:.4f}")
    logger.info(f"ROC AUC:   {auc:.4f}")
    
    # 5. Persistir el modelo
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Modelo guardado exitosamente en: {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
