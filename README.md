# El Descentralizador

*Noticias de todo Chile (menos Santiago)*

Agregador de medios regionales chilenos y municipalidades. API REST y
portada HTML, con filtros por región, tipo de fuente, medio, fecha y
palabras clave. La Región Metropolitana queda explícitamente fuera del
catálogo.

## Stack

Python 3.14, Litestar 2.24, Advanced Alchemy, PostgreSQL (`tsvector`),
SAQ + Redis/Valkey, Jinja, Granian.

## Correr con Docker

```bash
cp .env.example .env.docker   # ya existe un .env.docker de desarrollo
docker compose up --build
# → http://localhost:8000
```

Admin por defecto: `admin` / `admin` (cambiar `ADMIN_PASSWORD`).

## Correr en local

```bash
uv sync --extra dev
docker compose up db cache -d
alembic upgrade head
export $(grep -v '^#' .env.example | xargs)
litestar --app el_descentralizador.server.asgi:create_app run
```

Workers de ingesta (producción):

```bash
litestar --app el_descentralizador.server.asgi:create_app workers run
```

La ingesta también corre cada hora vía cron SAQ.

## API

OpenAPI: `/schema`

- `GET /api/v1/filters` — regiones, fuentes y rango de fechas
- `GET /api/v1/articles` — listado paginado (`limit`/`offset`), una fila por grupo de duplicados. Query: `region`, `kind`, `sourceId`, `q`, `from`, `to`
- `GET /api/v1/articles/{id}` — artículo con cuerpo cacheado
- `POST /api/v1/auth/login` — sesión cookie
- `POST /api/v1/ingestion-jobs` — encola ingesta (admin)
- `GET /api/v1/ingestion-jobs/current` — progreso (admin)
- `GET /api/v1/sources` — catálogo + curación (admin)
- `GET /api/v1/sources/{id}/sample` — últimas 10 entradas del feed (admin)
- `PATCH /api/v1/sources/{id}/curation` — clasificar fuente (admin)
- `DELETE /api/v1/sources/{id}/curation` — volver a pendiente (admin)

Páginas: `/`, `/login`, `/curator/media`, `/curator/municipalities`.

## Copyright

El lector muestra el cuerpo completo solo de municipalidades (información
pública). Para medios de prensa muestra los 3 primeros párrafos y un
enlace al original (Art. 71, Ley 17.336).

## Licencia

MIT. Las noticias enlazadas son propiedad de sus respectivos medios.
