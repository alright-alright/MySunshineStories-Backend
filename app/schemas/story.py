"""
Pydantic schemas for Story models
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class StoryTone(str, Enum):
    CALM = "calm"
    EMPOWERING = "empowering"
    BEDTIME = "bedtime"
    ADVENTURE = "adventure"


class Scene(BaseModel):
    scene_number: int
    description: str
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None


class StoryBase(BaseModel):
    title: str
    child_name: str
    age: int
    tone: StoryTone


class StoryCreate(BaseModel):
    sunshine_id: Optional[str] = None
    child_name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=2, le=18)
    fear_or_challenge: str = Field(..., min_length=1, max_length=500)
    favorite_items: Optional[str] = ""
    family_members: Optional[str] = ""
    tone: StoryTone = StoryTone.EMPOWERING


class StoryUpdate(BaseModel):
    rating: Optional[float] = Field(None, ge=1, le=5)
    is_favorite: Optional[bool] = None


class StoryInDB(StoryBase):
    id: str
    user_id: str
    sunshine_id: Optional[str]
    story_text: str
    fear_or_challenge: Optional[str]
    favorite_items: List[str]
    family_members: Dict[str, str]
    scenes: List[Scene]
    image_urls: List[str]
    pdf_url: Optional[str]
    reading_time: int
    word_count: Optional[int]
    rating: Optional[float]
    is_favorite: bool
    read_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_read_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class StoryResponse(StoryInDB):
    pass


class GeneratedStory(BaseModel):
    """Response model for story generation"""
    story_response: Dict
    pdf_url: str
    created_at: datetime