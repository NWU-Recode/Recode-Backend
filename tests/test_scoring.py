from app.features.challenges.scoring import (
    AttemptScore,
    recompute_semester_mark,
)


def test_plain_only():
    attempts = [AttemptScore(tier=AttemptScore.tier.__annotations__ if False else None, correct=True, total=1) for _ in range(3)]
    # simpler: use AttemptScore with correct flags
    attempts = [AttemptScore(tier=None, correct=True, total=1), AttemptScore(tier=None, correct=False, total=1)]
    agg = recompute_semester_mark(attempts, ruby_correct=False, emerald_correct=False, diamond_correct=False)
    assert agg.plain_pct == 50.0
    assert agg.blended_pct == 50.0


def test_ruby_blend():
    attempts = [AttemptScore(tier=None, correct=True, total=1) for _ in range(4)]
    # plain_pct = 100
    agg = recompute_semester_mark(attempts, ruby_correct=True, emerald_correct=False, diamond_correct=False)
    # blended = 0.6*100 + 0.4*100 = 100
    assert agg.plain_pct == 100.0
    assert agg.blended_pct == 100.0


def test_ruby_partial():
    attempts = [AttemptScore(tier=None, correct=True, total=1) for _ in range(2)] + [AttemptScore(tier=None, correct=False, total=1) for _ in range(2)]
    # plain_pct = 50
    agg = recompute_semester_mark(attempts, ruby_correct=True, emerald_correct=False, diamond_correct=False)
    # blended = 0.6*50 + 0.4*100 = 70
    assert agg.plain_pct == 50.0
    assert agg.blended_pct == 70.0


def test_emerald_blend():
    attempts = [AttemptScore(tier=None, correct=True, total=1) for _ in range(6)]
    # plain_pct = 100
    agg = recompute_semester_mark(attempts, ruby_correct=True, emerald_correct=True, diamond_correct=False)
    # specials_avg = avg(1,1)=1 -> 100
    # blended = 0.5*100 + 0.5*100 = 100
    assert agg.blended_pct == 100.0


def test_diamond_blend():
    attempts = [AttemptScore(tier=None, correct=False, total=1) for _ in range(4)]
    # plain_pct = 0
    agg = recompute_semester_mark(attempts, ruby_correct=True, emerald_correct=True, diamond_correct=True)
    # specials_avg = avg(1,1,1)=100
    # blended = 0.4*0 + 0.6*100 = 60
    assert agg.plain_pct == 0.0
    assert agg.blended_pct == 60.0
