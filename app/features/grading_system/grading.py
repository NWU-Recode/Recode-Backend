# grading.py
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------
# Database helper functions
# ---------------------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def fetch_pending_challenge_submissions(conn):
    """Fetch submissions for challenges that need grading."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT challenge_id
            FROM challenge_attempts
            WHERE status = 'in_progress'
        """)
        return [row[0] for row in cur.fetchall()]

def fetch_user_attempts(conn, challenge_id):
    """Fetch all submissions per user for a challenge."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ca.user_id, qa.id as question_attempt_id, qa.is_correct,
                   q.points, q.tier
            FROM challenge_attempts ca
            JOIN question_attempts qa ON qa.challenge_id = ca.challenge_id AND qa.user_id = ca.user_id
            JOIN questions q ON q.id = qa.question_id
            WHERE ca.challenge_id = %s
        """, (challenge_id,))
        results = {}
        for row in cur.fetchall():
            user_id, qa_id, is_correct, points, tier = row
            if user_id not in results:
                results[user_id] = []
            results[user_id].append({
                "qa_id": qa_id,
                "is_correct": is_correct,
                "points": points,
                "tier": tier
            })
        return results

# ---------------------------
# Scoring & GPA logic
# ---------------------------
TIER_POINTS = {"bronze": 10, "silver": 20, "gold": 40}
WEIGHTED_CHALLENGES = {"ruby": 0.3, "emerald": 0.4, "diamond": 0.5}  

def calculate_user_score(user_attempts, previous_gpa=0):
    """Calculate GPA and raw earned points."""
    earned_points = 0
    total_points = 0
    weighted_gpa = previous_gpa

    # First, normal tiers
    for attempt in user_attempts:
        tier = attempt["tier"].lower()
        if tier in TIER_POINTS:
            total_points += TIER_POINTS[tier]
            if attempt["is_correct"]:
                earned_points += TIER_POINTS[tier]

    # Then weighted challenges
    for attempt in user_attempts:
        tier = attempt["tier"].lower()
        if tier in WEIGHTED_CHALLENGES:
            weight = WEIGHTED_CHALLENGES[tier]
            attempt_score = TIER_POINTS.get("gold", 40) if attempt["is_correct"] else 0
            weighted_gpa = previous_gpa * (1 - weight) + attempt_score * weight
            previous_gpa = weighted_gpa  # update for next weighted challenge

    normal_gpa = (earned_points / total_points * 100) if total_points > 0 else 0
    final_gpa = weighted_gpa if weighted_gpa > 0 else normal_gpa
    return earned_points, total_points, final_gpa

def calculate_elo(current_elo, time_taken, memory_used, hints_used):
    """Calculate ELO based on performance."""
    base_gain = 20
    time_factor = max(0, 1 - time_taken / 3600)  # seconds
    memory_factor = max(0, 1 - memory_used / 256000)  # KB
    hint_penalty = hints_used * 2
    return int(current_elo + base_gain * time_factor * memory_factor - hint_penalty)

# ---------------------------
# Update functions 
# ---------------------------
def update_challenge_progress(cur, user_id, challenge_id, earned_points, total_points, gpa):
    cur.execute("""
        INSERT INTO challenge_progress (student_id, challenge_id, total_points_earned, max_possible_points, gpa, started_at, completed_at)
        VALUES (%s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (student_id, challenge_id)
        DO UPDATE SET total_points_earned = EXCLUDED.total_points_earned,
                      max_possible_points = EXCLUDED.max_possible_points,
                      gpa = EXCLUDED.gpa,
                      completed_at = now()
    """, (user_id, challenge_id, earned_points, total_points, gpa))

def update_user_elo(cur, user_id, new_elo):
    cur.execute("""
        UPDATE user_elo
        SET current_elo = %s, updated_at = now()
        WHERE student_id = %s
    """, (new_elo, user_id))

# ---------------------------
# Main grading loop
# ---------------------------
def grade_challenges():
    conn = get_db_connection()
    conn.autocommit = False  # manage transactions manually
    try:
        challenge_ids = fetch_pending_challenge_submissions(conn)

        for challenge_id in challenge_ids:
            user_attempts_map = fetch_user_attempts(conn, challenge_id)

            for user_id, attempts in user_attempts_map.items():
                with conn.cursor() as cur:
                    # Fetch previous GPA if exists
                    cur.execute("""
                        SELECT gpa FROM challenge_progress
                        WHERE student_id = %s ORDER BY completed_at DESC LIMIT 1
                    """, (user_id,))
                    row = cur.fetchone()
                    previous_gpa = row[0] if row else 0

                    earned_points, total_points, final_gpa = calculate_user_score(attempts, previous_gpa)
                    print(f"[INFO] User {user_id} Challenge {challenge_id}: {earned_points}/{total_points} pts, GPA {final_gpa:.2f}")

                    # Mock performance metrics
                    time_taken = 1200  # seconds
                    memory_used = 50000  # KB
                    hints_used = 1

                    # Fetch current ELO
                    cur.execute("SELECT current_elo FROM user_elo WHERE student_id = %s", (user_id,))
                    current_elo = cur.fetchone()[0]
                    new_elo = calculate_elo(current_elo, time_taken, memory_used, hints_used)

                    # Transaction block
                    try:
                        update_challenge_progress(cur, user_id, challenge_id, earned_points, total_points, final_gpa)
                        update_user_elo(cur, user_id, new_elo)
                        conn.commit()
                        print(f"[INFO] Updated GPA & ELO for user {user_id}")
                    except Exception as e:
                        conn.rollback()
                        print(f"[ERROR] Failed to update user {user_id}: {e}")

        print("[INFO] Grading completed for all challenges.")
    finally:
        conn.close()

if __name__ == "__main__":
    grade_challenges()
