"""
Usage tracking service for managing story generation limits and quotas
"""
from typing import Tuple, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from calendar import monthrange

from app.models.database_models import User, Subscription, Story, SubscriptionTier


class UsageTrackingService:
    """Service for tracking and managing usage limits"""
    
    @staticmethod
    def can_generate_story(user: User, db: Session) -> Tuple[bool, str]:
        """
        Check if user can generate a story based on their subscription
        Returns: (can_generate, reason)
        """
        subscription = user.subscription
        
        if not subscription:
            return False, "No subscription found"
        
        # Check subscription status
        if subscription.status not in ["active", None]:
            if subscription.status == "payment_failed":
                return False, "Payment failed. Please update your payment method."
            elif subscription.status == "cancelled":
                return False, "Subscription cancelled. Please reactivate to continue."
        
        # Reset monthly count if new month
        UsageTrackingService._reset_monthly_count_if_needed(subscription, db)
        
        # Check based on subscription tier
        if subscription.tier == SubscriptionTier.FREE:
            # Check individual credits first
            if subscription.individual_story_credits and subscription.individual_story_credits > 0:
                return True, "individual_credit"
            
            # Check monthly limit
            if subscription.stories_created_this_month >= subscription.stories_per_month:
                return False, f"Monthly limit of {subscription.stories_per_month} stories reached"
            return True, "free_tier"
        
        elif subscription.tier == SubscriptionTier.BASIC:
            # Basic plan - check monthly limit
            if subscription.stories_per_month == -1:
                return True, "unlimited"
            
            if subscription.stories_created_this_month >= subscription.stories_per_month:
                return False, f"Monthly limit of {subscription.stories_per_month} stories reached"
            return True, "subscription"
        
        elif subscription.tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE]:
            # Premium/Enterprise - unlimited stories
            return True, "unlimited"
        
        return False, "Unknown subscription tier"
    
    @staticmethod
    def record_story_generation(
        user: User,
        story: Story,
        db: Session,
        usage_type: Optional[str] = None
    ) -> bool:
        """
        Record that a story was generated and update usage counters
        """
        subscription = user.subscription
        
        if not subscription:
            return False
        
        # Reset monthly count if needed
        UsageTrackingService._reset_monthly_count_if_needed(subscription, db)
        
        # Update counters based on usage type
        if usage_type == "individual_credit":
            # Deduct individual credit
            if subscription.individual_story_credits > 0:
                subscription.individual_story_credits -= 1
        else:
            # Increment monthly count
            subscription.stories_created_this_month += 1
        
        # Update last generation timestamp
        subscription.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        return True
    
    @staticmethod
    def get_usage_stats(user: User, db: Session) -> dict:
        """Get detailed usage statistics for a user"""
        subscription = user.subscription
        
        if not subscription:
            return {
                "tier": "none",
                "stories_used_this_month": 0,
                "stories_limit": 0,
                "stories_remaining": 0,
                "individual_credits": 0,
                "period_start": None,
                "period_end": None,
                "can_generate": False
            }
        
        # Reset monthly count if needed
        UsageTrackingService._reset_monthly_count_if_needed(subscription, db)
        
        # Calculate remaining stories
        if subscription.stories_per_month == -1:
            stories_remaining = -1  # Unlimited
        else:
            stories_remaining = max(0, subscription.stories_per_month - subscription.stories_created_this_month)
        
        # Check if can generate
        can_generate, _ = UsageTrackingService.can_generate_story(user, db)
        
        # Get period dates
        if subscription.current_period_start and subscription.current_period_end:
            period_start = subscription.current_period_start
            period_end = subscription.current_period_end
        else:
            # Calculate based on creation date
            period_start, period_end = UsageTrackingService._get_current_period(subscription.created_at)
        
        return {
            "tier": subscription.tier.value,
            "stories_used_this_month": subscription.stories_created_this_month,
            "stories_limit": subscription.stories_per_month,
            "stories_remaining": stories_remaining,
            "individual_credits": subscription.individual_story_credits or 0,
            "period_start": period_start,
            "period_end": period_end,
            "can_generate": can_generate,
            "sunshines_count": len(user.sunshines) if user.sunshines else 0,
            "sunshines_limit": subscription.sunshines_limit
        }
    
    @staticmethod
    def check_sunshine_limit(user: User, db: Session) -> Tuple[bool, str]:
        """
        Check if user can add another Sunshine profile
        """
        subscription = user.subscription
        
        if not subscription:
            return False, "No subscription found"
        
        # Count active sunshines
        active_sunshines = sum(1 for s in user.sunshines if s.is_active)
        
        if subscription.sunshines_limit == -1:
            return True, "unlimited"
        
        if active_sunshines >= subscription.sunshines_limit:
            return False, f"Sunshine limit of {subscription.sunshines_limit} reached. Upgrade to add more."
        
        return True, "within_limit"
    
    @staticmethod
    def _reset_monthly_count_if_needed(subscription: Subscription, db: Session):
        """Reset monthly story count if we're in a new billing period"""
        now = datetime.now(timezone.utc)
        
        # If subscription has Stripe period dates, use those
        if subscription.current_period_end and subscription.current_period_start:
            if now >= subscription.current_period_end:
                # We're past the period end, reset count
                # Note: Stripe webhook should update period dates
                subscription.stories_created_this_month = 0
                db.commit()
        else:
            # Use creation date to determine monthly reset
            if subscription.created_at:
                period_start, period_end = UsageTrackingService._get_current_period(subscription.created_at)
                
                # Check if we need to reset
                if subscription.updated_at:
                    last_update_period_start, _ = UsageTrackingService._get_current_period(
                        subscription.updated_at
                    )
                    if period_start > last_update_period_start:
                        # New period, reset count
                        subscription.stories_created_this_month = 0
                        db.commit()
    
    @staticmethod
    def _get_current_period(start_date: datetime) -> Tuple[datetime, datetime]:
        """
        Calculate current billing period based on start date
        Returns (period_start, period_end)
        """
        now = datetime.now(timezone.utc)
        
        # Calculate months since start
        months_diff = (now.year - start_date.year) * 12 + (now.month - start_date.month)
        
        # Calculate current period start
        period_year = start_date.year + (start_date.month + months_diff - 1) // 12
        period_month = ((start_date.month + months_diff - 1) % 12) + 1
        period_day = min(start_date.day, monthrange(period_year, period_month)[1])
        
        period_start = datetime(
            period_year, period_month, period_day,
            start_date.hour, start_date.minute, start_date.second,
            tzinfo=timezone.utc
        )
        
        # Calculate period end (one month later)
        if period_month == 12:
            end_year = period_year + 1
            end_month = 1
        else:
            end_year = period_year
            end_month = period_month + 1
        
        end_day = min(start_date.day, monthrange(end_year, end_month)[1])
        
        period_end = datetime(
            end_year, end_month, end_day,
            start_date.hour, start_date.minute, start_date.second,
            tzinfo=timezone.utc
        )
        
        return period_start, period_end
    
    @staticmethod
    def get_story_history(
        user: User,
        db: Session,
        limit: int = 10,
        offset: int = 0
    ) -> list:
        """Get story generation history for a user"""
        stories = db.query(Story).filter(
            Story.user_id == user.id
        ).order_by(
            Story.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "id": story.id,
                "title": story.title,
                "child_name": story.child_name,
                "created_at": story.created_at,
                "word_count": story.word_count,
                "reading_time": story.reading_time
            }
            for story in stories
        ]
    
    @staticmethod
    def validate_subscription_features(
        user: User,
        feature: str
    ) -> Tuple[bool, str]:
        """
        Validate if user has access to a specific feature
        """
        subscription = user.subscription
        
        if not subscription:
            return False, "No subscription found"
        
        feature_map = {
            "pdf_export": "has_pdf_export",
            "image_generation": "has_image_generation",
            "custom_illustrations": "has_custom_illustrations",
            "multi_language": "has_multi_language",
            "api_access": "has_api_access"
        }
        
        if feature not in feature_map:
            return False, f"Unknown feature: {feature}"
        
        has_feature = getattr(subscription, feature_map[feature], False)
        
        if not has_feature:
            return False, f"Feature '{feature}' not available in {subscription.tier.value} tier"
        
        return True, "allowed"


# Global instance
usage_tracking_service = UsageTrackingService()