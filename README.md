# Iosef_Finance

Plataforma financiera web-first de alto rendimiento inspirada en Finviz, diseñada para análisis cuantitativo, flujos de datos en tiempo real y automatización mediante agentes inteligentes.

## Estructura del Proyecto

El proyecto está organizado en los siguientes módulos:

* **`backend/`**: Servidor de APIs REST de alta velocidad construido con **Python 3.12+** y **FastAPI**. Maneja autenticación, filtros de búsqueda avanzados (screener), agregación de datos e integración de modelos.
* **`frontend/`**: Cliente web interactivo y ultra-responsivo (web-first).
* **`realtime/`**: Ingesta y distribución de datos en tiempo real mediante WebSockets o SSE (Server-Sent Events).
* **`cache/`**: Almacenamiento temporal optimizado (Redis/in-memory) para minimizar latencia en lecturas repetidas de cotizaciones.
* **`snapshots/`**: Respaldos e históricos del estado del mercado y de la base de datos.
* **`data/`**: Repositorio de datos estructurados, históricos de precios y metadatos de tickers.
* **`agents/`**: Agentes autónomos de análisis financiero y alertas inteligentes.

## Requisitos de Entorno

* **Python 3.12+**
* **Node.js 18+**

## Inicio Rápido (Backend)

1. Ingresa a la carpeta del backend:
   ```bash
   cd backend
   ```

2. Crea y activa tu entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -e .
   ```

4. Ejecuta el servidor de desarrollo:
   ```bash
   fastapi dev app/main.py
   # O alternativamente:
   uvicorn app.main:app --reload
   ```
