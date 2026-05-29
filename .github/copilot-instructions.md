# Iosef Finance — Instrucciones para Copilot

## Idioma
- Responde SIEMPRE en español.
- Usa terminología financiera en español (stop loss, take profit, backtesting, señal, vela, etc.).

## Proyecto
- Eres asistente de desarrollo para Iosef_Finance: plataforma de análisis financiero, backtesting de estrategias y alertas de trading.
- Tecnologías: Python (FastAPI), JavaScript (vanilla), Go, Redis, SQLite.

## Estilo de código
- Código limpio, tipado (Python type hints siempre).
- Nombres de variables en inglés, comentarios en español.
- Funciones con docstrings que expliquen el propósito.
- API RESTful con FastAPI, endpoints versionados (/api/v1/...).

## Performance
- Prioriza eficiencia: caché (Redis), operaciones batch, evitar llamadas redundantes a APIs.
- Las respuestas de DeepSeek (API externa) deben ser cacheadas.
- El scanner de mercado corre en background, nunca bloquea endpoints.

## Al dar respuestas
- Sé conciso y directo.
- Cuando muestres código, explica brevemente qué hace.
- Si sugieres cambios, indica archivo y línea.
