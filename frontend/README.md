# Iosef_Finance - Frontend (Web-First Client)

Este directorio contendrá el cliente web de alto rendimiento para interactuar con la API financiera de **Iosef_Finance**.

## Enfoque de Diseño

1. **Alineación con Finviz**: Una vista tabular compacta pero extremadamente densa y responsiva (Stock Screener).
2. **Estética Premium**: 
   - Estilo moderno con soporte nativo de modo oscuro (Glassmorphism, sombras suaves, y efectos translúcidos).
   - Paleta de colores armoniosa en HSL (tonalidades de gris pizarra, verde esmeralda para subidas y rojo coral para bajadas).
   - Tipografía moderna (ej. `Inter` u `Outfit` desde Google Fonts).
3. **Optimización de Rendimiento**:
   - Renderizado rápido de tablas masivas usando paginación virtualizada.
   - Micro-animaciones interactivas en botones y filas para una experiencia premium.

## Estructura Recomendada

Una vez inicializado (ej. usando Vite + React + TypeScript), la estructura recomendada es:

```text
frontend/
├─ public/
├─ src/
│  ├─ assets/         # Logotipos y recursos visuales
│  ├─ components/     # Componentes visuales reutilizables (Tablas, Buscadores)
│  ├─ context/        # Estados globales (ej. filtros seleccionados)
│  ├─ services/       # Clientes HTTP (llamadas a la API del Backend)
│  ├─ styles/         # CSS Vanilla con variables CSS personalizadas (Diseño Moderno)
│  ├─ App.tsx
│  └─ main.tsx
├─ package.json
└─ vite.config.ts
```

## Configuración Sugerida de Desarrollo

Para inicializar un proyecto Vite + React:

```bash
# En el directorio Iosef_Finance/frontend
npx -y create-vite@latest ./ --template react-ts
npm install
npm run dev
```
