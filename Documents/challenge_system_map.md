# Challenge System Map

## Slide → Challenge Pipeline
- `POST /slides/upload` reads slide bytes, extracts topics, and resolves the **active semester window** using `ModuleRepository` with an environment fallback (`SEMESTER_START`).
- Upload metadata is saved into Supabase `slide_extractions`, topics are created/linked in `topics`, and the resolved `week_number` is preserved on the extraction as well as the generated challenges.
- Automatic generation triggers `ChallengePackGenerator.generate_and_save_tier` for base (every week) and optional ruby/emerald/diamond tiers based on the computed week. Each generator call persists into Supabase `challenges`/`questions`/`question_tests` and re-uses the detected topics.

## Challenge Generation
- `ChallengePackGenerator` builds a context from slides/topics, calls the Bedrock-backed template, normalises returned questions, and persists the challenge.
- Week numbers are explicitly supplied to `_insert_challenge` so that `week_number` is always written for every tier (emerald/diamond included). Duplicate-week checks are module aware.
- Challenges can be published immediately via `challenge_repository.publish_for_week` once generation finishes.

## Submissions & Scoring
- `MAX_SCORING_ATTEMPTS = 1` enforces a single scored submission per question. Additional attempts return `attempt_limit_reached` without affecting scores.
- ELO base rewards are tuned per tier (25/35/50/65/120/190/320 for base→diamond) with proportional fail penalties. Efficiency bonuses scale from these new baselines.
- GPA weights mirror the new tiers (`bronze` 12 → `diamond` 60).
- Achievements now scope ELO records by `(user_id, module_code, semester_id)` and reset every semester/module. Helper methods resolve the active semester window and persist `semester_start`/`semester_end` metadata alongside each `user_elo` row.

## Judge0 API Surface
- Public endpoints: `GET /judge0/languages`, `GET /judge0/statuses`, `POST /judge0/execute`, `/execute/stdout`, `/execute/simple`, `/execute/batch`.
- Auth-protected endpoints: `POST /judge0/submit/full` (async token) and `GET /judge0/result/{token}`.
- All endpoints rely on `Judge0Service` for submission orchestration and respond with normalised stdout/status payloads.

## Key Tables
- **slides** bucket: uploaded PPTX/PDF assets referenced by `slide_extractions`.
- **slide_extractions / topics**: derived from slide uploads, carry `week_number`, `module_code`, and topic metadata.
- **challenges / questions / question_tests**: generated challenge packs and their graded tests.
- **challenge_attempts**: student submissions with snapshot questions, correctness counts, and ELO/GPA deltas.
- **user_elo**: per-user, per-module, per-semester scoring records that feed achievements, analytics dashboards, and titles.
