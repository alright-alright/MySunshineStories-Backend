"""
Pydantic schemas for Sunshine (child profile) models
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FamilyRelationship(str, Enum):
    MOTHER = "mother"
    FATHER = "father"
    SISTER = "sister"
    BROTHER = "brother"
    GRANDMOTHER = "grandmother"
    GRANDFATHER = "grandfather"
    AUNT = "aunt"
    UNCLE = "uncle"
    COUSIN = "cousin"
    GUARDIAN = "guardian"
    PET = "pet"
    OTHER = "other"


class PhotoType(str, Enum):
    PROFILE = "profile"
    GALLERY = "gallery"
    FAMILY = "family"
    COMFORT_ITEM = "comfort_item"
    OBJECT = "object"


class PhotoBase(BaseModel):
    """Base schema for photos"""
    id: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    photo_type: PhotoType
    description: Optional[str] = None
    is_primary: bool = False
    uploaded_at: Optional[datetime] = None


class PhotoCreate(BaseModel):
    """Schema for creating photos"""
    photo_type: PhotoType
    description: Optional[str] = None
    is_primary: bool = False


class PhotoResponse(PhotoBase):
    """Schema for photo responses"""
    id: str
    sunshine_id: Optional[str] = None
    family_member_id: Optional[str] = None
    comfort_item_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class FamilyMemberBase(BaseModel):
    """Base schema for family members"""
    name: str
    relationship: FamilyRelationship
    relationship_custom: Optional[str] = None  # For "other" relationship
    age: Optional[int] = None
    description: Optional[str] = None
    personality_traits: List[str] = []


class FamilyMemberCreate(FamilyMemberBase):
    """Schema for creating family members"""
    pass


class FamilyMemberUpdate(BaseModel):
    """Schema for updating family members"""
    name: Optional[str] = None
    relationship: Optional[FamilyRelationship] = None
    relationship_custom: Optional[str] = None
    age: Optional[int] = None
    description: Optional[str] = None
    personality_traits: Optional[List[str]] = None


class FamilyMemberResponse(FamilyMemberBase):
    """Schema for family member responses"""
    id: str
    sunshine_id: str
    photos: List[PhotoResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_orm_model(cls, family_member):
        """Create response from SQLAlchemy model"""
        return cls(
            id=family_member.id,
            sunshine_id=family_member.sunshine_id,
            name=family_member.name,
            relationship=family_member.relation_type,  # Map from database field
            relationship_custom=family_member.relation_custom,
            age=family_member.age,
            description=family_member.description,
            personality_traits=family_member.personality_traits or [],
            photos=family_member.photos if hasattr(family_member, 'photos') else [],
            created_at=family_member.created_at,
            updated_at=family_member.updated_at
        )


class ComfortItemBase(BaseModel):
    """Base schema for comfort items"""
    name: str
    item_type: str  # toy, blanket, stuffed_animal, etc.
    description: Optional[str] = None
    significance: Optional[str] = None  # Why this item is important


class ComfortItemCreate(ComfortItemBase):
    """Schema for creating comfort items"""
    pass


class ComfortItemUpdate(BaseModel):
    """Schema for updating comfort items"""
    name: Optional[str] = None
    item_type: Optional[str] = None
    description: Optional[str] = None
    significance: Optional[str] = None


class ComfortItemResponse(ComfortItemBase):
    """Schema for comfort item responses"""
    id: str
    sunshine_id: str
    photos: List[PhotoResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class PersonalityTraitBase(BaseModel):
    """Base schema for personality traits"""
    trait: str
    description: Optional[str] = None
    strength: int = Field(ge=1, le=5, default=3)  # 1-5 scale


class PersonalityTraitCreate(PersonalityTraitBase):
    """Schema for creating personality traits"""
    pass


class PersonalityTraitResponse(PersonalityTraitBase):
    """Schema for personality trait responses"""
    id: str
    sunshine_id: str
    
    model_config = ConfigDict(from_attributes=True)


class SunshineBase(BaseModel):
    """Base schema for Sunshine profiles"""
    name: str
    birthdate: date
    gender: Gender
    pronouns: Optional[str] = None
    nickname: Optional[str] = None
    favorite_color: Optional[str] = None
    favorite_animal: Optional[str] = None
    favorite_food: Optional[str] = None
    favorite_activity: Optional[str] = None
    fears: List[str] = []
    dreams: List[str] = []
    allergies: List[str] = []
    special_needs: Optional[str] = None
    bedtime_routine: Optional[str] = None
    personality_summary: Optional[str] = None
    additional_notes: Optional[str] = None


class SunshineCreate(SunshineBase):
    """Schema for creating Sunshine profiles"""
    personality_traits: List[PersonalityTraitCreate] = []


class SunshineUpdate(BaseModel):
    """Schema for updating Sunshine profiles"""
    name: Optional[str] = None
    birthdate: Optional[date] = None
    gender: Optional[Gender] = None
    pronouns: Optional[str] = None
    nickname: Optional[str] = None
    favorite_color: Optional[str] = None
    favorite_animal: Optional[str] = None
    favorite_food: Optional[str] = None
    favorite_activity: Optional[str] = None
    fears: Optional[List[str]] = None
    dreams: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    special_needs: Optional[str] = None
    bedtime_routine: Optional[str] = None
    personality_summary: Optional[str] = None
    additional_notes: Optional[str] = None
    is_active: Optional[bool] = None


class SunshineResponse(SunshineBase):
    """Schema for Sunshine responses"""
    id: str
    user_id: str
    age: int  # Calculated from birthdate
    is_active: bool
    photos: List[PhotoResponse] = []
    family_members: List[FamilyMemberResponse] = []
    comfort_items: List[ComfortItemResponse] = []
    personality_traits: List[PersonalityTraitResponse] = []
    stories_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_orm_model(cls, sunshine):
        """Create response from SQLAlchemy model"""
        from datetime import date
        today = date.today()
        age = today.year - sunshine.birthdate.year - ((today.month, today.day) < (sunshine.birthdate.month, sunshine.birthdate.day))
        
        data = {
            "id": sunshine.id,
            "user_id": sunshine.user_id,
            "name": sunshine.name,
            "birthdate": sunshine.birthdate,
            "age": age,
            "gender": sunshine.gender,
            "pronouns": sunshine.pronouns,
            "nickname": sunshine.nickname,
            "favorite_color": sunshine.favorite_color,
            "favorite_animal": sunshine.favorite_animal,
            "favorite_food": sunshine.favorite_food,
            "favorite_activity": sunshine.favorite_activity,
            "fears": sunshine.fears or [],
            "dreams": sunshine.dreams or [],
            "allergies": sunshine.allergies or [],
            "special_needs": sunshine.special_needs,
            "bedtime_routine": sunshine.bedtime_routine,
            "personality_summary": sunshine.personality_summary,
            "additional_notes": sunshine.additional_notes,
            "is_active": sunshine.is_active,
            "photos": [PhotoResponse.model_validate(p) for p in sunshine.photos] if hasattr(sunshine, 'photos') else [],
            "family_members": [FamilyMemberResponse.from_orm_model(fm) for fm in sunshine.family_members] if hasattr(sunshine, 'family_members') else [],
            "comfort_items": [ComfortItemResponse.model_validate(ci) for ci in sunshine.comfort_items] if hasattr(sunshine, 'comfort_items') else [],
            "personality_traits": [PersonalityTraitResponse.model_validate(pt) for pt in sunshine.personality_traits] if hasattr(sunshine, 'personality_traits') else [],
            "stories_count": len(sunshine.stories) if hasattr(sunshine, 'stories') else 0,
            "created_at": sunshine.created_at,
            "updated_at": sunshine.updated_at
        }
        return cls(**data)


class SunshineSummary(BaseModel):
    """Summary schema for listing Sunshine profiles"""
    id: str
    name: str
    nickname: Optional[str] = None
    age: int
    gender: Gender
    profile_photo_url: Optional[str] = None
    stories_count: int = 0
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BulkPhotoUpload(BaseModel):
    """Schema for bulk photo upload response"""
    sunshine_id: str
    uploaded_photos: List[PhotoResponse]
    failed_uploads: List[Dict[str, str]] = []


class CharacterReference(BaseModel):
    """Schema for character reference data used in story generation"""
    sunshine_id: str
    name: str
    age: int
    gender: Gender
    pronouns: str
    physical_description: Dict[str, Any]
    personality_traits: List[str]
    family_members: List[Dict[str, Any]]
    comfort_items: List[str]
    reference_photos: List[str]  # URLs of photos for consistent character generation


# Import at bottom to avoid circular imports
from app.schemas.story import StoryBase

# SunshineResponse.model_rebuild()