-- READ-ONLY catalog inspection. No INSERT/UPDATE/DELETE, no client row export.
-- Run in the demo database, then inspect the result privately before sharing.
-- Function bodies/defaults can themselves contain hardcoded secrets: audit them.
with target_tables as (
  select c.oid, n.nspname as schema_name, c.relname as table_name
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind in ('r', 'p')
    and c.relname in ('leads', 'appointments', 'availability_rules',
                      'handoff_sessions', 'conversation_messages')
), columns_data as (
  select jsonb_agg(jsonb_build_object(
    'table', t.table_name, 'column', a.attname,
    'type', format_type(a.atttypid, a.atttypmod),
    'not_null', a.attnotnull,
    'default', pg_get_expr(d.adbin, d.adrelid),
    'identity', a.attidentity, 'generated', a.attgenerated
  ) order by t.table_name, a.attnum) as value
  from target_tables t join pg_attribute a on a.attrelid = t.oid
  left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
  where a.attnum > 0 and not a.attisdropped
), constraints_data as (
  select jsonb_agg(jsonb_build_object(
    'table', t.table_name, 'name', c.conname,
    'definition', pg_get_constraintdef(c.oid, true)
  ) order by t.table_name, c.conname) as value
  from target_tables t join pg_constraint c on c.conrelid = t.oid
), indexes_data as (
  select jsonb_agg(jsonb_build_object(
    'table', t.table_name, 'definition', pg_get_indexdef(i.indexrelid)
  ) order by t.table_name, i.indexrelid) as value
  from target_tables t join pg_index i on i.indrelid = t.oid
), functions_data as (
  select jsonb_agg(jsonb_build_object(
    'name', p.proname,
    'identity_arguments', pg_get_function_identity_arguments(p.oid),
    'definition', pg_get_functiondef(p.oid)
  ) order by p.proname, p.oid) as value
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public' and p.prokind = 'f'
    and (p.proname in ('get_available_slots', 'book_appointment',
      'reschedule_appointment', 'cancel_appointment', 'start_reschedule',
      'set_appointment_outcome')
      or p.oid in (
        select tr.tgfoid from pg_trigger tr join target_tables t on t.oid = tr.tgrelid
        where not tr.tgisinternal
      ))
), triggers_data as (
  select jsonb_agg(jsonb_build_object(
    'table', t.table_name, 'definition', pg_get_triggerdef(tr.oid, true)
  ) order by t.table_name, tr.tgname) as value
  from target_tables t join pg_trigger tr on tr.tgrelid = t.oid
  where not tr.tgisinternal
)
select jsonb_build_object(
  'columns', coalesce((select value from columns_data), '[]'::jsonb),
  'constraints', coalesce((select value from constraints_data), '[]'::jsonb),
  'indexes', coalesce((select value from indexes_data), '[]'::jsonb),
  'functions', coalesce((select value from functions_data), '[]'::jsonb),
  'triggers', coalesce((select value from triggers_data), '[]'::jsonb)
) as structure_only;
-- This is not a full pg_dump: grants, RLS, extensions and seed availability rules
-- are deliberately not exported. Dependent helper functions may need a review.
