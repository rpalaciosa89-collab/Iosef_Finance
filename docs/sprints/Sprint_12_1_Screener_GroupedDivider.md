# Sprint 12.1: Agrupación en Tiempo Real del Screener

**Fecha:** 5 de Junio de 2026

## Problema Raíz: ¿Por qué mostraba 66/66 tickers?

Se identificaron **dos causas independientes** que se combinaron para reducir de 98 a 66 tickers:

1. **Filtro de histórico insuficiente (< 200 velas):** Los tickers con poco historial disponible en yfinance eran descartados con un `continue` sin ser agregados a `results`, haciéndolos invisibles para el frontend.

2. **Lógica de inclusión mal ubicada (el bug principal):** Antes de Sprint 12, los tickers que no tenían señal activa eran ignorados. Al refactorizar para el auto-trading, se rompió el flujo de "agregar siempre a results".

3. **Mismatch de tipos en timestamps:** Al cambiar de timestamps Unix float a ISO strings en Sprint 12, el código existente que hacía `now - signal_detected_at` fallaba con error de tipo. Esto reventaba el escaneo completo.

4. **Caché vieja (Redis + Parquet + JSON snapshot):** Los datos obsoletos persistían incluso después de corregir el código, porque el sistema leía el cache antes de llegar al código nuevo.

## Correcciones Aplicadas

### Backend (`server.py`)
- **Tickers con < 200 velas:** Ahora se construye un `dummy_entry` y se agrega a `results` igual que el resto. El usuario ve el ticker en la tabla, marcado con `decision_clarity: baja` y sin señal activa.
- **`_format_lifecycle_output`:** Reescrito para aceptar tanto `float` (Unix) como `str` (ISO) en `signal_detected_at` mediante función `_parse_ts`.
- **Bloque `existing signal`:** Misma lógica de compatibilidad aplicada para `detected_at`.
- **Endpoint `/api/scan/refresh` (POST):** Nuevo endpoint que fuerza un escaneo inmediato, borrando la dependencia del ciclo de 60 segundos. Útil para debugging y verificaciones rápidas.

### Frontend (`ScreenerTable.tsx`)
- Tabla reescrita para mostrar **dos grupos separados** por una línea divisoria visual:
  - **Premium (≥70% o ≤30%):** Ordenados por certidumbre, con nombre en dorado y badge iluminado.
  - **Resto del mercado:** Ordenados por la columna seleccionada por el usuario.
- Contador en el filter bar indica cuántos activos son Premium en tiempo real.
- Si un activo tiene 0 datos (dummy), muestra `–` en lugar de `0.00`.

## Resultado
- **Total tickers servidos:** 98 / 98 (TITAN_100)
- **Premium detectados en la sesión:** 22
- **Scan forzado verificado:** `{"status": "ok", "market": "titan100", "tickers": 98}`
