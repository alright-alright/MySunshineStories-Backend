"""
Story generation API routes with usage tracking and payment integration
"""
from fastapi import APIRouter, HTTPException, status, Depends, Form
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from app.core.dependencies import CurrentUser, DatabaseSession
from app.services.story_generator import StoryGeneratorService
from app.services.enhanced_story_generator import enhanced_story_generator
from app.services.usage_tracking_service import usage_tracking_service
from app.models.database_models import Story, StoryTone, Sunshine
from app.schemas.story import StoryCreate, StoryResponse

router = APIRouter()

# Initialize services
story_service = StoryGeneratorService()


class GenerateStoryRequest(BaseModel):
    """Request model for story generation"""
    sunshine_id: str = Field(..., description="ID of the Sunshine profile")
    fear_or_challenge: str = Field(..., description="Fear or challenge to address")
    tone: Optional[StoryTone] = Field(default=StoryTone.EMPOWERING)
    language: Optional[str] = Field(default="english")
    include_family: Optional[bool] = Field(default=True)
    include_comfort_items: Optional[bool] = Field(default=True)
    custom_elements: Optional[List[str]] = Field(default=[])


class StoryGenerationResponse(BaseModel):
    """Response model for story generation"""
    story_id: str
    title: str
    story_text: str
    scenes: List[Dict[str, Any]]
    image_urls: List[str]
    reading_time: int
    word_count: int
    usage_type: str  # "subscription", "individual_credit", "free_tier"
    credits_remaining: Optional[int] = None


# ============== Story Generation ==============

@router.post("/generate", response_model=StoryGenerationResponse)
async def generate_story(
    request: GenerateStoryRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """
    Generate a personalized story with enhanced photo-based character consistency
    Uses authenticated user, Sunshine profile, subscription validation, and DALL-E 3
    """
    # Get Sunshine profile first
    sunshine = db.query(Sunshine).filter(
        Sunshine.id == request.sunshine_id,
        Sunshine.user_id == current_user.id
    ).first()
    
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    try:
        # Use enhanced story generator with full photo integration
        result = enhanced_story_generator.generate_personalized_story(
            user=current_user,
            sunshine=sunshine,
            fear_or_challenge=request.fear_or_challenge,
            tone=request.tone,
            db=db,
            include_family=request.include_family,
            include_comfort_items=request.include_comfort_items,
            custom_elements=request.custom_elements
        )
        
        # Get updated usage stats
        usage_stats = usage_tracking_service.get_usage_stats(current_user, db)
        
        return StoryGenerationResponse(
            story_id=result["story_id"],
            title=result["title"],
            story_text=result["story_text"],
            scenes=result["scenes"],
            image_urls=result["image_urls"],
            reading_time=result["reading_time"],
            word_count=result["word_count"],
            usage_type=result["usage_type"],
            credits_remaining=usage_stats.get("stories_remaining", 0)
        )
        
    except ValueError as e:
        # This is a subscription/usage limit error
        error_msg = str(e)
        if "limit" in error_msg.lower() or "payment" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
    except Exception as e:
        # Log error but don't charge user
        print(f"Story generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate story. You have not been charged."
        )


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_story_history(
    current_user: CurrentUser,
    db: DatabaseSession,
    limit: int = 10,
    offset: int = 0
):
    """Get story generation history for current user"""
    stories = usage_tracking_service.get_story_history(
        user=current_user,
        db=db,
        limit=limit,
        offset=offset
    )
    return stories


@router.get("/{story_id}", response_model=Dict[str, Any])
async def get_story(
    story_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Get a specific story by ID"""
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    # Update read count
    story.read_count = (story.read_count or 0) + 1
    story.last_read_at = datetime.now(timezone.utc)
    db.commit()
    
    return {
        "id": story.id,
        "title": story.title,
        "story_text": story.story_text,
        "child_name": story.child_name,
        "age": story.age,
        "fear_or_challenge": story.fear_or_challenge,
        "tone": story.tone.value if story.tone else "empowering",
        "scenes": story.scenes or [],
        "image_urls": story.image_urls or [],
        "pdf_url": story.pdf_url,
        "reading_time": story.reading_time,
        "word_count": story.word_count,
        "is_favorite": story.is_favorite,
        "read_count": story.read_count,
        "created_at": story.created_at,
        "last_read_at": story.last_read_at
    }


@router.put("/{story_id}/favorite")
async def toggle_favorite(
    story_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Toggle favorite status of a story"""
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    story.is_favorite = not story.is_favorite
    db.commit()
    
    return {"is_favorite": story.is_favorite}


@router.delete("/{story_id}")
async def delete_story(
    story_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Delete a story"""
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    db.delete(story)
    db.commit()
    
    return {"message": "Story deleted successfully"}


@router.post("/{story_id}/rate")
async def rate_story(
    story_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    rating: float = Form(..., ge=1, le=5)
):
    """Rate a story"""
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    story.rating = rating
    db.commit()
    
    return {"rating": rating}


# ============== PDF Export ==============

@router.post("/{story_id}/export-pdf")
async def export_story_pdf(
    story_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Export story as PDF (requires subscription feature)"""
    # Check if user has PDF export feature
    can_export, reason = usage_tracking_service.validate_subscription_features(
        user=current_user,
        feature="pdf_export"
    )
    
    if not can_export:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=reason
        )
    
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    # Generate PDF if not already generated
    if not story.pdf_url:
        from app.services.pdf_generator import PDFGeneratorService
        pdf_service = PDFGeneratorService()
        
        # Create PDF
        pdf_path = pdf_service.generate_pdf(
            title=story.title,
            story_text=story.story_text,
            child_name=story.child_name,
            image_urls=story.image_urls or []
        )
        
        # Upload to S3 or save locally
        # For now, save locally
        story.pdf_url = f"/static/pdfs/{story_id}.pdf"
        db.commit()
    
    return {"pdf_url": story.pdf_url}