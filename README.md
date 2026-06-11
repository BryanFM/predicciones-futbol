# Hamster Fijas

App web para predicciones del Mundial 2026: doble oportunidad, más/menos goles, login con Google y roles admin/usuario.

| Entorno | URL |
|---------|-----|
| **Producción (Render)** | https://predicciones-futbol-tmyr.onrender.com/ |
| **Desarrollo local** | http://127.0.0.1:8000 |

## Stack

- Python 3 + FastAPI + Jinja2
- SQLAlchemy — SQLite (dev rápido) o PostgreSQL (como Render)
- Auth Google OAuth (Authlib)
- Deploy: [Render](https://render.com) (`render.yaml`)

---

## Desarrollo local (inicio rápido)

```bash
git clone https://github.com/BryanFM/predicciones-futbol.git
cd predicciones-futbol
make setup          # venv + dependencias + .env
```

Edita `.env` con tus credenciales (ver sección Google OAuth abajo).

```bash
make dev            # arranca en http://127.0.0.1:8000
```

### Comandos útiles

| Comando | Descripción |
|---------|-------------|
| `make setup` | Primera vez: venv, deps y `.env` |
| `make dev` | Servidor con SQLite + hot reload |
| `make db-up` | Levanta PostgreSQL en Docker |
| `make dev-postgres` | Dev con PostgreSQL (igual que Render) |
| `make db-reset` | Borra y recrea tablas + seed Mundial |
| `make db-down` | Para el contenedor PostgreSQL |

---

## Variables de entorno

Copia `.env.example` → `.env`:

```bash
cp .env.example .env
```

| Variable | Local | Render |
|----------|-------|--------|
| `DATABASE_URL` | *(vacío = SQLite)* | Auto desde `predicciones-db` |
| `SECRET_KEY` | cualquier string | Generado por Render |
| `HTTPS_ONLY` | `false` | `true` |
| `GOOGLE_CLIENT_ID` | tu client ID | mismo valor |
| `GOOGLE_CLIENT_SECRET` | tu secret | mismo valor |
| `ADMIN_EMAILS` | `tu@gmail.com` | mismo valor |
| `TWILIO_*` | opcional en dev | obligatorio en prod (SMS) |
| `ENVIRONMENT` | `development` | `production` (auto en Render) |
| `ENFORCE_UNIQUE_PHONE` | `false` en dev | `true` en prod (auto en Render) |

---

## Google OAuth

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth 2.0 Client
2. **Authorized redirect URIs** (añade las tres):

```
http://127.0.0.1:8000/auth/callback
http://localhost:8000/auth/callback
https://predicciones-futbol-tmyr.onrender.com/auth/callback
```

Cuando conectes **hamsterfijas.com**, añade también sus URIs (ver [docs/LANZAMIENTO.md](docs/LANZAMIENTO.md)).

3. Copia Client ID y Secret a `.env` (local) y al dashboard de Render (producción).

Los emails en `ADMIN_EMAILS` reciben rol **admin** al iniciar sesión (gestionar partidos, marcadores y categorías).

---

## PostgreSQL local (opcional, paridad con Render)

```bash
make db-up
```

En `.env`, descomenta:

```
DATABASE_URL=postgresql://predicciones:predicciones@localhost:5432/predicciones
```

```bash
make dev
# o en un solo paso:
make dev-postgres
```

Requiere [Docker Desktop](https://www.docker.com/products/docker-desktop/).

---

## Producción (Render)

**URL:** https://predicciones-futbol-tmyr.onrender.com/

El blueprint `render.yaml` define:

- Web service `predicciones-futbol` (Python 3.12, health check `/health`)
- PostgreSQL `predicciones-db`
- Variables automáticas: `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT=production`, `HTTPS_ONLY=true`, `SITE_URL` (URL de Render hasta conectar dominio propio)

Guía completa de dominio y checklist de lanzamiento: **[docs/LANZAMIENTO.md](docs/LANZAMIENTO.md)**.

### Variables a configurar en el dashboard de Render

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth Google |
| `GOOGLE_CLIENT_SECRET` | OAuth Google |
| `ADMIN_EMAILS` | Emails admin (coma) |
| `TWILIO_ACCOUNT_SID` | SMS verificación |
| `TWILIO_AUTH_TOKEN` | SMS verificación |
| `TWILIO_VERIFY_SERVICE_SID` | SMS verificación |

### Deploy

```bash
make verify-deploy    # comprueba que la app arranca en modo producción
git push origin master   # Render redeploya si auto-deploy está activo
```

Al arrancar, la app crea tablas, aplica migraciones y sincroniza el calendario del Mundial 2026.

---

## Funcionalidades

- Login con Google; predicciones por usuario
- **Admin**: categorías, partidos, marcadores
- **Usuario**: agregar/eliminar sus predicciones
- Doble oportunidad (1X, X2, 12) y más/menos goles
- Evaluación automática al registrar marcador
- Categoría **Mundial** con jornada 1 del Mundial 2026 (seed)
- Página `/proximamente` — sistema de puntos
