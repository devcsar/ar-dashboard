-- Migración: attr_segmento
-- Guarda por qué una fila de Airmeet cuenta o no como registro real, para mostrar el total completo.
alter table attr_registrations add column if not exists segmento text
  check (segmento in ('registered','speaker','pending','other'));
-- Relleno inicial; el siguiente sync lo refina (speaker / pending / other).
update attr_registrations set segmento = case when es_real then 'registered' else 'other' end where segmento is null;

create or replace view attr_segment_summary with (security_invoker = true) as
select coalesce(segmento, 'other') as segmento, count(*) as n
from attr_registrations group by 1;
