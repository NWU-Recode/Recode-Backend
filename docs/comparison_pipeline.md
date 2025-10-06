# Parallel Comparison & Normalisation Pipeline

Grading is now powered by a registry of comparison strategies that execute in parallel. Every Judge0 `Accepted` result fans out across the strategy pool and the first pass (by priority) wins. The registry keeps the tolerant behaviour introduced earlier while making it configurable per test.

## Execution flow

1. **Unicode NFC** – inputs are normalised to the configured Unicode form (default `NFC`) and Windows newlines are rewritten to `\n`.
2. **Large output hashing** – strings above the configurable threshold (default 2 MB) are hashed with SHA-256. Matching hashes pass immediately and skip the rest of the pipeline.
3. **Strict equality** – an identical match after normalisation short-circuits (`STRICT`).
4. **Async strategy fan-out** – remaining strategies run concurrently on a background thread pool. The priority order is:
   1. `TRIM_EOL`
   2. `NORMALISE_WHITESPACE` (conservative then aggressive)
   3. `CANONICAL_PY_LITERAL`
   4. `FLOAT_EPS`
   5. `TOKEN_SET`

Each strategy reports whether it passed, failed, or deferred (returns `None`). The first passing strategy wins; the first hard failure becomes the reason if nobody succeeds.

## Per-test configuration

Two new columns live on `question_tests`:

| Column           | Type    | Default | Purpose                                                        |
| ---------------- | ------- | ------- | -------------------------------------------------------------- |
| `compare_mode`   | `text`  | `AUTO`  | Force a single comparator or leave `AUTO` to run the full pool |
| `compare_config` | `jsonb` | `{}`    | Strategy overrides (e.g. `{ "float_eps": 1e-4 }`)              |

The API exposes these via `QuestionTestSchema.compare_mode` and `compare_config`. Use `resolve_mode(value)` to safely coerce database strings – invalid or empty values fall back to `AUTO`.

## Response telemetry

Each `TestRunResult` now carries a richer trace:

- `compare_mode_applied` – name of the winning strategy (or hash shortcut)
- `normalisations_applied` – base normalisations plus the winner’s annotations
- `comparison_attempts` – ordered attempts with `{mode, passed, reason, normalisations, duration_ms}`
- `why_failed` – populated with the first decisive failure when no strategy succeeds

This makes it easier to explain marks to learners and to tune future strategies.

## Strategy overrides

- `float_eps` – override numeric tolerance (`float_eps` or nested `{ "float": { "eps": ... } }`)
- `token_set_limit` – raise/lower the maximum length for word-token comparison
- `unicode_nf` or `large_output_threshold` – adjust base normalisation behaviour

All overrides are optional. Anything unspecified falls back to `CompareConfig` defaults.

## Debugging tips

- Hit `GET /submissions/challenges/{cid}/questions/{qid}/bundle` to inspect expected outputs and per-test comparator settings.
- Review `comparison_attempts` on a test result to see every strategy’s verdict.
- `why_failed` tells you which strategy vetoed the submission.

Legacy notes about `expected_hash` still apply: precomputing hashes is optional but supported for content tooling.
