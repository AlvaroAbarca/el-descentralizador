# Migración a Litestar + Postgres

Documento de lo implementado al reemplazar Flask + SQLite por Litestar 2.24, Advanced Alchemy, PostgreSQL, SessionAuth, SAQ y Docker Compose. No se migraron datos de `noticias.db`.

Fecha de referencia: 2026-08-12.

---

## Objetivo

Reescribir **El Descentralizador** (agregador de noticias regionales chilenas, sin Santiago) como aplicación Litestar de dominio bajo `src/el_descentralizador/`, con:

- API REST en inglés (`/api/v1/...`)
- Páginas Jinja + HTMX
- Un solo admin con cookie de sesión
- Ingesta asíncrona en cola SAQ (Redis/Valkey)
- Postgres con búsqueda full-text (`tsvector` español + GIN)

---

## Decisiones cerradas

| Tema | Decisión |
|------|----------|
| Flask | Reemplazo total (API + HTML) |
| Catálogo | CSV → tabla `source`, seed inicial |
| Búsqueda | `tsvector` español + índice GIN |
| Auth | Cookie de sesión; un admin; portada/listado/lector públicos |
| Ingesta | SAQ + Redis; job consultable; ciega a curación |
| PKs | UUID v7 (sin importar SQLite) |
| Layout | Dominios bajo `src/el_descentralizador/` |
| Runtime | Python 3.14 + Docker Compose |
| Rutas | Contrato nuevo en inglés; sin aliases Flask |

---

## Arquitectura

```text
Browser → App (Litestar / Granian :8000)
              ├→ Postgres 16
              └→ Valkey/Redis (sesiones + cola SAQ)
Worker (litestar workers run) → Postgres + Redis
Migrator (alembic upgrade head) → Postgres
```

Compose: `db`, `cache`, `migrator`, `app`, `worker`.

---

## Layout del paquete

```text
src/el_descentralizador/
  domain/
    articles/      API pública: filters, list, detail
    sources/       catálogo + curación (admin)
    ingestion/     pipeline, SAQ job, scrapers, lector
    accounts/      User, SessionAuth, login, guards
    web/           páginas Jinja + fragmentos HTMX
  db/models/       User, Source, Article
  db/migrations/   Alembic (Advanced Alchemy)
  lib/             settings, exceptions, msgspec, DI helpers
  server/          asgi.py, plugins.py, routers.py, seed.py, templates/
  data/            medios_rss_actualizado.csv (seed empaquetado)
scripts/           descubrir_feeds.py, descubrir_municipalidades.py
tests/             AsyncTestClient + unitarios
docker-compose.yml
Dockerfile
alembic.ini
```

App factory: `el_descentralizador.server.asgi:create_app`  
CLI: `LITESTAR_APP=el_descentralizador.server.asgi:create_app`

---

## Modelos Postgres (`UUIDv7AuditBase`)

IDs UUID v7 (ordenables por tiempo). `created_at` / `updated_at` del mixin. Migración inicial: `20260812_0001`.

### User (`user_account`)

- `username` unique
- `password` (`PasswordHash` / Argon2)
- `is_active`
- Un admin seed desde `ADMIN_USERNAME` / `ADMIN_PASSWORD`

### Source (`source`)

- `name` unique, `region`, `url`, `feed_url` nullable
- `kind`: `media` | `municipality`
- `has_rss`, `site_live`, `is_active`
- Curación en la misma fila:
  - `curation_status` nullable: `approved` | `fix` | `discarded` (`NULL` = pendiente)
  - `curation_comment`, `curated_at`
- `kind` al seed: prefijo `Municipalidad de ` → municipality

### Article (`article`)

- FK `source_id` → Source
- `title`, `url` unique, `published_at` (`DateTimeUTC`)
- `summary`, `image_url`, `body_html` (cache del lector)
- `title_norm` (dedupe), `region`
- `group_id` self-FK (canónico del grupo de duplicados)
- `search_vector` generado (`spanish`, peso A título / B resumen) + GIN

Seed en lifespan: admin + CSV si la tabla `source` está vacía (~203 filas del catálogo).

