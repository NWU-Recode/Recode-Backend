# Recode Backend

> **Transform lecture slides into engaging coding challenges with automated grading and gamified rewards**

Recode converts lecture slides into weekly coding challenges, keeps the semester schedule in sync, and tracks rewards (ELO, GPA, badges) for every student attempt. Built on FastAPI with Supabase as the primary datastore.

---

## 🎯 What the System Does

### Slide Ingestion → Challenges

Admins upload slides, we extract topics, calculate the teaching week from the active semester, and auto-generate a base (and optional ruby/emerald/diamond) challenge for that week.

### Challenge Delivery

The challenge repository exposes base/special tiers with full question snapshots (including test cases) for lecturers and students.

### Submissions and Grading

Students submit their program output once per question; we normalise it, compare with the expected answer, compute GPA/ELO deltas, and persist attempt records without sending code to Judge0.

### Rewards

Achievements service keeps `user_elo`, `elo_events`, and badge tables updated, attaching human-readable summaries so learners know why scores changed. The Elo ladder now spans **0 – 8 000** with a logistic scorer tuned for the 12-week, 18-challenge season:

- Tier ratings: Bronze 1 600, Silver 3 000, Gold 4 200, Ruby 5 400, Emerald 6 400, Diamond 7 600 (plain/base map to Bronze).
- K-factors scale from 420 → 500 so perfect clears trend toward 7 500+ while caps enforce the 8 000 ceiling.
- Performance score blends accuracy, speed (time vs. limit), efficiency bonuses, and penalties for hints/resubmissions to reward thoughtful play.
- API responses include full `achievements.summary` payloads (Elo/GPA before/after, badge unlock reasons, title changes) after every challenge submission.

---

## 🏗️ Key Components

<pre class="font-ui border-border-100/50 overflow-x-scroll w-full rounded border-[0.5px] shadow-[0_2px_12px_hsl(var(--always-black)/5%)]"><table class="bg-bg-100 min-w-full border-separate border-spacing-0 text-sm leading-[1.88888] whitespace-normal"><thead class="border-b-border-100/50 border-b-[0.5px] text-left"><tr class="[tbody>&]:odd:bg-bg-500/10"><th class="text-text-000 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] px-2 [&:not(:first-child)]:border-l-[0.5px]">Component</th><th class="text-text-000 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] px-2 [&:not(:first-child)]:border-l-[0.5px]">Purpose</th></tr></thead><tbody><tr class="[tbody>&]:odd:bg-bg-500/10"><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]"><code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">app/features/slides</code></td><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]">Upload endpoints, semester/week resolution, topic creation</td></tr><tr class="[tbody>&]:odd:bg-bg-500/10"><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]"><code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">app/features/challenges</code></td><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]">Generator (<code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">challenge_pack_generator.py</code>), repository helpers, public/admin endpoints</td></tr><tr class="[tbody>&]:odd:bg-bg-500/10"><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]"><code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">app/features/submissions</code></td><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]">Judge0 integration, scoring rules, attempt persistence</td></tr><tr class="[tbody>&]:odd:bg-bg-500/10"><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]"><code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">app/features/achievements</code></td><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]">ELO/GPA/badge logic and reward summaries</td></tr><tr class="[tbody>&]:odd:bg-bg-500/10"><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]"><code class="bg-text-200/5 border border-0.5 border-border-300 text-danger-000 whitespace-pre-wrap rounded-[0.4rem] px-1 py-px text-[0.9rem]">app/DB/supabase.py</code></td><td class="border-t-border-100/50 [&:not(:first-child)]:-x-[hsla(var(--border-100) / 0.5)] border-t-[0.5px] px-2 [&:not(:first-child)]:border-l-[0.5px]">Lightweight Supabase client factory used across repositories</td></tr></tbody></table></pre>

---

## 🚀 Run It Locally

### 1. Python Environment

bash

```bash
python -m venv .venv
.venv\Scripts\activate  # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file:

env

```env
SUPABASE_URL=...              # required
SUPABASE_KEY=...              # service role key recommended for local dev
SEMESTER_START=2025-08-31     # fallback if no active semester in DB
PUBLISHER_INTERVAL_SEC=300    # optional: auto-publish loop interval
```

### 3. Start FastAPI

bash

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. API Documentation

Swagger UI available at: **`http://localhost:8000/docs`**

Access all endpoints including Judge0 helpers, slide upload, submissions, and achievements.

---

## 🔄 How the Pipeline Works

### 1️⃣ Slide Upload (`POST /slides/upload`)

- Reads the active semester (module-specific if set, otherwise env fallback)
- Calculates the teaching week, stores slide extraction + topic
- Triggers `generate_and_save_tier`
- Generator writes challenges, questions, and question_tests to Supabase
- Current-week challenges are promoted to `status="active"`
- Older challenges are demoted by the background publisher in `app/main.py`

### 2️⃣ Challenge Access

Repositories expose:

- `get_active_for_week`
- `list_challenges_by_module`
- `list_questions_for_challenge(include_testcases=True)`

Points per question come from tier constants (`POINTS_BY_DIFFICULTY`), matching the gamified ladder:

- **Base:** 10/20/40
- **Ruby:** 80
- **Emerald:** 120
- **Diamond:** 200

### 3️⃣ Submissions & Judge0

- Students submit once per question (`MAX_SCORING_ATTEMPTS = 1`)
- Judge0 validates outputs
- Scoring service calculates:
  - Base ELO
  - Efficiency bonus
  - GPA contribution
- Stores attempt/test results

### 4️⃣ Rewards Engine

Achievements service:

- Updates `user_elo` per module + semester
- Logs `elo_events` with reasons (performance ratio, hint penalties, override notes)
- Recomputes GPA
- Awards badges
- API responses include `summary` payloads describing before/after ELO, GPA deltas, and badge grants

---

## ⚙️ Operational Notes

### Database

All persistence uses Supabase PostgREST. Ensure these tables exist:

- `challenges`
- `questions`
- `question_tests`
- `slide_extractions`
- `topics`
- `user_elo`
- `elo_events`
- `user_badges` (or `user_badge`)

### Semesters

Admin tools rely on `semesters` table with `is_current=true` for auto week calculation. Set `SEMESTER_START` env only as a fallback.

### Background Publisher

On startup, we schedule a coroutine (in `app/main.py`) that:

- Checks every module
- Computes the current week
- Calls `publish_for_week`
- Enforces active limits

### Judge0

Configure base URL and keys in `.env` if you run a private instance; otherwise the default service wrapper expects the hosted Judge0 configured in Supabase secrets.

---

## 🧪 Testing

`pytest` requires `SUPABASE_URL` and `SUPABASE_KEY`. Use disposable Supabase projects or mocked responses for CI.

Integration tests live under `tests/`:

- Generation fakes
- Admin flows
- Submissions

---

## 📦 Deployment Checklist

- [ ] Supply the Supabase service role key to the container/instance
- [ ] Run database migrations (see `alembic/versions` and SQL scripts under `scripts/`)
- [ ] Configure environment vars for semester start (or seed the `semesters` table plus `teaching_assignments`)
- [ ] Expose HTTP/HTTPS for FastAPI behind your load balancer
- [ ] Ensure background publisher interval is reasonable for your traffic volume
