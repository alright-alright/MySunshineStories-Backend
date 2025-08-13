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
        
        # ENSURE ALL FIELDS ARE SAFE FOR FRONTEND
        return StoryGenerationResponse(
            id=result.get("story_id", ""),  # Frontend expects 'id'
            story_id=result.get("story_id", ""),
            title=result.get("title", "Untitled Story"),
            story_text=result.get("story_text", ""),  # CRITICAL: Never None
            scenes=result.get("scenes", []),
            image_urls=result.get("image_urls", []),
            reading_time=result.get("reading_time", 5),
            word_count=result.get("word_count", 0),
            usage_type=result.get("usage_type", "free_tier"),
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
        
        # ENSURE ALL FIELDS ARE SAFE FOR FRONTEND
        return StoryGenerationResponse(
            id=result.get("story_id", ""),  # Frontend expects 'id'
            story_id=result.get("story_id", ""),
            title=result.get("title", "Untitled Story"),
            story_text=result.get("story_text", ""),  # CRITICAL: Never None
            scenes=result.get("scenes", []),
            image_urls=result.get("image_urls", []),
            reading_time=result.get("reading_time", 5),
            word_count=result.get("word_count", 0),
            usage_type=result.get("usage_type", "free_tier"),
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
        
        # ENSURE ALL FIELDS ARE SAFE FOR FRONTEND
        return StoryGenerationResponse(
            id=result.get("story_id", ""),  # Frontend expects 'id'
            story_id=result.get("story_id", ""),
            title=result.get("title", "Untitled Story"),
            story_text=result.get("story_text", ""),  # CRITICAL: Never None
            scenes=result.get("scenes", []),
            image_urls=result.get("image_urls", []),
            reading_time=result.get("reading_time", 5),
            word_count=result.get("word_count", 0),
            usage_type=result.get("usage_type", "free_tier"),
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


# SIMPLE DEBUG ENDPOINT - NO AUTH REQUIRED
@router.get("/all")
async def list_all_stories(db: DatabaseSession):
    """List ALL stories in database for debugging"""
    print(f"🔍 CHECKING DATABASE FOR ALL STORIES...")
    
    # Get total count
    total_count = db.query(Story).count()
    print(f"📊 TOTAL STORIES IN DATABASE: {total_count}")
    
    # Get first 20 stories
    stories = db.query(Story).order_by(Story.created_at.desc()).limit(20).all()
    
    # Log each story
    for s in stories:
        print(f"📖 Story: {s.id} | {s.title} | User: {s.user_id} | Created: {s.created_at}")
    
    # If no stories, check if database is connected
    if total_count == 0:
        print(f"⚠️ NO STORIES IN DATABASE!")
        print(f"⚠️ Checking database connection...")
        try:
            # Try a simple query to test connection
            from app.models.database_models import User
            user_count = db.query(User).count()
            print(f"✅ Database connected. Users in DB: {user_count}")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
    
    return {
        "total_count": total_count,
        "database_status": "connected" if total_count >= 0 else "error",
        "stories": [
            {
                "id": s.id,
                "title": s.title or "No Title",
                "user_id": s.user_id,
                "sunshine_id": s.sunshine_id,
                "created_at": s.created_at.isoformat() if s.created_at else "Unknown",
                "child_name": s.child_name or "Unknown",
                "word_count": s.word_count or 0
            } for s in stories
        ]
    }

# TEMPORARY: Debug endpoint to list all stories
@router.get("/debug/all-stories")
async def debug_all_stories(
    db: DatabaseSession,
    limit: int = 20
):
    """TEMPORARY: List all stories for debugging"""
    stories = db.query(Story).order_by(Story.created_at.desc()).limit(limit).all()
    
    print(f"📚 DEBUG: Found {len(stories)} stories in database")
    
    result = []
    for story in stories:
        print(f"📖 Story: {story.id} - {story.title} (user: {story.user_id})")
        result.append({
            "id": story.id,
            "title": story.title,
            "user_id": story.user_id,
            "sunshine_id": story.sunshine_id,
            "created_at": story.created_at,
            "child_name": story.child_name,
            "word_count": story.word_count
        })
    
    return {
        "total_stories": len(stories),
        "stories": result
    }

# TEST DATABASE WRITE CAPABILITY
@router.get("/test-db-write")
async def test_database_write(db: DatabaseSession):
    """Test if we can write to the database"""
    import uuid
    from datetime import datetime, timezone
    
    print(f"🔍 TESTING DATABASE WRITE...")
    
    try:
        # Create a test story
        test_id = f"test-{str(uuid.uuid4())[:8]}"
        test_story = Story(
            id=test_id,
            user_id="test-user-db-check",
            title=f"Test Story {datetime.now().isoformat()}",
            story_text="This is a test story to verify database write capability.",
            tone=StoryTone.EMPOWERING,
            child_name="Test Child",
            age=5,
            fear_or_challenge="Testing database",
            reading_time=1,
            word_count=10,
            created_at=datetime.now(timezone.utc)
        )
        
        print(f"📝 Adding test story: {test_id}")
        db.add(test_story)
        
        print(f"💾 Committing to database...")
        db.commit()
        
        print(f"🔄 Refreshing object...")
        db.refresh(test_story)
        
        print(f"✅ Test story saved: {test_story.id}")
        
        # Verify it's in the database
        verify = db.query(Story).filter(Story.id == test_id).first()
        
        if verify:
            print(f"✅ VERIFIED: Test story found in database")
            # Clean up - delete test story
            db.delete(verify)
            db.commit()
            print(f"🧹 Test story cleaned up")
            
            return {
                "status": "SUCCESS",
                "message": "Database write test successful",
                "test_id": test_id,
                "database_writable": True
            }
        else:
            print(f"❌ Test story NOT found after save")
            return {
                "status": "FAILED",
                "message": "Story saved but not found in database",
                "test_id": test_id,
                "database_writable": False
            }
            
    except Exception as e:
        print(f"❌ Database write test failed: {e}")
        import traceback
        print(traceback.format_exc())
        
        try:
            db.rollback()
        except:
            pass
            
        return {
            "status": "ERROR",
            "message": str(e),
            "error_type": type(e).__name__,
            "database_writable": False
        }

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
    """Get a specific story by ID - ROBUST VERSION"""
    print(f"🔍 LOOKING FOR: {story_id}")
    print(f"🔍 Current user: {current_user.id}")
    
    # First check if story exists at all (NO USER FILTER)
    story = db.query(Story).filter(Story.id == story_id).first()
    
    if not story:
        print(f"❌ STORY NOT FOUND IN DATABASE")
        # List recent stories for debugging
        recent = db.query(Story).order_by(Story.created_at.desc()).limit(5).all()
        print(f"🔍 RECENT STORIES IN DB:")
        for s in recent:
            print(f"  - ID: {s.id}")
            print(f"    Title: {s.title}")
            print(f"    User: {s.user_id}")
            print(f"    Created: {s.created_at}")
        
        # Also check total count
        total_count = db.query(Story).count()
        print(f"🔍 TOTAL STORIES IN DATABASE: {total_count}")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story not found. ID: {story_id}"
        )
    
    # Story found - log details
    print(f"✅ FOUND STORY: {story.title}")
    print(f"  📖 Story ID: {story.id}")
    print(f"  👤 Story User ID: {story.user_id}")
    print(f"  👤 Current User ID: {current_user.id}")
    print(f"  🔍 User Match: {story.user_id == current_user.id}")
    
    # FOR NOW: BYPASS USER CHECK - return any found story
    print(f"⚠️ BYPASSING USER CHECK FOR TESTING")
    
    # Update read count
    story.read_count = (story.read_count or 0) + 1
    story.last_read_at = datetime.now(timezone.utc)
    db.commit()
    
    print(f"📖 RETURNING STORY: {story.title} (ID: {story.id})")
    
    # ENSURE ALL FIELDS ARE NEVER None FOR FRONTEND
    return {
        "id": story.id or "",
        "title": story.title or "Untitled Story",
        "story_text": story.story_text or "",  # CRITICAL: Must be string, not None
        "child_name": story.child_name or "",
        "age": story.age or 0,
        "fear_or_challenge": story.fear_or_challenge or "",
        "tone": story.tone.value if story.tone else "empowering",
        "scenes": story.scenes or [],
        "image_urls": story.image_urls or [],
        "pdf_url": story.pdf_url or "",
        "reading_time": story.reading_time or 5,
        "word_count": story.word_count or 0,
        "is_favorite": story.is_favorite or False,
        "read_count": story.read_count or 0,
        "created_at": story.created_at.isoformat() if story.created_at else "",
        "last_read_at": story.last_read_at.isoformat() if story.last_read_at else None
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


# SIMPLIFIED GET ENDPOINT WITHOUT AUTH FOR TESTING
@router.get("/simple/{story_id}")
async def get_story_simple(
    story_id: str,
    db: DatabaseSession
):
    """SIMPLE: Get story without auth - for testing"""
    print(f"🔍 SIMPLE GET: Looking for {story_id}")
    
    story = db.query(Story).filter(Story.id == story_id).first()
    
    if not story:
        # Debug: show what's actually in the database
        all_stories = db.query(Story).all()
        print(f"❌ Story {story_id} not found")
        print(f"📚 Database has {len(all_stories)} stories total")
        if all_stories:
            print(f"📚 Sample IDs: {[s.id for s in all_stories[:3]]}")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story {story_id} not found"
        )
    
    print(f"✅ FOUND: {story.title} (user: {story.user_id})")
    
    # ENSURE ALL FIELDS ARE NEVER None FOR FRONTEND
    return {
        "id": story.id or "",
        "title": story.title or "Untitled Story",
        "story_text": story.story_text or "",  # CRITICAL: Must be string, not None
        "child_name": story.child_name or "",
        "age": story.age or 0,
        "fear_or_challenge": story.fear_or_challenge or "",
        "tone": story.tone.value if story.tone else "empowering",
        "scenes": story.scenes or [],
        "image_urls": story.image_urls or [],
        "reading_time": story.reading_time or 5,
        "word_count": story.word_count or 0,
        "created_at": story.created_at.isoformat() if story.created_at else ""
    }

# TEMPORARY: Test endpoint without auth to debug story retrieval
@router.get("/test/{story_id}")
async def get_story_test(
    story_id: str,
    db: DatabaseSession
):
    """TEMPORARY: Get a story by ID without authentication for debugging"""
    print(f"🔍 TEST GET STORY: Looking for story ID: {story_id}")
    
    # Query without any user filter
    story = db.query(Story).filter(Story.id == story_id).first()
    
    if not story:
        print(f"❌ Story not found: {story_id}")
        # List all stories for debugging
        all_stories = db.query(Story).order_by(Story.created_at.desc()).limit(20).all()
        print(f"📚 All stories in database (newest first, max 20):")
        for s in all_stories:
            print(f"  - ID: {s.id}")
            print(f"    Title: {s.title}")
            print(f"    User: {s.user_id}")
            print(f"    Created: {s.created_at}")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story not found. ID: {story_id}. Check server logs for available stories."
        )
    
    print(f"✅ Found story: {story.title}")
    print(f"📖 Story details:")
    print(f"  - ID: {story.id}")
    print(f"  - User ID: {story.user_id}")
    print(f"  - Title: {story.title}")
    print(f"  - Created: {story.created_at}")
    
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
        "last_read_at": story.last_read_at,
        "user_id": story.user_id,  # Include for debugging
        "sunshine_id": story.sunshine_id  # Include for debugging
    }

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