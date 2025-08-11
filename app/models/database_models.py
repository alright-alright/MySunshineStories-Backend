"""
SQLAlchemy database models for LucianTales
"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, Text, ForeignKey, JSON, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from app.core.database import Base


class SubscriptionTier(enum.Enum):
    """Subscription tier levels"""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class StoryTone(enum.Enum):
    """Story tone options"""
    CALM = "calm"
    EMPOWERING = "empowering"
    BEDTIME = "bedtime"
    ADVENTURE = "adventure"


class User(Base):
    """User model for authentication and profile"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True)
    full_name = Column(String(255))
    hashed_password = Column(String(255))  # Null for OAuth users
    
    # OAuth fields
    google_id = Column(String(255), unique=True, index=True)
    apple_id = Column(String(255), unique=True, index=True)
    avatar_url = Column(String(500))
    
    # User status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    sunshines = relationship("Sunshine", back_populates="user", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class Sunshine(Base):
    """Child profile for personalized stories"""
    __tablename__ = "sunshines"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Child information
    name = Column(String(100), nullable=False)
    birthdate = Column(Date, nullable=False)
    gender = Column(String(50), nullable=False)
    pronouns = Column(String(50))
    nickname = Column(String(100))
    
    # Preferences
    favorite_color = Column(String(50))
    favorite_animal = Column(String(100))
    favorite_food = Column(String(100))
    favorite_activity = Column(String(200))
    
    # Psychological/Medical
    fears = Column(JSON, default=list)
    dreams = Column(JSON, default=list)
    allergies = Column(JSON, default=list)
    special_needs = Column(Text)
    bedtime_routine = Column(Text)
    
    # Personality
    personality_summary = Column(Text)
    additional_notes = Column(Text)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sunshines")
    stories = relationship("Story", back_populates="sunshine", cascade="all, delete-orphan")
    photos = relationship("SunshinePhoto", back_populates="sunshine", cascade="all, delete-orphan")
    family_members = relationship("FamilyMember", back_populates="sunshine", cascade="all, delete-orphan")
    comfort_items = relationship("ComfortItem", back_populates="sunshine", cascade="all, delete-orphan")
    personality_traits = relationship("PersonalityTrait", back_populates="sunshine", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Sunshine {self.name}>"


class Story(Base):
    """Generated story model"""
    __tablename__ = "stories"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sunshine_id = Column(String, ForeignKey("sunshines.id", ondelete="SET NULL"))
    
    # Story content
    title = Column(String(255), nullable=False)
    story_text = Column(Text, nullable=False)
    tone = Column(SQLEnum(StoryTone), nullable=False)
    
    # Story metadata
    child_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    fear_or_challenge = Column(String(500))
    favorite_items = Column(JSON, default=list)
    family_members = Column(JSON, default=dict)
    
    # Generated content
    scenes = Column(JSON, default=list)  # List of scene descriptions
    image_urls = Column(JSON, default=list)  # List of generated image URLs
    pdf_url = Column(String(500))
    
    # Statistics
    reading_time = Column(Integer, default=5)  # Estimated reading time in minutes
    word_count = Column(Integer)
    rating = Column(Float)  # User rating 1-5
    is_favorite = Column(Boolean, default=False)
    read_count = Column(Integer, default=0)
    
    # AI Generation metadata
    model_used = Column(String(50), default="gpt-4o")
    generation_time = Column(Float)  # Time taken to generate in seconds
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_read_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="stories")
    sunshine = relationship("Sunshine", back_populates="stories")
    
    def __repr__(self):
        return f"<Story {self.title}>"


class Subscription(Base):
    """User subscription model"""
    __tablename__ = "subscriptions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Subscription details
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    status = Column(String(50), default="active")  # active, cancelled, expired, paused
    
    # Stripe integration
    stripe_customer_id = Column(String(255), unique=True, index=True)
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    stripe_price_id = Column(String(255))
    
    # Subscription limits
    stories_per_month = Column(Integer, default=3)  # -1 for unlimited
    stories_created_this_month = Column(Integer, default=0)
    sunshines_limit = Column(Integer, default=1)  # -1 for unlimited
    
    # Features
    has_pdf_export = Column(Boolean, default=False)
    has_image_generation = Column(Boolean, default=True)
    has_custom_illustrations = Column(Boolean, default=False)
    has_multi_language = Column(Boolean, default=False)
    has_api_access = Column(Boolean, default=False)
    
    # Billing
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, default=False)
    individual_story_credits = Column(Integer, default=0)  # For pay-per-story users
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    cancelled_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    
    def __repr__(self):
        return f"<Subscription {self.user_id} - {self.tier.value}>"
    
    def can_create_story(self) -> bool:
        """Check if user can create a new story based on subscription limits"""
        if self.stories_per_month == -1:  # Unlimited
            return True
        return self.stories_created_this_month < self.stories_per_month
    
    def can_add_sunshine(self, current_count: int) -> bool:
        """Check if user can add another sunshine profile"""
        if self.sunshines_limit == -1:  # Unlimited
            return True
        return current_count < self.sunshines_limit


