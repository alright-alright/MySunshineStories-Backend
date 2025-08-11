"""
Pydantic schemas for Subscription models
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"


class SubscriptionBase(BaseModel):
    tier: SubscriptionTier = SubscriptionTier.FREE
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE


class SubscriptionCreate(SubscriptionBase):
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionInDB(SubscriptionBase):
    id: str
    user_id: str
    stories_per_month: int
    stories_created_this_month: int
    sunshines_limit: int
    has_pdf_export: bool
    has_image_generation: bool
    has_custom_illustrations: bool
    has_multi_language: bool
    has_api_access: bool
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(SubscriptionInDB):
    can_create_story: bool = True
    stories_remaining: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_orm_model(cls, subscription):
        """Create response from SQLAlchemy model"""
        data = {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "tier": subscription.tier,
            "status": subscription.status,
            "stories_per_month": subscription.stories_per_month,
            "stories_created_this_month": subscription.stories_created_this_month,
            "sunshines_limit": subscription.sunshines_limit,
            "has_pdf_export": subscription.has_pdf_export,
            "has_image_generation": subscription.has_image_generation,
            "has_custom_illustrations": subscription.has_custom_illustrations,
            "has_multi_language": subscription.has_multi_language,
            "has_api_access": subscription.has_api_access,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "created_at": subscription.created_at,
            "updated_at": subscription.updated_at,
            "cancelled_at": subscription.cancelled_at,
            "can_create_story": subscription.can_create_story() if hasattr(subscription.can_create_story, '__call__') else True,
            "stories_remaining": subscription.stories_per_month - subscription.stories_created_this_month if subscription.stories_per_month != -1 else None
        }
        return cls(**data)