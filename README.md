# ar-dashboard

Dashboard de atribución por UTM para Airflow Summit 2026 Online Reconnect (4 y 5 de nov de 2026).
Meta: 3,000 registros. Muestra solo números agregados, nunca personas.

Estructura: `scripts/` (sync con Airmeet), `.github/workflows/` (Action), `docs/` (dashboard en GitHub Pages),
`sql/` (migraciones y inventario), `supabase/functions/` (edge functions de login y datos).

Las llaves viven solo en GitHub Secrets y en `supabase secrets`; nunca en este repo.
