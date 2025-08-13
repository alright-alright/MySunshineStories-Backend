"""
Story generation API routes with usage tracking and payment integration
"""
from fastapi import APIRouter, HTTPException, status, Depends, Form, UploadFile, File
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
    id: str  # Frontend expects 'id' field
    story_id: str  # Also keep story_id for compatibility
    title: str
    story_text: str
    scenes: List[Dict[str, Any]]
    image_urls: List[str]
    reading_time: int
    word_count: int
    usage_type: str  # "subscription", "individual_credit", "free_tier"
    credits_remaining: Optional[int] = None


# ============== Story Generation ==============

# TEMPORARY: FormData version of generate endpoint for testing
@router.post("/generate-form", response_model=StoryGenerationResponse)
async def generate_story_form(
    db: DatabaseSession,
    sunshine_id: str = Form(...),
    fear_or_challenge: str = Form(...),
    tone: str = Form(default="empowering"),
    include_family: bool = Form(default=True),
    include_comfort_items: bool = Form(default=True),
    custom_elements: Optional[str] = Form(default=None),
    # Photo uploads (optional for v2)
    additional_child_photos: List[UploadFile] = File(default=[]),
    additional_family_photos: List[UploadFile] = File(default=[]),
    comfort_item_photos: List[UploadFile] = File(default=[])
):
    """
    TEMPORARY: FormData version of story generation for testing
    Accepts multipart/form-data like v3 endpoint
    """
    from datetime import timedelta
    from app.models.database_models import SubscriptionTier
    
    print("🔍 V2 FORM DATA:")
    print(f"🔍 Sunshine ID: {sunshine_id}")
    print(f"🔍 Fear/challenge: {fear_or_challenge}")
    print(f"🔍 Tone: {tone}")
    print(f"🔍 Include family: {include_family}")
    print(f"🔍 Include comfort items: {include_comfort_items}")
    print(f"🔍 Custom elements: {custom_elements}")
    print(f"🔍 Child photos: {len(additional_child_photos)}")
    print(f"🔍 Family photos: {len(additional_family_photos)}")
    print(f"🔍 Comfort photos: {len(comfort_item_photos)}")
    
    # Convert tone string to enum
    try:
        from app.models.database_models import StoryTone
        story_tone = StoryTone(tone.lower())
    except ValueError:
        story_tone = StoryTone.EMPOWERING
    
    # Parse custom elements
    custom_elements_list = []
    if custom_elements:
        custom_elements_list = [elem.strip() for elem in custom_elements.split(",")]
    
    # Use hardcoded test user
    test_user_id = "test-user-id-12345"
    
    # Mock subscription with "free" tier that works
    class MockSubscription:
        def __init__(self):
            self.plan_type = "free"
            self.tier = "free"  # Using "free" which we know works
            self.is_active = True
            self.status = "active"
            self.is_valid = True
            self.stories_limit = 999
            self.stories_used = 0
            self.stories_remaining = 999
            self.sunshines_limit = 999  # CRITICAL: Needed for save!
            # Fields needed for FREE tier validation
            self.individual_story_credits = 10
            self.stories_per_month = 5
            self.stories_created_this_month = 0
            self.current_period_start = datetime.now(timezone) - timedelta(days=1)
            self.current_period_end = datetime.now(timezone) + timedelta(days=30)
            self.can_generate_stories = True
            self.has_payment_method = True
            self.trial_expired = False
    
    # Mock user object
    class MockUser:
        def __init__(self):
            self.id = test_user_id
            self.email = "test@example.com"
            self.full_name = "Test User"
            self.subscription = MockSubscription()
            self.is_active = True
            self.is_verified = True
            self.is_admin = False
            self.created_at = datetime.now(timezone) - timedelta(days=30)
            self.last_login = datetime.now(timezone)
            self.sunshines = []  # CRITICAL: Needed for story save!
    
    mock_user = MockUser()
    
    # Get Sunshine profile
    sunshine = db.query(Sunshine).filter(
        Sunshine.id == sunshine_id,
        Sunshine.user_id == test_user_id
    ).first()
    
    if not sunshine:
        print(f"❌ V2 FORM: Sunshine not found: {sunshine_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sunshine profile not found: {sunshine_id}"
        )
    
    print(f"✅ V2 FORM: Found sunshine: {sunshine.name}")
    
    try:
        # Generate story
        result = enhanced_story_generator.generate_personalized_story(
            user=mock_user,
            sunshine=sunshine,
            fear_or_challenge=fear_or_challenge,
            tone=story_tone,
            db=db,
            include_family=include_family,
            include_comfort_items=include_comfort_items,
            custom_elements=custom_elements_list if custom_elements_list else None
        )
        
        print(f"✅ V2 FORM: Story generated successfully!")
        
        # Get usage stats
        usage_stats = usage_tracking_service.get_usage_stats(mock_user, db)
        
        return StoryGenerationResponse(
            id=result["story_id"],  # Frontend expects 'id'
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
        
    except Exception as e:
        print(f"❌ V2 FORM: Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Story generation failed: {str(e)}"
        )

@router.post("/generate", response_model=StoryGenerationResponse)
async def generate_story(
    request: GenerateStoryRequest,
    # current_user: CurrentUser,  # TEMPORARILY DISABLED FOR TESTING
    db: DatabaseSession
):
    # Log raw request for debugging
    try:
        print(f"🔍 V2 RAW REQUEST: {request}")
        print(f"🔍 V2 REQUEST DICT: {request.dict() if hasattr(request, 'dict') else 'No dict method'}")
    except Exception as e:
        print(f"❌ V2 Error logging request: {e}")
    """
    Generate a personalized story with enhanced photo-based character consistency
    TEMPORARILY: Auth disabled for testing - using mock user
    """
    from datetime import timedelta
    from app.models.database_models import SubscriptionTier
    
    # Debug logging for request data
    print("🔍 V2 REQUEST DATA:")
    print(f"🔍 Request type: {type(request)}")
    print(f"🔍 Sunshine ID: {request.sunshine_id}")
    print(f"🔍 Fear/challenge: {request.fear_or_challenge}")
    print(f"🔍 Tone: {request.tone}")
    print(f"🔍 Include family: {request.include_family}")
    print(f"🔍 Include comfort items: {request.include_comfort_items}")
    print(f"🔍 Custom elements: {request.custom_elements}")
    print("🔍 V2 validation starting...")
    
    # TEMPORARY: Use hardcoded test user
    test_user_id = "test-user-id-12345"
    print(f"🔍 V2 MAIN: TEMP - Generating story for test user: {test_user_id}")
    
    # Mock subscription object
    class MockSubscription:
        def __init__(self):
            self.plan_type = "free"
            self.tier = SubscriptionTier.FREE  # Use actual enum value!
            self.is_active = True
            self.status = "active"
            self.is_valid = True
            self.stories_limit = 999
            self.stories_used = 0
            self.stories_remaining = 999
            self.sunshines_limit = 999  # CRITICAL: Needed for save!
            # Fields needed for FREE tier validation
            self.individual_story_credits = 10
            self.stories_per_month = 5
            self.stories_created_this_month = 0
            self.current_period_start = datetime.now(timezone) - timedelta(days=1)
            self.current_period_end = datetime.now(timezone) + timedelta(days=30)
            self.can_generate_stories = True
            self.has_payment_method = True
            self.trial_expired = False
    
    # Mock user object
    class MockUser:
        def __init__(self):
            self.id = test_user_id
            self.email = "test@example.com"
            self.full_name = "Test User"
            self.subscription = MockSubscription()
            self.is_active = True
            self.is_verified = True
            self.is_admin = False
            self.created_at = datetime.now(timezone) - timedelta(days=30)
            self.last_login = datetime.now(timezone)
            self.sunshines = []  # CRITICAL: Needed for story save!
    
    current_user = MockUser()  # Use mock user instead of real auth
    # Get Sunshine profile first
    sunshine = db.query(Sunshine).filter(
        Sunshine.id == request.sunshine_id,
        Sunshine.user_id == test_user_id  # TEMP: Use test user ID
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
            id=result["story_id"],  # Frontend expects 'id'
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


# TEMPORARY: Test version without auth for story generation
@router.post("/generate-test", response_model=StoryGenerationResponse)
async def generate_story_test(
    request: GenerateStoryRequest,
    db: DatabaseSession
):
    """
    TEMPORARY: Test version of story generation without authentication
    """
    from datetime import timedelta
    
    # Use hardcoded test user
    test_user_id = "test-user-id-12345"
    print(f"🔍 V2 TEST: Generating story for test user: {test_user_id}")
    print(f"🔍 V2 TEST: Request data - sunshine_id: {request.sunshine_id}, fear: {request.fear_or_challenge}")
    
    # Mock subscription object with all authorization attributes
    class MockSubscription:
        def __init__(self):
            self.plan_type = "free"
            self.tier = SubscriptionTier.FREE  # Use actual enum value!
            self.is_active = True
            self.status = "active"
            self.is_valid = True
            self.stories_limit = 999
            self.stories_used = 0
            self.stories_remaining = 999
            self.sunshines_limit = 999  # CRITICAL: Needed for save!
            # Fields needed for FREE tier validation
            self.individual_story_credits = 10
            self.stories_per_month = 5
            self.stories_created_this_month = 0
            self.current_period_start = datetime.now(timezone) - timedelta(days=1)
            self.current_period_end = datetime.now(timezone) + timedelta(days=30)
            self.can_generate_stories = True
            self.has_payment_method = True
            self.trial_expired = False
    
    # Mock user object with full authorization
    class MockUser:
        def __init__(self):
            self.id = test_user_id
            self.email = "test@example.com"
            self.full_name = "Test User"
            self.subscription = MockSubscription()
            self.is_active = True
            self.is_verified = True
            self.is_admin = False
            self.created_at = datetime.now(timezone) - timedelta(days=30)
            self.last_login = datetime.now(timezone)
            self.sunshines = []  # CRITICAL: Needed for story save!
    
    mock_user = MockUser()
    
    print(f"🔍 V2 TEST: Mock user created with subscription tier: {mock_user.subscription.tier}")
    
    # Get Sunshine profile - using test user ID
    sunshine = db.query(Sunshine).filter(
        Sunshine.id == request.sunshine_id,
        Sunshine.user_id == test_user_id  # Use test user ID
    ).first()
    
    if not sunshine:
        print(f"❌ V2 TEST: Sunshine profile not found for ID: {request.sunshine_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sunshine profile not found. ID: {request.sunshine_id}, User: {test_user_id}"
        )
    
    print(f"✅ V2 TEST: Found sunshine profile: {sunshine.name}")
    
    try:
        # Use enhanced story generator with mock user
        result = enhanced_story_generator.generate_personalized_story(
            user=mock_user,
            sunshine=sunshine,
            fear_or_challenge=request.fear_or_challenge,
            tone=request.tone,
            db=db,
            include_family=request.include_family,
            include_comfort_items=request.include_comfort_items,
            custom_elements=request.custom_elements
        )
        
        print(f"✅ V2 TEST: Story generated successfully!")
        
        # Get updated usage stats
        usage_stats = usage_tracking_service.get_usage_stats(mock_user, db)
        
        return StoryGenerationResponse(
            id=result["story_id"],  # Frontend expects 'id'
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
        print(f"❌ V2 TEST: ValueError - {error_msg}")
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
        print(f"❌ V2 TEST: Story generation failed: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate story: {str(e)}"
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