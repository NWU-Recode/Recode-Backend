-- Migration: create stored procedure record_test_result_and_award
-- This file can be applied in Supabase SQL editor or via psql.
-- Function signature expected by application:
-- record_test_result_and_award(p_profile_id integer, p_question_id text, p_test_id text, p_is_public boolean, p_passed boolean, p_public_badge_id uuid)

-- Note: p_profile_id corresponds to profiles.id (integer). The `question_attempts` table in this
-- project uses columns `submitted_at`, `time_ms`, and `memory_kb` and the unique constraint
-- name `question_attempts_user_id_question_id_idempotency_key_key` as provided by the schema.

CREATE OR REPLACE FUNCTION public.record_test_result_and_award(
    p_profile_id integer,
    p_question_id text,
    p_test_id text,
    p_is_public boolean,
    p_passed boolean,
    p_public_badge_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := now();
    v_question_attempt_id uuid;
    v_existing boolean := false;
    v_user_elo_record record;
    v_elo_after integer;
    v_badge_awarded boolean := false;
BEGIN
    -- 1) Insert a question_attempt row idempotently using the existing unique constraint
    -- The question_attempts table has unique constraint question_attempts_user_id_question_id_idempotency_key_key (user_id, question_id, idempotency_key)
    -- Application is expected to call this RPC only for passed tests; but we still record attempts regardless.

    -- Try to insert a new attempt row guarded by the composite unique on (question_id, user_id, idempotency_key).
    -- Since the app does not pass an idempotency key here, we create a synthetic one from test id + profile to make repeated RPC calls safe.
    PERFORM 1; -- no-op to ensure plpgsql context

    BEGIN
        INSERT INTO question_attempts(
            id, question_id, challenge_id, user_id, judge0_token, source_code, stdout, stderr,
            status_id, status_description, time_ms, memory_kb, is_correct, submitted_at, idempotency_key, latest
        )
        VALUES (
            gen_random_uuid(), p_question_id::uuid, NULL, p_profile_id::integer, NULL, NULL, NULL, NULL,
            CASE WHEN p_passed THEN 3 ELSE 1 END, CASE WHEN p_passed THEN 'passed_via_rpc' ELSE 'failed_via_rpc' END,
            NULL, NULL, p_passed, v_now, ('rpc:' || p_test_id || ':' || p_profile_id), true
        )
        ON CONFLICT ON CONSTRAINT question_attempts_user_id_question_id_idempotency_key_key
        DO UPDATE SET latest = true
        RETURNING id INTO v_question_attempt_id;
    EXCEPTION WHEN unique_violation THEN
        -- Fallback: if conflict raised differently, select existing row
        SELECT id INTO v_question_attempt_id FROM question_attempts
        WHERE question_id = p_question_id::uuid AND user_id = p_profile_id::integer AND idempotency_key = ('rpc:' || p_test_id || ':' || p_profile_id)
        LIMIT 1;
        v_existing := true;
    END;

    -- If we didn't get an id (very unlikely), try to fetch existing
    IF v_question_attempt_id IS NULL THEN
    SELECT id INTO v_question_attempt_id FROM question_attempts
    WHERE question_id = p_question_id::uuid AND user_id = p_profile_id::integer
    ORDER BY submitted_at DESC LIMIT 1;
        IF v_question_attempt_id IS NOT NULL THEN
            v_existing := true;
        END IF;
    END IF;

    -- 2) Award badge (if public and badge id provided) and not already present
    IF p_is_public AND p_public_badge_id IS NOT NULL AND p_passed THEN
        -- Some deployments use `user_badges` table, some `user_badge` - check both.
        IF NOT EXISTS (SELECT 1 FROM user_badges WHERE user_id = p_profile_id::integer AND badge_id = p_public_badge_id) THEN
            BEGIN
                INSERT INTO user_badges(id, user_id, badge_id, challenge_id, challenge_attempt_id, source_submission_id, awarded_at, date_earned)
                VALUES (gen_random_uuid(), p_profile_id::integer, p_public_badge_id, NULL, NULL, NULL, v_now, v_now);
                v_badge_awarded := true;
            EXCEPTION WHEN undefined_table OR undefined_column THEN
                -- try alternate table name
                PERFORM 1;
            END;
        END IF;
        -- if still not inserted, try the alternate single-name table
        IF NOT v_badge_awarded THEN
            IF NOT EXISTS (SELECT 1 FROM user_badge WHERE user_id = p_profile_id::integer AND badge_id = p_public_badge_id) THEN
                BEGIN
                    INSERT INTO user_badge(id, user_id, badge_id, challenge_id, challenge_attempt_id, source_submission_id, awarded_at, date_earned)
                    VALUES (gen_random_uuid(), p_profile_id::integer, p_public_badge_id, NULL, NULL, NULL, v_now, v_now);
                    v_badge_awarded := true;
                EXCEPTION WHEN undefined_table OR undefined_column THEN
                    -- give up quietly if neither table exists
                    PERFORM 1;
                END;
            END IF;
        END IF;
    END IF;

    -- 3) Update or insert user_elo record: increment elo_points by a small delta for a passed test;
    -- The delta is intentionally conservative. The application calculates elo delta itself; here we apply a fixed small award to keep an auditable running total.
    -- If a larger or computed delta is required, change this function to accept p_elo_delta numeric.
    IF p_passed THEN
        -- award +1 elo point by default for a passed test; this keeps an auditable running total
        PERFORM 1;
        BEGIN
            -- Prefer canonical user_elo table
            UPDATE user_elo SET elo_points = COALESCE(elo_points,0) + 1, updated_at = v_now
            WHERE user_id = p_profile_id::integer
            RETURNING elo_points INTO v_elo_after;
            IF NOT FOUND THEN
                -- try inserting into user_elo; if that table doesn't exist, we'll try user_scores below
                BEGIN
                    INSERT INTO user_elo(id, user_id, elo_points, running_gpa, updated_at)
                    VALUES (gen_random_uuid(), p_profile_id::integer, 1, NULL, v_now)
                    RETURNING elo_points INTO v_elo_after;
                EXCEPTION WHEN undefined_table OR undefined_column THEN
                    v_elo_after := NULL;
                END;
            END IF;
        EXCEPTION WHEN undefined_table THEN
            -- If user_elo table is not present or columns differ, ignore gracefully
            v_elo_after := NULL;
        END;
        -- If the canonical user_elo table wasn't available, try updating the denormalized `user_scores` table
        IF v_elo_after IS NULL THEN
            BEGIN
                UPDATE user_scores SET total_earned_elo = COALESCE(total_earned_elo,0) + 1, elo = COALESCE(elo,1000) + 1, last_updated = v_now
                WHERE student_id = p_profile_id::integer
                RETURNING elo INTO v_elo_after;
                IF NOT FOUND THEN
                    -- attempt to insert into user_scores if it exists
                    INSERT INTO user_scores(student_id, elo, total_earned_elo, last_updated)
                    VALUES (p_profile_id::integer, 1001, 1, v_now)
                    RETURNING elo INTO v_elo_after;
                END IF;
            EXCEPTION WHEN undefined_table OR undefined_column THEN
                v_elo_after := NULL;
            END;
        END IF;
    ELSE
        -- For failed tests we do not change elo here
        v_elo_after := NULL;
    END IF;

    RETURN jsonb_build_object(
        'existing', v_existing,
        'attempt_id', v_question_attempt_id,
        'badge_awarded', v_badge_awarded,
        'elo_after', v_elo_after
    );
END;
$$;

-- Note: this function uses gen_random_uuid() which is provided by the pgcrypto extension on many Postgres installs.
-- If pgcrypto is not available, replace gen_random_uuid() with uuid_generate_v4() (from the uuid-ossp extension) or another UUID generator.
