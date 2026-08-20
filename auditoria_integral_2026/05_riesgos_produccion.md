# 6. Riesgos de Producción

---

## 6.1 Qué impide o compromete un despliegue sólido

1. **Autenticación comprometida:** El JWT secret hardcodeado permite a cualquiera con acceso al código generar tokens válidos.

2. **CORS mal configurado:** `allow_origins=["*"]` con `allow_credentials=True` puede causar fallos en navegadores modernos y exponer datos.

3. **URLs hardcodeadas en frontend:** El frontend compilado apunta a `localhost:8002`, inutilizable en producción sin rebuild.

4. **Sin HTTPS:** No hay configuración de TLS en Nginx ni en FastAPI. Las credenciales viajan en texto plano.

5. **Sin healthchecks:** Docker Compose no verifica que los servicios estén realmente listos antes de enrutar tráfico.

6. **Sin CI/CD:** No hay pipeline que garantice que el código deployado pasa tests, lint y build.

7. **Modelo ML no válido:** XGBoost entrenado con datos sintéticos produce predicciones sin valor.

8. **Sin separación de entornos:** La misma configuración sirve para dev, staging y producción.

## 6.2 Qué fallaría bajo carga, errores externos o uso real

| Escenario | Consecuencia |
|---|---|
| 50+ usuarios concurrentes | Operaciones bloqueantes (yfinance, signal evaluation) saturan el event loop |
| yfinance rate limited o caído | El screener y datos de mercado dejan de funcionar sin degradación graceful |
| Redis caído | Todas las requests van a yfinance directamente, multiplicando latencia y rate limiting |
| Disco lleno | SQLite puede corromperse; snapshots y parquets pueden fallar silenciosamente |
| Ataque de fuerza bruta en login | Sin rate limiting, un atacante puede probar contraseñas ilimitadamente |
| Token JWT robado | Sin invalidación, el atacante tiene acceso por hasta 7 días |

## 6.3 Qué dependencias son frágiles

| Dependencia | Fragilidad |
|---|---|
| yfinance | API no oficial, sin SLA, sujeta a rate limiting y cambios de schema |
| DeepSeek API | API externa con disponibilidad y costos variables |
| Redis (single instance) | Punto único de fallo para toda la capa de caché |
| SQLite | No diseñado para concurrencia; riesgo de corrupción bajo carga |
| Modelos ML locales | Si el archivo `.pth` o `.pkl` falta o está corrupto, el scoring falla silenciosamente (retorna 50.0) |

## 6.4 Qué observabilidad falta

- Sin health endpoint (`/health`)
- Sin métricas de aplicación (Prometheus/Grafana)
- Sin alertas configuradas
- Sin logging estructurado (JSON)
- Sin tracing distribuido
- Sin monitoreo de Redis (hit/miss rate, memoria)
- Sin monitoreo de SQLite (tamaño, fragmentación)
- Sin monitoreo de modelos ML (drift, accuracy en producción)
- Sin alertas de errores (Sentry o similar)
