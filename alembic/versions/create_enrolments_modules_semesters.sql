-- Migration: create enrolments, modules, semesters, lecturers
-- This SQL creates the minimal tables required for enrolments, modules, semesters and lecturers.

create table public.enrolments (
  id uuid not null default gen_random_uuid (),
  semester_id uuid not null,
  student_id integer not null,
  module_id uuid not null,
  enrolled_on timestamp with time zone not null default now(),
  status text not null default 'active'::text,
  constraint enrolments_pkey primary key (id),
  constraint enrolments_student_id_module_id_key unique (student_id, module_id),
  constraint enrolments_module_id_fkey foreign KEY (module_id) references modules (id),
  constraint enrolments_semester_id_fkey foreign KEY (semester_id) references semesters (id),
  constraint enrolments_student_id_fkey foreign KEY (student_id) references profiles (id) on update CASCADE on delete RESTRICT,
  constraint enrolments_status_check check (
    (
      status = any (
        array[
          'active'::text,
          'withdrawn'::text,
          'completed'::text
        ]
      )
    )
  )
);

create index IF not exists idx_enrolments_student_id on public.enrolments using btree (student_id);
create index IF not exists idx_enrolments_module_id on public.enrolments using btree (module_id);
create index IF not exists idx_enrolments_semester_id on public.enrolments using btree (semester_id);
create index IF not exists idx_enrolments_status on public.enrolments using btree (status);
create index IF not exists idx_enrolments_student_active on public.enrolments using btree (student_id, status) where (status = 'active'::text);

create table public.lecturers (
  profile_id integer not null,
  department character varying null,
  faculty character varying null,
  specialization text null,
  office_location character varying null,
  consultation_hours character varying null,
  constraint lecturers_pkey primary key (profile_id),
  constraint lecturers_profile_id_fkey foreign KEY (profile_id) references profiles (id) on update CASCADE on delete CASCADE
);

create table public.modules (
  id uuid not null default gen_random_uuid (),
  code text not null,
  name text not null,
  description text not null,
  semester_id uuid not null,
  lecturer_id integer not null,
  code_language character varying(50) null,
  credits smallint null default 8,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint modules_pkey primary key (id),
  constraint modules_code_key unique (code),
  constraint modules_lecturer_id_fkey foreign KEY (lecturer_id) references profiles (id) on update CASCADE on delete RESTRICT,
  constraint modules_semester_id_fkey foreign KEY (semester_id) references semesters (id) on update CASCADE on delete RESTRICT,
  constraint modules_code_check check ((code ~ '^[A-Z]{4}[0-9]{3}$'::text))
);

create index IF not exists idx_modules_semester_id on public.modules using btree (semester_id);
create index IF not exists idx_modules_lecturer_id on public.modules using btree (lecturer_id);

create table public.semesters (
  id uuid not null default gen_random_uuid (),
  year integer not null,
  term_name text not null default 'Semester 1'::text,
  start_date date not null,
  end_date date not null,
  is_current boolean not null default false,
  created_at timestamp without time zone not null default now(),
  updated_at timestamp without time zone null default now(),
  constraint semesters_pkey primary key (id),
  constraint semesters_check check ((end_date > start_date)),
  constraint semesters_term_name_check check ((term_name = any (array['Semester 1'::text, 'Semester 2'::text]))),
  constraint semesters_year_check check (((year >= 2025) and (year <= 2100)))
);

create index IF not exists idx_semesters_is_current on public.semesters using btree (is_current);
create index IF not exists idx_semesters_year_term on public.semesters using btree (year, term_name);

-- Note: this migration expects pgcrypto (gen_random_uuid) or uuid-ossp; adjust as needed.
