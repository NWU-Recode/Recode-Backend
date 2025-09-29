-- Create lecturers table and teaching_assignments table
-- Run this on your Postgres/Supabase database (psql or Supabase SQL editor).

-- Ensure pgcrypto (for gen_random_uuid) is available; if not, use uuid_generate_v4()
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.lecturers (
    profile_id integer PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.teaching_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    semester_id uuid NOT NULL REFERENCES public.semesters(id) ON DELETE CASCADE,
    module_id uuid NOT NULL REFERENCES public.modules(id) ON DELETE CASCADE,
    lecturer_profile_id integer NOT NULL REFERENCES public.lecturers(profile_id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT ta_unique_module UNIQUE (module_id),
    CONSTRAINT ta_unique_triple UNIQUE (semester_id, module_id, lecturer_profile_id)
);

-- Index to speed lookups by lecturer
CREATE INDEX IF NOT EXISTS idx_teaching_assignments_lecturer ON public.teaching_assignments (lecturer_profile_id);

-- Notes:
-- 1) If your Postgres doesn't have gen_random_uuid(), enable pgcrypto or replace with uuid_generate_v4().
-- 2) Apply this migration in the environment where your app's DB lives (Supabase SQL editor or psql).
