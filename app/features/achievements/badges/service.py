from app.DB.session import get_db
from app.features.achievements.badges.schemas import UserBadgesResponse,BadgeInfo, BadgeAwardResponse
from app.features.achievements.repository import BadgeRepository
from datetime import datetime, timedelta

class BadgesService:
    def __init__(self, badge_repo: BadgeRepository):
        self.badge_repo = badge_repo

    def get_all_user_badges(self, user_id: str) -> UserBadgesResponse:
        raw_badges = self.badge_repo.get_user_badges(user_id)
        badges = [BadgeInfo(**b) for b in raw_badges]
        return UserBadgesResponse(
            user_id=user_id,
            badges=badges,
            total_badges=len(badges)
        )
    
    def check_for_new_badge_after_submission(self, user_id: str, question_id: str) -> BadgeAwardResponse:
        #this is defining a short time window to help detect recent awarded badges (so that it doesnt send "new badge" alert to frontend if user reattempts question)
        one_minute_ago = datetime.uctnow() - timedelta(minutes=1)

        #fetch badge for specific user and question 
        badge_data = self.badge_repo.check_for_new_badge_after_submission(user_id, question_id)

        #only returns it if badge was awareded recently (in the last minute)
        if badge_data and badge_data['awarded_at'] and badge_data['awarded_at'] >= one_minute_ago:
            return BadgeAwardResponse(
                badge_awarded=True,
                badge=BadgeInfo(**badge_data)
            )
        return BadgeAwardResponse(badge_awarded=False)