---

## API REST `/api/v1` (msgspec, camelCase)

OpenAPI: `/schema`.

### Público

| Método | Ruta | Notas |
|--------|------|--------|
| GET | `/api/v1/filters` | regiones N→S, sources con conteo, rango de fechas |
| GET | `/api/v1/articles` | `region`, `kind`, `sourceId`, `q`, `from`, `to`; limit/offset (24); una fila por `group_id`; `alsoIn[]` |
| GET | `/api/v1/articles/{id}` | cuerpo cacheado; si `bodyHtml` es null, extrae y persiste |
| GET | `/health` | `{ "status": "ok" }` |

### Admin (`requires_admin` + SessionAuth)

| Método | Ruta | Notas |
|--------|------|--------|
| POST | `/api/v1/auth/login` | cookie de sesión |
| POST | `/api/v1/auth/logout` | |
| GET | `/api/v1/auth/me` | |
| POST | `/api/v1/ingestion-jobs` | enqueue SAQ `key=ingest-run`; 202; 409 si ya corre |
| GET | `/api/v1/ingestion-jobs/current` | fase, done/total, error, resultado |
| GET | `/api/v1/sources?kind=` | catálogo + curación |
| GET | `/api/v1/sources/{id}/sample` | últimas 10 del feed; 502 si falla |
| PATCH | `/api/v1/sources/{id}/curation` | `{ status, comment? }` |
| DELETE | `/api/v1/sources/{id}/curation` | vuelve a pendiente |

---

## Páginas HTML

| Ruta | Acceso |
|------|--------|
| `GET /` | pública (portada) |
| `GET /login`, `POST /login`, `POST /logout` | login cookie |
| `GET /curator/media`, `GET /curator/municipalities` | admin |

Fragmentos HTMX:

- `GET /partials/articles` — lista/paginación
- `GET /partials/curator/{kind}` — tarjeta de curador
- `PATCH /partials/sources/{id}/curation` — clasificar
- `GET /partials/sources/{id}/sample` — muestra de feed

El lector sigue pidiendo `GET /api/v1/articles/{id}`. Copyright: cuerpo completo solo municipalidades; medios = 3 párrafos + enlace al original (en plantilla, no en el JSON).

Sin sesión el visitante no ve curador ni “Actualizar edición”; `REPO_URL` sigue en la cinta.

---

## Auth

- `SessionAuth` + store Redis (`sessions`)
- Middleware opcional: sin sesión → `user=None` (rutas públicas); con sesión → `request.user`
- Cookie httpOnly; `SECRET_KEY` en settings
- Guard `requires_admin`: HTML Accept → 302 `/login`; API → 401
- `MODO_PUBLICO` / `ADMIN_TOKEN` del Flask antiguo ya no aplican

---

## Ingesta (SAQ + Redis)

Lógica portada desde `ingestar.py` / `lector.py` / `scrapers.py` a `domain/ingestion/`:

- Fuentes desde tabla `source` (`has_rss` o scraper), **sin filtrar por curación**
- Cola Redis `ingestion`; task `run_ingest` (timeout ~600 s, heartbeat, `monitored_job`)
- Progreso en Redis clave `ingest:current`
- Cron SAQ cada 60 min (`0 * * * *`)
- Compose: `worker` con `litestar workers run` y `SAQ_USE_SERVER_LIFESPAN=false`
- Local: `SAQ_USE_SERVER_LIFESPAN=true` posible para un solo proceso

Scripts CLI de descubrimiento quedan en `scripts/` (fuera del corte HTTP).

---

## Settings y plugins

`lib/settings.py` (dataclass + `get_env`):

- `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`
- `REPO_URL`, `CATALOG_CSV`, `APP_DEBUG`, flags SAQ

Plugins en `server/plugins.py`:

- `SQLAlchemyPlugin` (singleton config; keys `alchemy_engine` / `alchemy_session_maker`)
- `SAQPlugin`
- `GranianPlugin`
- `HTMXPlugin`
- TemplateConfig Jinja (`server/templates/`)

