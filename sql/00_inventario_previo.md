# Inventario previo del proyecto Supabase `airflow-summit` (2026-10-08)

Solo se agrega; nada de esto se toca. Todo lo nuevo lleva prefijo `attr_`.

- Tablas (public): `attendees` (RLS on, 0 filas, policy `anon_insert_attendees`)
- Vistas: ninguna
- Funciones (public): ninguna
- Edge functions: ninguna
- Migraciones: `20260830172736 create_attendees_insert_only`, `20260904214155 drop_email_unique_add_ticket_ref`
- Objetos `attr_*` existentes: ninguno
