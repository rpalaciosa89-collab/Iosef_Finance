"""Cache de scan en Parquet.

Histórico del bug SP-3.1:
- `pa.Table.from_pydict` infiere el tipo de cada columna desde la primera fila.
- El payload del scan mezcla tipos en una misma columna (timestamps ISO string,
  números, bools, dicts). Esto rompía la escritura con:
  `Could not convert '2026-08-20T06:57:54.871572Z' with type str: tried to convert to double`.

Solución elegida (blob JSON):
- El payload completo se serializa a JSON string y se guarda en una sola columna.
- Round-trip fiel garantizado por `json` (int/float/str/bool/None/dict/list).
- El coste de compresión columnar es irrelevante para un payload de ~100 tickers.
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


PARQUET_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "cache", "parquet"
)
os.makedirs(PARQUET_CACHE_DIR, exist_ok=True)
PARQUET_CACHE_TTL = 60  # seconds, same as scan interval


def _parquet_cache_path(market: str) -> str:
    return os.path.join(PARQUET_CACHE_DIR, f"scan_{market}.parquet")


def write_parquet_cache(market: str, payload: dict) -> None:
    """Write scan payload as a JSON blob inside a single-column Parquet file."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        blob = json.dumps(payload, default=str, ensure_ascii=False)
        table = pa.table({"payload": [blob]})
        pq.write_table(table, _parquet_cache_path(market))
    except ImportError:
        pass  # pyarrow not installed, skip parquet
    except Exception as e:
        logger.warning(f"[parquet] Write error for {market}: {e}")


def read_parquet_cache(market: str) -> Optional[dict]:
    """Restore scan payload from the Parquet cache (None if stale or missing)."""
    try:
        import pyarrow.parquet as pq

        parq_path = _parquet_cache_path(market)
        if os.path.exists(parq_path):
            cache_mtime = os.path.getmtime(parq_path)
            if time.time() - cache_mtime < PARQUET_CACHE_TTL:
                table = pq.read_table(parq_path)
                blob = table.to_pylist()[0]["payload"]
                return json.loads(blob)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[parquet] Read error for {market}: {e}")
    return None