Seed: `server/seed.py` usa `alchemy_config()` (el plugin expone `config` como lista).

---

## Docker

- `Dockerfile`: multi-stage, `PYTHON_VERSION=3.14`, `uv`, non-root, `litestar run :8000`
- `docker-compose.yml`: Postgres 16, Valkey, migrator (`alembic upgrade head`), app, worker
- Healthcheck HTTP en `app` → `/health`
- `.env.docker` / `.env.example`

```bash
docker compose up --build
# → http://localhost:8000
```

Admin por defecto: `admin` / `admin` (cambiar `ADMIN_PASSWORD`).

---

## Qué se eliminó

- `app.py`, `basedatos.py`, `ingestar.py`, `lector.py`, `scrapers.py` (raíz)
- Flask y `requirements.txt` como fuente de verdad
- Dependencia de `noticias.db` en runtime
- Gate `MODO_PUBLICO` / token admin en query

El CSV permanece solo como seed (`medios_rss_actualizado.csv` + copia empaquetada en `src/.../data/`).

---

## Tests

`pytest` + `AsyncTestClient` (app slim con MemoryStore y fakes DI; no levanta Redis/Postgres en el camino feliz).

Cobertura aproximada:

- `/health`, portada, login HTML
- filters / articles list+detail públicos (camelCase)
- fragmento HTMX `/partials/articles`
- 401/403 en ingest y sources sin sesión
- login cookie / credenciales inválidas
- enqueue 202 y 409 (dedup `ingest-run`)
- seed CSV (kind municipality)
- FTS `tsvector`: skip si no hay `DATABASE_URL` postgres

Última corrida local de referencia: **18 passed, 1 skipped**.

```bash
uv sync --extra dev
pytest tests -q
```

---

## Dependencias (`pyproject.toml`)

`requires-python = ">=3.14"`

Principales: `litestar[standard]`, `advanced-alchemy`, `litestar-saq[hiredis]`, `litestar-htmx`, `litestar-granian`, `asyncpg`, `msgspec`, `httpx`, `feedparser`, `beautifulsoup4`, `argon2-cffi`, `redis`, `jinja2`.

Dev: `pytest`, `anyio`, `ruff`, `fakeredis`, `pytest-databases`, etc.

---

## Detalles técnicos relevantes

1. **SessionAuth público**: middleware custom que no exige sesión en todas las rutas; solo popula `user` cuando hay cookie válida.
2. **DI en tests**: `Injected = Annotated[T, Dependency(skip_validation=True)]` para poder stubbear services sin tipado ORM.
3. **SQLAlchemy config singleton**: evita sufijos `_1` en app state al crear el plugin más de una vez.
4. **Wire format**: msgspec `CamelizedBaseStruct` (snake_case en Python, camelCase en JSON).
5. **Extracción de cuerpo**: sync `httpx`/`bs4` envuelta en `asyncio.to_thread` desde handlers async.
6. **Progreso de ingesta**: campos `phase`, `done`, `total`, `started_at` (el front espera camel/inglés, no `fase`/`hechos`).

---

## Cómo correr en local (sin Compose completo)

```bash
uv sync --extra dev
docker compose up db cache -d
alembic upgrade head
# cargar vars de .env.example
litestar --app el_descentralizador.server.asgi:create_app run
# worker aparte:
litestar --app el_descentralizador.server.asgi:create_app workers run
```

---

## Checklist del plan (estado)

- [x] Scaffold uv/pyproject, settings, asgi, plugins, layout de dominios
- [x] Modelos UUIDv7 + Alembic + seed CSV
- [x] API pública `/api/v1` (filters, articles, FTS, group_id)
- [x] SessionAuth Redis, User seed, login/logout, guards
- [x] API admin sources + sample + PATCH/DELETE curation
- [x] Pipeline async + SAQ + progreso + cron 60m
- [x] Templates Jinja + JS `/api/v1` + fragmentos HTMX
- [x] Docker Compose + Dockerfile 3.14 + `/health`
- [x] Tests AsyncTestClient (público, auth, jobs, seed; FTS condicional)
