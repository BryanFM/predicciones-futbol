# Predicciones Fútbol

Aplicación web para registrar partidos, predicciones (doble oportunidad y más/menos goles) y llevar control de aciertos.

## Stack

- **Python 3** + **FastAPI**
- **SQLite** + **SQLAlchemy**
- Interfaz web con **Jinja2** (sin Node.js)

## Requisitos

- Python 3.10 o superior

## Instalación

```bash
cd ~/Projects/predicciones-futbol
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar

```bash
uvicorn app.main:app --reload
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Funcionalidades

- **Categorías**: crea torneos/ligas (viene pre-cargada "Mundial")
- **Partidos**: CRUD con equipos, fecha, grupo y sede
- **Marcador**: al guardar el resultado, las predicciones se evalúan automáticamente
- **Predicciones**:
  - Doble oportunidad: 1X, X2, 12
  - Más/Menos goles: líneas 1.5, 2.5, 3.5, 4.5
- **Resultado manual**: puedes marcar acertada/fallida/pendiente
- **Estadísticas**: total, aciertos, fallos y efectividad

## Datos iniciales

La categoría **Mundial** incluye los 24 partidos de la **jornada 1** de la fase de grupos del Mundial 2026 (fixture oficial FIFA).
