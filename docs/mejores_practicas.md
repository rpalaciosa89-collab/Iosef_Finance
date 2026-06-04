# Mejores Prácticas y Estándares (Iosef Finance)

Este documento rige las leyes absolutas de desarrollo, arquitectura y despliegue dictadas por la dirección. 

## 1. Ingeniería Financiera y Machine Learning (Regla de Carlos)
- **Precisión de Francotirador:** Prohibido el uso de modelos "caja negra" sin justificación estadística. Todo modelo debe mostrar sus métricas de varianza, sesgo y significancia.
- **Realismo Estadístico:** "Cero poesía". Se requiere estadística aplicada pura. Si una señal no tiene esperanza matemática positiva tras costos de transacción, se descarta. 
- **Ausencia de Sesgos:** Se auditará rigurosamente todo backtest para asegurar que no exista *look-ahead bias* (sesgo de información futura) ni *survivorship bias*.

## 2. Desarrollo e Infraestructura (Regla de Javier)
- **Clean Architecture:** Separación estricta de responsabilidades. Controladores (APIs), Casos de Uso (Servicios) y Persistencia (Repositorios) no deben acoplarse.
- **Rendimiento Máximo:** Iosef Finance es una plataforma de alta frecuencia. El código no debe bloquear el *Event Loop* en Python ni asfixiar las Goroutines en Go. Todo I/O debe ser asíncrono.
- **Código Legible:** El código se lee 10 veces más de lo que se escribe. Nomenclatura descriptiva obligatoria.

## 3. Calidad y Ciberseguridad (Regla de Luis)
- **Tests Obligatorios:** Ningún algoritmo cuantitativo de Carlos ni *endpoint* de Javier entra a `main` sin pruebas unitarias (`pytest` o `go test`).
- **Secretos:** Nunca se suben credenciales ni `.env` al repositorio. Se usa manejo de variables de entorno estricto con validación (pydantic).
- **Inyección y XSS:** Validación estricta de todos los *inputs* del cliente web.
