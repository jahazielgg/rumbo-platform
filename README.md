# Rumbo — MVP 0.3

Rumbo es un MVP para construir y configurar mapas indoor a partir de planos de una clínica. El repositorio está separado explícitamente en dos aplicaciones:

```text
rumbo/
├── rumbo-web-app/       # Frontend React
├── rumbo-api/           # Backend FastAPI
├── structural-mapper/   # Servicio de Structural Mapping (percepción + geometría + grafo)
├── docs/
├── samples/
└── docker-compose.yml
```

## Alcance funcional

| ID | Funcionalidad | Estado |
|---|---|---|
| F01 | Carga y gestión de planos PDF/PNG/JPG/SVG por edificio y piso | ✅ |
| F02 | Escala, paredes, nodos, puntos de atención y conexiones entre nodos | ✅ |
| F03 | Ascensores, escaleras y rampas entre pisos | ✅ |
| F04 | Puntos QR asociados a nodos del mapa | ✅ |
| F05 | Structural Mapping automático: paredes, puertas, espacios, circulación y grafo validado (V3) | ✅ |

## Aplicaciones

### `rumbo-web-app`

- React + TypeScript
- Vite
- React Router
- Editor SVG 2D
- Consume exclusivamente la API HTTP de `rumbo-api`

La organización visual del sidebar es una decisión de experiencia de usuario y no representa bounded contexts del backend.

### `structural-mapper`

- Python + FastAPI, sin dependencia de PyTorch para la parte geométrica
- Ingesta vectorial (PDF/SVG con PyMuPDF) y raster
- Percepción: trazos vectoriales, morfología clásica y BuildingCV multi-escala (opcional)
- Reconstrucción, inferencia de espacios, espacio transitable, grafo semántico y validación
- Ver `docs/structural-mapping-v3.md`

Tests sin ML:

```bash
cd structural-mapper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-geometry.txt
pytest -q
```

### `rumbo-api`

- Python + FastAPI
- Monolito modular
- Domain-Driven Design
- SQLAlchemy 2
- PostgreSQL + PostGIS
- Alembic
- PyMuPDF para preview de PDF
- Storage local detrás de un port/adapter

## Bounded contexts del backend

No existe una división `Core/Sources` en el backend. Los contextos están al mismo nivel y se nombran según el lenguaje del dominio:

```text
rumbo-api/app/
├── floorplans/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
├── modeling/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
├── navigation/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
├── positioning/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
├── shared_kernel/
├── infrastructure/
└── main.py
```

### Responsabilidades

- `floorplans`: archivo fuente, edificio, piso y preview.
- `modeling`: escala, geometría, nodos y puntos de atención.
- `navigation`: conexiones del grafo y conectores verticales.
- `positioning`: anchors QR asociados a nodos.
- `shared_kernel`: conceptos mínimos realmente compartidos.
- `infrastructure`: configuración y acceso técnico transversal a la base de datos.

## Regla de dependencias DDD

Dentro de cada bounded context:

```text
presentation ──► application ──► domain
                     ▲
                     │
infrastructure ──────┘
```

El dominio no conoce FastAPI, SQLAlchemy ni detalles de persistencia.

## Ejecutar con Docker

```bash
docker compose up --build
```

- Web: `http://localhost:5173`
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Ejecutar manualmente

### API

```bash
cd rumbo-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Web

```bash
cd rumbo-web-app
npm install
npm run dev
```

## Flujo MVP

1. **Planos**: subir Piso 1 y Piso 2.
2. **Modelado**: calibrar una medida conocida.
3. Crear nodos sobre pasillos e intersecciones.
4. Crear puntos de atención y asociarlos a nodos.
5. Crear conexiones entre nodos.
6. Crear ascensores, escaleras o rampas entre pisos.
7. Crear puntos QR y asociarlos a nodos.
8. Guardar configuración.

## API

```text
/api/v1/floorplans/{id}
/api/v1/floorplans/{id}/preview
/api/v1/modeling/{floorplan_id}
/api/v1/navigation/{floorplan_id}
/api/v1/positioning/{floorplan_id}
```

El siguiente incremento recomendado es `Routing`, como consumidor de los modelos publicados por `modeling` y `navigation`, sin apropiarse de esos datos.
