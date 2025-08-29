-- Recode MVP Supabase schema (idempotent where possible)
-- Topics, Challenges extras, Question tests, Questions.valid, Attempts

-- 1) Enums
do $$
begin
  if not exists (select 1 from pg_type where typname = 'challengekind') then
    create type challengekind as enum ('common','ruby','platinum','diamond');
  end if;
  if not exists (select 1 from pg_type where typname = 'challengestatus') then
    create type challengestatus as enum ('draft','published');
  end if;
  if not exists (select 1 from pg_type where typname = 'challengetier') then
    create type challengetier as enum ('plain','ruby','emerald','diamond');
  end if;
  if not exists (select 1 from pg_type where typname = 'questiontestvisibility') then
    create type questiontestvisibility as enum ('public','hidden');
  end if;
end$$;

-- 2) Topics (plural – used by TopicRepository)
create table if not exists public.topics (
  id serial primary key,
  week int not null,
  slug text not null unique,
  title text not null,
  subtopics jsonb null,
  created_at timestamptz not null default now()
);
create index if not exists ix_topics_week on public.topics(week);

-- 3) Challenges extras
alter table public.challenges
  add column if not exists slug text,
  add column if not exists kind challengekind,
  add column if not exists status challengestatus,
  add column if not exists topic_id int,
  add column if not exists tier challengetier,
  add column if not exists sequence_index int;

create unique index if not exists ix_challenges_slug on public.challenges(slug);
create index if not exists ix_challenges_tier on public.challenges(tier);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.challenges'::regclass
      and conname = 'challenges_topic_id_fkey'
  ) then
    alter table public.challenges
      add constraint challenges_topic_id_fkey
      foreign key (topic_id) references public.topics(id) on delete set null;
  end if;
end$$;

-- 4) Questions.valid flag
alter table public.questions
  add column if not exists valid boolean not null default false;

-- 5) Question tests
create table if not exists public.question_tests (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions(id) on delete cascade,
  input text not null,
  expected text not null,
  visibility questiontestvisibility not null,
  created_at timestamptz not null default now()
);
create index if not exists ix_question_tests_question_id on public.question_tests(question_id);
create index if not exists ix_question_tests_visibility on public.question_tests(visibility);

-- 6) Helpful indexes for services
create index if not exists ix_questions_challenge_id on public.questions(challenge_id);
create index if not exists ix_questions_language_id on public.questions(language_id);

-- 7) Question attempts (used by question/challenge flows)
create table if not exists public.question_attempts (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions(id) on delete cascade,
  challenge_id uuid not null references public.challenges(id) on delete cascade,
  user_id bigint not null,
  judge0_token text null,
  source_code text not null,
  stdout text null,
  stderr text null,
  status_id int not null,
  status_description text not null,
  time text null,
  memory int null,
  is_correct boolean not null,
  code_hash text null,
  idempotency_key text null,
  latest boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists ix_question_attempts_user_id on public.question_attempts(user_id);
create index if not exists ix_question_attempts_challenge_id on public.question_attempts(challenge_id);
create index if not exists ix_question_attempts_question_id on public.question_attempts(question_id);
create index if not exists ix_question_attempts_token on public.question_attempts(judge0_token);
create index if not exists ix_question_attempts_is_correct on public.question_attempts(is_correct);

-- 8) Challenge attempts
create table if not exists public.challenge_attempts (
  id uuid primary key default gen_random_uuid(),
  challenge_id uuid not null references public.challenges(id) on delete cascade,
  user_id bigint not null,
  status text not null default 'open',
  score int not null default 0,
  correct_count int null,
  snapshot_questions jsonb null,
  started_at timestamptz null,
  deadline_at timestamptz null,
  submitted_at timestamptz null,
  created_at timestamptz not null default now()
);
create index if not exists ix_challenge_attempts_challenge on public.challenge_attempts(challenge_id);
create index if not exists ix_challenge_attempts_user on public.challenge_attempts(user_id);

