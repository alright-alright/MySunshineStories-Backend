from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class StoryTone(str, Enum):
    CALM = "calm"
    EMPOWERING = "empowering"
    BEDTIME = "bedtime"
    ADVENTURE = "adventure"

class FamilyMember(BaseModel):
    name: str = Field(..., description="Family member's name")
    relationship: str = Field(..., description="Relationship to child (mom, dad, sister, etc.)")

class StoryRequest(BaseModel):
    child_name: str = Field(..., min_length=1, example="Emma")
    age: Optional[int] = Field(None, ge=2, le=12, example=6)
    fear_or_challenge: str = Field(..., min_length=1, example="afraid of the dark")
    favorite_items: Optional[List[str]] = Field(default=[], example=["teddy bear", "night light"])
    family_members: Optional[List[FamilyMember]] = Field(default=[], example=[
        {"name": "Mom", "relationship": "mother"},
        {"name": "Alex", "relationship": "brother"}
    ])
    tone: Optional[StoryTone] = Field(default=StoryTone.EMPOWERING)
    language: Optional[str] = Field(default="english", example="english")

class StoryScene(BaseModel):
    scene_number: int
    description: str
    image_prompt: str

class StoryResponse(BaseModel):
    story_title: str
    story_text: str
    scenes: List[StoryScene]
    child_name: str
    tone: str

class GeneratedStory(BaseModel):
    story_response: StoryResponse
    pdf_url: str
    created_at: str
