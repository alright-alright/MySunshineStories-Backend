"""
User service for database operations
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import uuid

from app.models.database_models import User, Subscription, SubscriptionTier, SUBSCRIPTION_TIERS
from app.schemas.user import UserCreate, UserOAuthCreate
from app.core.security import get_password_hash, verify_password


class UserService:
    """Service for user-related database operations"""
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """
        Create a new user with email/password
        """
        # Check if user already exists
        existing_user = db.query(User).filter(
            User.email == user_data.email
        ).first()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            username=user_data.username or user_data.email.split('@')[0],
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password) if user_data.password else None,
            is_active=True,
            is_verified=False,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(user)
        
        # Create free subscription for new user
        subscription = UserService.create_subscription(db, user.id)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def create_oauth_user(db: Session, user_data: UserOAuthCreate) -> User:
        """
        Create or update a user from OAuth login
        """
        # Check if user exists by OAuth ID
        if user_data.google_id:
            user = db.query(User).filter(User.google_id == user_data.google_id).first()
            if user:
                # Update last login
                user.last_login = datetime.now(timezone.utc)
                db.commit()
                return user
        
        if user_data.apple_id:
            user = db.query(User).filter(User.apple_id == user_data.apple_id).first()
            if user:
                # Update last login
                user.last_login = datetime.now(timezone.utc)
                db.commit()
                return user
        
        # Check if user exists by email
        user = db.query(User).filter(User.email == user_data.email).first()
        if user:
            # Link OAuth account to existing user
            if user_data.google_id:
                user.google_id = user_data.google_id
            if user_data.apple_id:
                user.apple_id = user_data.apple_id
            if user_data.avatar_url:
                user.avatar_url = user_data.avatar_url
            user.last_login = datetime.now(timezone.utc)
            db.commit()
            return user
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=user_data.email,
            username=user_data.username or user_data.email.split('@')[0],
            full_name=user_data.full_name,
            google_id=user_data.google_id,
            apple_id=user_data.apple_id,
            avatar_url=user_data.avatar_url,
            is_active=True,
            is_verified=True,  # OAuth users are auto-verified
            created_at=datetime.now(timezone.utc),
            last_login=datetime.now(timezone.utc)
        )
        
        db.add(user)
        
        # Create free subscription for new user
        subscription = UserService.create_subscription(db, user.id)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email/password
        """
        user = db.query(User).filter(User.email == email).first()
        
        if not user or not user.hashed_password:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        return user
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get a user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def create_subscription(db: Session, user_id: str, tier: SubscriptionTier = SubscriptionTier.FREE) -> Subscription:
        """
        Create a subscription for a user
        """
        # Check if subscription already exists
        existing_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).first()
        
        if existing_sub:
            return existing_sub
        
        # Get tier configuration
        tier_config = SUBSCRIPTION_TIERS[tier]
        
        # Create subscription
        subscription = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tier=tier,
            status="active",
            stories_per_month=tier_config["stories_per_month"],
            stories_created_this_month=0,
            sunshines_limit=tier_config["sunshines_limit"],
            has_pdf_export=tier_config["has_pdf_export"],
            has_image_generation=tier_config["has_image_generation"],
            has_custom_illustrations=tier_config["has_custom_illustrations"],
            has_multi_language=tier_config["has_multi_language"],
            has_api_access=tier_config["has_api_access"],
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(subscription)
        
        return subscription
    
    @staticmethod
    def update_user_profile(
        db: Session, 
        user: User, 
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> User:
        """Update user profile information"""
        if username:
            # Check if username is taken
            existing = db.query(User).filter(
                User.username == username,
                User.id != user.id
            ).first()
            if existing:
                raise ValueError("Username already taken")
            user.username = username
        
        if full_name is not None:
            user.full_name = full_name
        
        if avatar_url is not None:
            user.avatar_url = avatar_url
        
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        
        return user