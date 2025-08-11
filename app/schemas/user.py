"""
Pydantic schemas for User models
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: Optional[str] = None  # Optional for OAuth users


class UserOAuthCreate(UserBase):
    google_id: Optional[str] = None
    apple_id: Optional[str] = None
    avatar_url: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserInDB(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class User(UserInDB):
    pass


class UserWithSubscription(User):
    subscription: Optional["SubscriptionResponse"] = None
    sunshines: List["SunshineBase"] = []


# Import at bottom to avoid circular imports
from app.schemas.subscription import SubscriptionResponse
from app.schemas.sunshine import SunshineBase

UserWithSubscription.model_rebuild()