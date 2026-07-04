-- =============================================================
-- MDH Stoma Care Clinic — Encounters backend (v92)
-- Run this once in Supabase: SQL Editor -> New query -> paste -> Run
-- =============================================================

-- One table for all clinical encounters. The type column says which
-- form produced the row; the data column holds the full structured form.
create table if not exists encounters (
  id uuid primary key default gen_random_uuid(),
  patient_id uuid not null,
  appointment_id uuid,
  encounter_type text not null,          -- daily_stoma_review, wound_review, fistula_review,
                                         -- phone_advice, teaching_session, discharge_planning,
                                         -- general_note, stoma_review, followup_review, postop_daily_review
  encounter_date date not null,
  encounter_time text,
  recorded_by text,
  data jsonb not null default '{}',      -- full structured form payload
  summary text,                          -- human-readable block (same text as patients.findings)
  created_at timestamptz not null default now()
);

create index if not exists encounters_patient_idx on encounters (patient_id, encounter_date desc);
create index if not exists encounters_type_idx on encounters (encounter_type);

-- Row level security: any signed-in clinic user can read/insert.
alter table encounters enable row level security;

drop policy if exists "encounters_select_authenticated" on encounters;
create policy "encounters_select_authenticated"
  on encounters for select to authenticated using (true);

drop policy if exists "encounters_insert_authenticated" on encounters;
create policy "encounters_insert_authenticated"
  on encounters for insert to authenticated with check (true);
