# Challenge System Map

## Overview
- **FastAPI entrypoint**: `app/main.py` wires routers, CORS, and session middleware. Auth-protected routers include challenges, Judge0, profiles, dashboard, slides.
- **Persistence layers**:
  - **Supabase** via `app/DB/supabase.py` for challenge metadata (`challenges`, `questions`, `challenge_attempts`, etc.).
  - **Postgres (SQLAlchemy)** via `app/DB/session.py` for Judge0 submission history tables (`CodeSubmission`, `CodeResult`).
- **Caching**: lightweight in-memory cache through `app.common.cache` reused by repositories.

## Challenge lifecycle
1. **Generation** (`app/features/challenges/claude_generator.py`)
   - Generates tiered challenge sets (base/ruby/emerald/diamond) using Claude or fallback templates.
   - Persists challenge rows and their questions into Supabase.
   - Normalises question metadata (language, starter code, reference solution, tier) and **inserts per-question tests** into the `tests` (aka `question_tests`) table via `_insert_tests`.
   - Public test expected output is stored back on the question row for quick comparisons.

2. **Repository access** (`app/features/challenges/repository.py`)
   - Provides cached fetch for challenges, questions, and open attempts.
   - Creates and updates `challenge_attempts`, snapshots the first 5 questions (base challenges), and finalises attempts with aggregated score + correctness count.
   - Utility methods fetch attempts, plain challenge counts, etc.

3. **Challenge service** (`app/features/challenges/service.py`)
   - Orchestrates student submissions.
   - Resolves/creates open attempt, fetches snapshot metadata, and re-runs Judge0 for missing question attempts.
   - Uses `Judge0Service.execute_batch` to run code and marks correctness using stored expected output per snapshot question.
   - Summarises attempt scores (currently 1 point per question) and finalises challenge attempt once all snapshot questions have attempts.

4. **Judge0 integration** (`app/features/judge0/service.py`)
   - Normalises language IDs, submits code to configured Judge0 instance, and resolves acceptance by comparing stdout with expected output.
   - Supports synchronous waits, batch execution, result retrieval, and caching of language/status metadata.

5. **Routing** (`app/features/challenges/endpoints.py`)
   - Currently exposes lecturer-facing generation endpoints (`/generate/{tier}`, `/publish/{week_number}`, `/semester/overview`).
   - Student-facing retrieval/submit endpoints are pending wiring to the `ChallengeService` orchestration.

## Data relationships (Supabase)
- `challenges` → `questions` (1:N). Questions include metadata such as `expected_output`, `language_id`, difficulty tier, `max_time_ms`, `max_memory_kb`.
- `questions` → `question_tests` (1:N). Each test stores `input`, `expected`, and `visibility` (public/private). The first public test is considered the base validation.
- `challenge_attempts` snapshot up to five questions by storing `snapshot_questions` array with per-question execution constraints and expected output.
- Additional tables track attempts per question (via Supabase RPC `latest_attempts_for_challenge`).

## Scoring today
- `app/features/challenges/scoring.py` contains GPA-style aggregation for semester progress, blending plain and special tiers (ruby/emerald/diamond).
- `ChallengeService.submit` currently collapses per-question pass/fail into a total `score` and `correct_count`, but GPA/ELO specific logic is not yet implemented.

## Identified gaps for new grading flow
- Question test cases are persisted but not surfaced/linked when students view or attempt questions.
- No unified submissions module exists to tie attempts, Judge0 execution, GPA, and future ELO calculations together.
- Need to extend challenge endpoints to serve bundled question + test-case data, run quick public-test validations, and update challenge attempts accordingly.

