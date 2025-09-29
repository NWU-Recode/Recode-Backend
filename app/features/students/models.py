

from tortoise import fields, models

# -------------------
# Profiles Table
# -------------------
class Profile(models.Model):
    id = fields.IntField(pk=True)
    supabase_id = fields.UUIDField()
    email = fields.CharField(max_length=255, unique=True)
    full_name = fields.CharField(max_length=255)
    avatar_url = fields.CharField(max_length=255, null=True)
    phone = fields.CharField(max_length=20, null=True)
    bio = fields.TextField(null=True)
    role = fields.CharField(max_length=50, null=True)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)
    email_verified = fields.BooleanField(default=False)
    last_sign_in = fields.DatetimeField(null=True)
    user_metadata = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    title_id = fields.UUIDField(null=True)

    class Meta:
        table = "profiles"

# -------------------
# Student Dashboard View
# -------------------
class StudentDashboard(models.Model):
    user_id = fields.IntField(pk=True)
    module_id = fields.UUIDField()
    module_code = fields.CharField(max_length=50)
    module_name = fields.CharField(max_length=255)
    progress_percent = fields.FloatField()
    elo = fields.IntField(null=True)
    current_title = fields.CharField(max_length=255, null=True)
    current_streak = fields.IntField(null=True)
    longest_streak = fields.IntField(null=True)
    total_points = fields.IntField(null=True)
    total_questions_passed = fields.IntField(null=True)
    challenges_completed = fields.IntField(null=True)
    total_badges = fields.IntField(null=True)
    last_submission = fields.DatetimeField(null=True)

    class Meta:
        table = "student_dashboard"

# -------------------
# User Badges Table
# -------------------
class UserBadge(models.Model):
    id = fields.UUIDField(pk=True)
    profile_id = fields.IntField()
    badge_id = fields.UUIDField()
    awarded_at = fields.DatetimeField(null=True)

    class Meta:
        table = "user_badge"

# -------------------
# Badges Table
# -------------------
class Badge(models.Model):
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=255)
    description = fields.TextField(null=True)
    badge_type = fields.CharField(max_length=50)

    class Meta:
        table = "badges"

# -------------------
# User ELO Table
# -------------------
class UserElo(models.Model):
    student_id = fields.IntField(pk=True)
    current_elo = fields.IntField()
    current_streak = fields.IntField()
    longest_streak = fields.IntField()
    updated_at = fields.DatetimeField(null=True)
    total_awarded_elo = fields.BigIntField()
    last_awarded_at = fields.DatetimeField(null=True)

    class Meta:
        table = "user_elo"

# -------------------
# Submissions Table
# -------------------
class Submission(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.IntField()
    challenge_id = fields.UUIDField()
    question_id = fields.UUIDField()
    status_id = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "submissions"

# -------------------
# Code Submissions Table
# -------------------
class CodeSubmission(models.Model):
    id = fields.IntField(pk=True)
    user_id = fields.IntField()
    challenge_id = fields.UUIDField()
    question_id = fields.UUIDField()
    is_correct = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "code_submissions"