# Subscription tier configurations
SUBSCRIPTION_TIERS = {
    SubscriptionTier.FREE: {
        "name": "Free",
        "price": 0,
        "stories_per_month": 3,
        "sunshines_limit": 1,
        "has_pdf_export": False,
        "has_image_generation": True,
        "has_custom_illustrations": False,
        "has_multi_language": False,
        "has_api_access": False,
    },
    SubscriptionTier.BASIC: {
        "name": "Basic",
        "price": 9.99,
        "stories_per_month": 10,
        "sunshines_limit": 3,
        "has_pdf_export": True,
        "has_image_generation": True,
        "has_custom_illustrations": False,
        "has_multi_language": False,
        "has_api_access": False,
    },
    SubscriptionTier.PREMIUM: {
        "name": "Premium",
        "price": 19.99,
        "stories_per_month": 50,
        "sunshines_limit": 10,
        "has_pdf_export": True,
        "has_image_generation": True,
        "has_custom_illustrations": True,
        "has_multi_language": True,
        "has_api_access": False,
    },
    SubscriptionTier.ENTERPRISE: {
        "name": "Enterprise",
        "price": 99.99,
        "stories_per_month": -1,  # Unlimited
        "sunshines_limit": -1,  # Unlimited
        "has_pdf_export": True,
        "has_image_generation": True,
        "has_custom_illustrations": True,
        "has_multi_language": True,
        "has_api_access": True,
    },
}


class SunshinePhoto(Base):
    """Photos associated with Sunshine profiles"""
    __tablename__ = "sunshine_photos"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sunshine_id = Column(String, ForeignKey("sunshines.id", ondelete="CASCADE"), nullable=False)
    family_member_id = Column(String, ForeignKey("family_members.id", ondelete="CASCADE"))
    comfort_item_id = Column(String, ForeignKey("comfort_items.id", ondelete="CASCADE"))
    
    url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    photo_type = Column(String(50), nullable=False)  # profile, gallery, family, comfort_item, object
    description = Column(Text)
    is_primary = Column(Boolean, default=False)
    
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    sunshine = relationship("Sunshine", back_populates="photos")
    family_member = relationship("FamilyMember", back_populates="photos")
    comfort_item = relationship("ComfortItem", back_populates="photos")
    
    def __repr__(self):
        return f"<SunshinePhoto {self.id} - {self.photo_type}>"


class FamilyMember(Base):
    """Family members associated with Sunshine profiles"""
    __tablename__ = "family_members"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sunshine_id = Column(String, ForeignKey("sunshines.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(100), nullable=False)
    relation_type = Column(String(50), nullable=False)  # mother, father, sister, brother, etc.
    relation_custom = Column(String(100))  # For "other" relationship type
    age = Column(Integer)
    description = Column(Text)
    personality_traits = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    sunshine = relationship("Sunshine", back_populates="family_members")
    photos = relationship("SunshinePhoto", back_populates="family_member", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<FamilyMember {self.name} - {self.relation_type}>"


class ComfortItem(Base):
    """Comfort items associated with Sunshine profiles"""
    __tablename__ = "comfort_items"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sunshine_id = Column(String, ForeignKey("sunshines.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(100), nullable=False)
    item_type = Column(String(50), nullable=False)  # toy, blanket, stuffed_animal, etc.
    description = Column(Text)
    significance = Column(Text)  # Why this item is important
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    sunshine = relationship("Sunshine", back_populates="comfort_items")
    photos = relationship("SunshinePhoto", back_populates="comfort_item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ComfortItem {self.name} - {self.item_type}>"


class PersonalityTrait(Base):
    """Personality traits associated with Sunshine profiles"""
    __tablename__ = "personality_traits"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sunshine_id = Column(String, ForeignKey("sunshines.id", ondelete="CASCADE"), nullable=False)
    
    trait = Column(String(100), nullable=False)
    description = Column(Text)
    strength = Column(Integer, default=3)  # 1-5 scale
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    sunshine = relationship("Sunshine", back_populates="personality_traits")
    
    def __repr__(self):
        return f"<PersonalityTrait {self.trait} ({self.strength}/5)>"