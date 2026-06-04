# Registro de Aprendizajes

Este documento almacena los descubrimientos técnicos, cuellos de botella identificados y soluciones arquitectónicas complejas encontradas durante el desarrollo de Iosef Finance.

## Aprendizajes Recientes
1. **Configuración de Entorno de FastAPI:** El modelo `Settings` de Pydantic requería la configuración `extra="ignore"` para poder procesar archivos `.env` que contengan variables no explícitamente declaradas en la clase (como variables de Redis).
2. **Arquitectura de WebSockets en Go:** El uso de Go para el servicio de *Realtime* en el puerto 8080 es una excelente decisión arquitectónica para descargar el procesamiento pesado de WebSockets fuera de Python, apoyándose en Redis como puente de comunicación (Patrón Pub/Sub).
