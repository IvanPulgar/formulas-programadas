# Queue Theory Formula Engine

Aplicación web local para teoría de colas con arquitectura modular y un motor de fórmulas basado en Python.

## Requisitos
- Python 3.11+ recomendado
- Windows / macOS / Linux

## Instalación
```powershell
cd "c:\Users\Hp\Desktop\octavo\octavo\tecnicasp simulacion\formulas programadas"
# Si el comando python no funciona en Windows, use py -3
py -3 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución local
```powershell
.\.venv\Scripts\activate
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000` en tu navegador.

## Rutas disponibles
- `GET /` - página base con plantilla Jinja2
- `GET /health` - ruta de salud

## Pruebas
```powershell
.\.venv\Scripts\activate
pytest
```

## Arquitectura y responsabilidades
- `app/` - punto de entrada FastAPI, configuración de la aplicación y montaje de rutas y archivos estáticos.
- `domain/` - lógica de dominio del motor de fórmulas:
  - `entities/` para objetos del dominio y valores principales
  - `services/` para orquestación y procesos de negocio
  - `rules/` para reglas de selección, validación y coincidencia
- `infrastructure/` - adaptadores y transformaciones de entrada/salida:
  - `repositories/` para acceso a datos persistidos o cachés futuros
  - `parsers/` para normalización y validación de datos crudos
- `presentation/` - capa de presentación y transporte:
  - `routes/` para definiciones de rutas FastAPI
  - `schemas/` para modelos Pydantic y contratos de API
  - `templates/` para vistas Jinja2
  - `static/` para recursos estáticos como CSS o JS
- `tests/` - pruebas de la aplicación:
  - `unit/` para pruebas de lógica aislada
  - `integration/` para pruebas de rutas y flujo completo

## Notas
- Las fórmulas se implementarán en código Python dentro de módulos específicos de categoría.
- SymPy sólo se usará cuando sea necesario para despejar variables o validar expresiones complejas.
