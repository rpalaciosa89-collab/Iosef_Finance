"""
scripts/download_titan_history.py

Pipeline industrial de descarga de historia: 15 años, Titan 100.
- Descarga datos OHLCV (Open, High, Low, Close, Volume) desde yfinance (MIT).
- Almacena en formato .parquet por ticker (ultra-rápido, columnar).
- Incluye retry y manejo robusto de errores por ticker.
- El Volumen se preserva explícitamente como columna de primera clase.

Responsable: Javier (Pipeline) | Auditado por: Carlos (Quant)
"""

import sys
import time
import logging
from pathlib import Path

import yfinance as yf
import pandas as pd

# Ajustar el path para importar el universo
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from config.titan_universe import TITAN_100, SECTOR_MAP

# ── Configuración ────────────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data" / "titan_parquet"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_START = "2008-01-01"   # 15+ años: captura Subprime Crisis, Flash Crash, COVID, post-FED
HISTORY_END   = "2025-12-31"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def download_ticker(ticker: str, retries: int = 3) -> pd.DataFrame | None:
    """
    Descarga OHLCV diario desde yfinance con manejo de errores y reintentos.
    Retorna un DataFrame o None si falla después de N intentos.
    """
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                ticker,
                start=HISTORY_START,
                end=HISTORY_END,
                interval="1d",
                auto_adjust=True,   # Ajuste automático por splits/dividendos
                progress=False,
                timeout=30,
            )
            if df.empty:
                logger.warning(f"[{ticker}] Sin datos disponibles.")
                return None

            # Aplanar columnas multi-índice que yfinance puede generar
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Normalizar nombres de columna
            df.columns = [c.lower().replace(" ", "_") for c in df.columns]

            # Asegurar que Volume esté presente (innegociable según instrucciones)
            required = {"open", "high", "low", "close", "volume"}
            if not required.issubset(set(df.columns)):
                logger.warning(f"[{ticker}] Columnas faltantes: {required - set(df.columns)}")
                return None

            df.index = pd.to_datetime(df.index)
            df.index.name = "date"

            # Agregar metadatos de sector como columna constante
            df["sector"] = SECTOR_MAP.get(ticker, "UNKNOWN")
            df["ticker"] = ticker

            logger.info(
                f"[{ticker}] ✓ {len(df):>5} días ({df.index[0].date()} → {df.index[-1].date()})"
            )
            return df

        except Exception as e:
            logger.error(f"[{ticker}] Intento {attempt}/{retries} fallido: {e}")
            time.sleep(2 ** attempt)  # Backoff exponencial

    logger.error(f"[{ticker}] ✗ Descarga fallida después de {retries} intentos.")
    return None


def run():
    logger.info("=" * 60)
    logger.info(f"TITAN 100 — Descarga de 15 años de historia")
    logger.info(f"Universo: {len(TITAN_100)} tickers únicos")
    logger.info(f"Rango: {HISTORY_START} → {HISTORY_END}")
    logger.info("=" * 60)

    success, failed = [], []

    for i, ticker in enumerate(TITAN_100, 1):
        logger.info(f"[{i:>3}/{len(TITAN_100)}] Descargando {ticker}...")
        df = download_ticker(ticker)

        if df is not None:
            out_path = DATA_DIR / f"{ticker.replace('/', '_')}.parquet"
            df.to_parquet(out_path, index=True)
            success.append(ticker)
        else:
            failed.append(ticker)

        # Pausa cortés para no saturar la API (yfinance es pública)
        time.sleep(0.5)

    logger.info("=" * 60)
    logger.info(f"✓ Descargados exitosamente: {len(success)}/{len(TITAN_100)}")
    if failed:
        logger.warning(f"✗ Fallidos ({len(failed)}): {failed}")
    logger.info(f"  Datos almacenados en: {DATA_DIR}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
