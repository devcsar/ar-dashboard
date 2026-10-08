# ar-dashboard

Dashboard de atribución por UTM para Airflow Summit 2026 Online Reconnect (4 y 5 de nov de 2026).
Meta: 3,000 registros. Muestra solo números agregados, nunca personas.

Estructura: `scripts/` (sync con Airmeet), `.github/workflows/` (Action), `docs/` (dashboard en GitHub Pages),
`sql/` (migraciones y inventario), `supabase/functions/` (edge functions de login y datos).

Las llaves viven solo en GitHub Secrets y en `supabase secrets`; nunca en este repo.

## Secrets

GitHub (`gh secret set`): `AIRMEET_ACCESS_KEY`, `AIRMEET_SECRET_KEY`, `AIRMEET_REGION_URL`, `AIRMEET_EVENT_ID`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `HASH_SALT`.

Supabase edge functions (`supabase secrets set`): `DASH_PASSWORD`, `DASH_TOKEN_SECRET`.
Opcional: `ALLOWED_ORIGIN` (por defecto `https://devcsar.github.io`).

## Flujo

`sync.yml` corre cada hora (cada 15 min del 28 de oct al 6 de nov) y llama a `scripts/sync_airmeet.py`,
que une todo por HMAC del email (sin guardar emails) y escribe en las tablas `attr_*`.
El dashboard (`docs/index.html`) pide un token a `dashboard-login` y los agregados a `dashboard-data`.
