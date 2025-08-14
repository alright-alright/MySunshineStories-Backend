"""
Enhanced Story Generation API with Direct Photo Upload
Provides advanced story generation with real-time photo analysis
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import json

from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.models.database_models import User, Story, StoryTone, Sunshine
from sqlalchemy.orm import Session
from typing import Annotated
from app.services.enhanced_story_generator import enhanced_story_generator, CharacterProfile
from app.services.usage_tracking_service import usage_tracking_service
from app.services.image_generator import resize_uploaded_image, validate_image_file

# Type aliases for FastAPI dependencies
CurrentUser = Annotated[User, Depends(get_current_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]
from pydantic import BaseModel, Field

router = APIRouter()


class EnhancedStoryResponse(BaseModel):
    """Response model for enhanced story generation"""
    id: str  # Frontend expects 'id' field
    story_id: str  # Also keep story_id for compatibility
    title: str
    story_text: str
    scenes: List[Dict[str, Any]]
    image_urls: List[str]
    reading_time: int
    word_count: int
    usage_type: str
    credits_remaining: Optional[int] = None
    character_profiles: Dict[str, Any]
    generation_quality: str  # "standard" or "premium"


# Main endpoint - BOTH URLs for frontend compatibility
@router.post("/create-with-photos", response_model=EnhancedStoryResponse)
@router.post("/generate-with-photos", response_model=EnhancedStoryResponse)
async def generate_story_with_photos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sunshine_id: str = Form(...),
    fear_or_challenge: str = Form(...),
    tone: str = Form(default="empowering"),
    include_family: bool = Form(default=True),
    include_comfort_items: bool = Form(default=True),
    custom_elements: Optional[str] = Form(default=None),
    # Photo uploads for real-time character analysis
    additional_child_photos: List[UploadFile] = File(default=[]),
    additional_family_photos: List[UploadFile] = File(default=[]),
    comfort_item_photos: List[UploadFile] = File(default=[])
):
    """
    Generate story with photos for authenticated user
    Note: Both /create-with-photos and /generate-with-photos routes point here
    Frontend uses /create-with-photos, keeping both for compatibility
    """
    print(f"🔍 V3 ENHANCED: Generating story for authenticated user: {current_user.id}")
    print(f"🔍 V3 ENHANCED: Form data - sunshine_id: {sunshine_id}, fear: {fear_or_challenge}, tone: {tone}")
    
    # TEMPORARY: Add mock subscription if user doesn't have one
    if not hasattr(current_user, 'subscription') or not current_user.subscription:
        print(f"⚠️ User has no subscription, adding mock subscription for testing")
        from app.models.database_models import Subscription, SubscriptionTier
        from datetime import datetime, timezone, timedelta
        
        # Create a mock subscription object
        mock_subscription = Subscription(
            id=f"mock-sub-{current_user.id}",
            user_id=current_user.id,
            tier=SubscriptionTier.FREE,
            status="active",
            is_active=True,
            stories_per_month=10,
            stories_created_this_month=0,
            current_period_start=datetime.now(timezone.utc) - timedelta(days=1),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            created_at=datetime.now(timezone.utc)
        )
        current_user.subscription = mock_subscription
        print(f"✅ Added mock FREE subscription for user")
    
    # Debug logging to trace authorization
    print(f"🔍 V3 DEBUG: Starting story generation with authenticated user...")
    print(f"🔍 V3 User ID: {current_user.id}")
    print(f"🔍 V3 User email: {current_user.email}")
    print(f"🔍 V3 User is_active: {getattr(current_user, 'is_active', 'N/A')}")
    print(f"🔍 V3 User is_verified: {getattr(current_user, 'is_verified', 'N/A')}")
    
    if hasattr(current_user, 'subscription') and current_user.subscription:
        print(f"🔍 V3 DEBUG: Checking subscription details...")
        print(f"🔍 V3 Subscription status: {current_user.subscription.status}")
        print(f"🔍 V3 Subscription tier: {current_user.subscription.tier}")
        print(f"🔍 V3 Subscription plan_type: {getattr(current_user.subscription, 'plan_type', 'N/A')}")
        print(f"🔍 V3 Subscription is_active: {current_user.subscription.is_active}")
    else:
        print(f"🔍 V3 DEBUG: User has no subscription, using defaults")
    
    print(f"🔍 DEBUG: Calling story generation implementation...")
    
    # Call the implementation function with authenticated user
    return await generate_story_with_photos_impl(
        current_user=current_user,
        db=db,
        sunshine_id=sunshine_id,
        fear_or_challenge=fear_or_challenge,
        tone=tone,
        include_family=include_family,
        include_comfort_items=include_comfort_items,
        custom_elements=custom_elements,
        additional_child_photos=additional_child_photos,
        additional_family_photos=additional_family_photos,
        comfort_item_photos=comfort_item_photos
    )


# Original function renamed - implementation with auth
async def generate_story_with_photos_impl(
    current_user: User,
    db: Session,
    sunshine_id: str,
    fear_or_challenge: str,
    tone: str = "empowering",
    include_family: bool = True,
    include_comfort_items: bool = True,
    custom_elements: Optional[str] = None,
    # Photo uploads for real-time character analysis
    additional_child_photos: List[UploadFile] = [],
    additional_family_photos: List[UploadFile] = [],
    comfort_item_photos: List[UploadFile] = []
):
    """
    INTERNAL: Implementation function with auth parameter
    """
    # Get Sunshine profile with detailed debugging
    print(f"🔍 Looking for Sunshine ID: {sunshine_id}")
    print(f"🔍 Current user ID: {current_user.id}")
    
    # TEMPORARY FIX: Allow access to test Sunshine profiles
    # Check if this is a test Sunshine (belongs to test-user-id-12345)
    test_user_id = "test-user-id-12345"
    
    # First try to get the Sunshine by ID only
    sunshine = db.query(Sunshine).filter(Sunshine.id == sunshine_id).first()
    
    if sunshine:
        print(f"✅ Sunshine found with ID {sunshine_id}, belongs to user: {sunshine.user_id}")
        
        # Check if it's a test Sunshine or belongs to current user
        if sunshine.user_id == test_user_id:
            print(f"🔧 Using TEST Sunshine profile (owner: {test_user_id})")
            # Allow access to test Sunshine for any authenticated user
        elif sunshine.user_id != current_user.id:
            print(f"❌ Sunshine belongs to different user: {sunshine.user_id} != {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to access this Sunshine profile"
            )
        else:
            print(f"✅ Sunshine belongs to current user")
    else:
        print(f"❌ Sunshine profile not found with ID: {sunshine_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sunshine profile not found with ID: {sunshine_id}"
        )
    
    # Parse custom elements
    custom_elements_list = []
    if custom_elements:
        custom_elements_list = [elem.strip() for elem in custom_elements.split(",")]
    
    # Convert tone string to enum
    try:
        story_tone = StoryTone(tone.lower())
    except ValueError:
        story_tone = StoryTone.EMPOWERING
    
    # Process additional photos if provided
    enhanced_profiles = {}
    
    # Process additional child photos for better character consistency
    if additional_child_photos:
        for i, photo in enumerate(additional_child_photos[:3]):  # Limit to 3 additional photos
            if photo and photo.filename:
                try:
                    photo_bytes = await photo.read()
                    if validate_image_file(photo_bytes):
                        resized_photo = resize_uploaded_image(photo_bytes)
                        # Analyze for additional character details
                        additional_description = enhanced_story_generator.photo_processor.analyze_photo(
                            resized_photo,
                            sunshine.name,
                            f"child photo {i+1}"
                        )
                        if sunshine.name not in enhanced_profiles:
                            enhanced_profiles[sunshine.name] = []
                        enhanced_profiles[sunshine.name].append(additional_description)
                except Exception as e:
                    print(f"Error processing additional child photo {i}: {e}")
    
    # Process additional family photos
    if additional_family_photos and sunshine.family_members:
        for i, photo in enumerate(additional_family_photos[:len(sunshine.family_members)]):
            if photo and photo.filename and i < len(sunshine.family_members):
                try:
                    photo_bytes = await photo.read()
                    if validate_image_file(photo_bytes):
                        resized_photo = resize_uploaded_image(photo_bytes)
                        family_member = sunshine.family_members[i]
                        additional_description = enhanced_story_generator.photo_processor.analyze_photo(
                            resized_photo,
                            family_member.name,
                            family_member.relation_type
                        )
                        if family_member.name not in enhanced_profiles:
                            enhanced_profiles[family_member.name] = []
                        enhanced_profiles[family_member.name].append(additional_description)
                except Exception as e:
                    print(f"Error processing family photo {i}: {e}")
    
    # Process comfort item photos for scene enrichment
    comfort_item_descriptions = []
    if comfort_item_photos:
        for i, photo in enumerate(comfort_item_photos[:3]):
            if photo and photo.filename:
                try:
                    photo_bytes = await photo.read()
                    if validate_image_file(photo_bytes):
                        resized_photo = resize_uploaded_image(photo_bytes)
                        # Analyze comfort item for story integration
                        item_description = enhanced_story_generator.photo_processor.analyze_photo(
                            resized_photo,
                            f"comfort item {i+1}",
                            "object"
                        )
                        comfort_item_descriptions.append(item_description)
                except Exception as e:
                    print(f"Error processing comfort item photo {i}: {e}")
    
    # Merge comfort item descriptions with custom elements
    if comfort_item_descriptions:
        custom_elements_list.extend(comfort_item_descriptions)
    
    try:
        print(f"🚀 STARTING STORY GENERATION PROCESS...")
        print(f"🚀 User: {current_user.id}")
        print(f"🚀 Sunshine: {sunshine.name} (ID: {sunshine.id})")
        
        # Temporarily enhance character profiles with additional photo data
        if enhanced_profiles:
            # Store original profiles
            original_profiles = enhanced_story_generator.character_profiles.copy()
            
            # Build enhanced profiles
            enhanced_story_generator._build_character_profiles(sunshine, include_family)
            
            # Merge additional photo descriptions
            for name, descriptions in enhanced_profiles.items():
                profile = enhanced_story_generator.character_profiles.get(name.lower())
                if profile:
                    # Combine multiple photo descriptions for richer character detail
                    combined_description = f"{profile.visual_description}. Additional details: {'. '.join(descriptions)}"
                    profile.visual_description = combined_description
        
        print(f"🚀 CALLING STORY GENERATOR...")
        # Generate the enhanced story
        result = enhanced_story_generator.generate_personalized_story(
            user=current_user,
            sunshine=sunshine,
            fear_or_challenge=fear_or_challenge,
            tone=story_tone,
            db=db,
            include_family=include_family,
            include_comfort_items=include_comfort_items,
            custom_elements=custom_elements_list if custom_elements_list else None
        )
        print(f"✅ STORY GENERATOR RETURNED SUCCESSFULLY")
        
        # Determine generation quality based on subscription
        generation_quality = "premium" if current_user.subscription and current_user.subscription.tier.value in ["premium", "enterprise"] else "standard"
        
        # Get updated usage stats
        usage_stats = usage_tracking_service.get_usage_stats(current_user, db)
        
        print(f"📤 V3 RETURNING STORY TO FRONTEND:")
        print(f"  📖 story_id: {result.get('story_id')}")
        print(f"  📖 title: {result.get('title')}")
        print(f"  📖 story_text length: {len(result.get('story_text', ''))} chars")
        print(f"  📖 scenes count: {len(result.get('scenes', []))}")
        print(f"  📖 image_urls count: {len(result.get('image_urls', []))}")
        print(f"  📖 word_count: {result.get('word_count', 0)}")
        print(f"  📖 reading_time: {result.get('reading_time', 0)}")
        
        # ENSURE ALL FIELDS ARE SAFE FOR FRONTEND - NEVER None
        response = EnhancedStoryResponse(
            id=result.get("story_id", ""),  # Frontend expects 'id'
            story_id=result.get("story_id", ""),  # Also include story_id
            title=result.get("title", "Untitled Story"),
            story_text=result.get("story_text", ""),  # CRITICAL: Never None, always string
            scenes=result.get("scenes", []),
            image_urls=result.get("image_urls", []),
            reading_time=result.get("reading_time", 5),
            word_count=result.get("word_count", 0),
            usage_type=result.get("usage_type", "free_tier"),
            credits_remaining=usage_stats.get("stories_remaining", 0),
            character_profiles=result.get("character_profiles", {}),
            generation_quality=generation_quality
        )
        
        # Log the final response format
        response_dict = response.dict() if hasattr(response, 'dict') else response
        print(f"📤 FINAL RESPONSE FORMAT:")
        print(f"  📖 id: {response_dict.get('id') if isinstance(response_dict, dict) else 'N/A'}")
        print(f"  📖 story_id: {response_dict.get('story_id') if isinstance(response_dict, dict) else 'N/A'}")
        print(f"  📖 title: {response_dict.get('title') if isinstance(response_dict, dict) else 'N/A'}")
        print(f"  📖 story_text present: {'Yes' if response_dict.get('story_text') else 'No'}")
        print(f"  📖 story_text length: {len(response_dict.get('story_text', '')) if isinstance(response_dict, dict) else 0} chars")
        print(f"  📖 scenes present: {'Yes' if response_dict.get('scenes') else 'No'}")
        print(f"  📖 scenes count: {len(response_dict.get('scenes', [])) if isinstance(response_dict, dict) else 0}")
        print(f"  📖 image_urls present: {'Yes' if response_dict.get('image_urls') else 'No'}")
        print(f"  📖 image_urls count: {len(response_dict.get('image_urls', [])) if isinstance(response_dict, dict) else 0}")
        print(f"  📖 word_count: {response_dict.get('word_count', 0) if isinstance(response_dict, dict) else 0}")
        print(f"  📖 reading_time: {response_dict.get('reading_time', 0) if isinstance(response_dict, dict) else 0}")
        
        return response
        
    except ValueError as e:
        # This is a subscription/usage limit error
        error_msg = str(e)
        print(f"🔴 DEBUG: ValueError caught in story generation: {error_msg}")
        print(f"🔴 DEBUG: This is causing the 403 Forbidden error!")
        
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
        print(f"❌ ENHANCED STORY GENERATION FAILED!")
        print(f"❌ Error: {str(e)}")
        print(f"❌ Error Type: {type(e).__name__}")
        
        # Log full traceback
        import traceback
        print(f"❌ FULL TRACEBACK:")
        print(traceback.format_exc())
        
        # Check if it's a database issue
        if "database" in str(e).lower() or "sql" in str(e).lower():
            print(f"❌ This appears to be a database error")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate enhanced story: {str(e)}"
        )
    finally:
        # Clear character cache for next story
        enhanced_story_generator.character_profiles.clear()


# TEMPORARY: Test version without auth for story generation
@router.post("/generate-with-photos-test", response_model=EnhancedStoryResponse)
async def generate_story_with_photos_test(
    db: DatabaseSession,
    sunshine_id: str = Form(...),
    fear_or_challenge: str = Form(...),
    tone: str = Form(default="empowering"),
    include_family: bool = Form(default=True),
    include_comfort_items: bool = Form(default=True),
    custom_elements: Optional[str] = Form(default=None),
    # Photo uploads for real-time character analysis
    additional_child_photos: List[UploadFile] = File(default=[]),
    additional_family_photos: List[UploadFile] = File(default=[]),
    comfort_item_photos: List[UploadFile] = File(default=[])
):
    """TEMPORARY: Test version without authentication"""
    # Use hardcoded test user
    test_user_id = "test-user-id-12345"
    print(f"TEMP: Generating story for test user: {test_user_id}")
    
    # Mock subscription object with all authorization attributes
    class MockSubscription:
        def __init__(self):
            # Plan details
            self.plan_type = "free"
            self.tier = "free"  # CONFIRMED WORKING: "free" tier passes validation
            
            # Status flags - all active/valid
            self.is_active = True
            self.status = "active"  # Could also be "paid"
            self.is_valid = True  # Explicitly valid
            
            # Usage tracking - plenty of capacity
            self.stories_limit = 999
            self.stories_used = 0  # No stories used yet
            self.stories_remaining = 999  # Full capacity
            self.sunshines_limit = 999  # CRITICAL: Needed for save!
            
            # Fields needed for FREE tier validation
            self.individual_story_credits = 10  # Some free credits
            self.stories_per_month = 5  # Monthly limit for free tier
            self.stories_created_this_month = 0  # Haven't used any this month
            
            # Period dates
            self.current_period_start = datetime.now(timezone.utc) - timedelta(days=1)
            self.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            
            # Additional flags that might be checked
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
            
            # Additional user attributes that might be checked
            self.is_active = True
            self.is_verified = True
            self.is_admin = False  # Regular user
            self.created_at = datetime.now(timezone.utc) - timedelta(days=30)
            self.last_login = datetime.now(timezone.utc)
            self.sunshines = []  # CRITICAL: Needed for story save!
    
    mock_user = MockUser()
    
    # Debug logging to trace authorization
    print(f"🔍 V3 DEBUG: Starting story generation with mock user...")
    print(f"🔍 V3 User ID: {mock_user.id}")
    print(f"🔍 V3 User email: {mock_user.email}")
    print(f"🔍 V3 User is_active: {getattr(mock_user, 'is_active', 'N/A')}")
    print(f"🔍 V3 User is_verified: {getattr(mock_user, 'is_verified', 'N/A')}")
    
    print(f"🔍 V3 DEBUG: Checking subscription details...")
    print(f"🔍 V3 Subscription status: {mock_user.subscription.status}")
    print(f"🔍 V3 Subscription tier: {mock_user.subscription.tier} (type: {type(mock_user.subscription.tier)})")
    print(f"🔍 V3 Subscription tier.value: {mock_user.subscription.tier.value if hasattr(mock_user.subscription.tier, 'value') else 'N/A'}")
    print(f"🔍 V3 Subscription plan_type: {mock_user.subscription.plan_type}")
    print(f"🔍 V3 Subscription is_active: {mock_user.subscription.is_active}")
    print(f"🔍 Subscription is_valid: {getattr(mock_user.subscription, 'is_valid', 'N/A')}")
    print(f"🔍 Stories limit: {mock_user.subscription.stories_limit}")
    print(f"🔍 Stories used: {getattr(mock_user.subscription, 'stories_used', 'N/A')}")
    print(f"🔍 Stories remaining: {getattr(mock_user.subscription, 'stories_remaining', 'N/A')}")
    print(f"🔍 Can generate stories: {getattr(mock_user.subscription, 'can_generate_stories', 'N/A')}")
    
    print(f"🔍 DEBUG: Calling story generation implementation...")
    
    # Call the implementation function with mock user
    return await generate_story_with_photos_impl(
        current_user=mock_user,
        db=db,
        sunshine_id=sunshine_id,
        fear_or_challenge=fear_or_challenge,
        tone=tone,
        include_family=include_family,
        include_comfort_items=include_comfort_items,
        custom_elements=custom_elements,
        additional_child_photos=additional_child_photos,
        additional_family_photos=additional_family_photos,
        comfort_item_photos=comfort_item_photos
    )


@router.post("/analyze-photo-for-character")
async def analyze_photo_for_character(
    current_user: User = Depends(get_current_user),
    character_name: str = Form(...),
    relationship: str = Form(default="child"),
    photo: UploadFile = File(...)
):
    """
    Analyze a photo to extract character description for story generation
    Useful for previewing how a character will be described in the story
    """
    try:
        photo_bytes = await photo.read()
        
        if not validate_image_file(photo_bytes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file. Please upload JPG, PNG, or WebP."
            )
        
        # Resize for efficiency
        resized_photo = resize_uploaded_image(photo_bytes)
        
        # Analyze photo
        description = enhanced_story_generator.photo_processor.analyze_photo(
            resized_photo,
            character_name,
            relationship
        )
        
        # Generate a sample DALL-E prompt to show how the character would be rendered
        sample_prompt = f"""
Children's book illustration character:
{character_name} ({relationship}): {description}
Style: Warm, friendly cartoon suitable for children's stories
"""
        
        return {
            "character_name": character_name,
            "relationship": relationship,
            "visual_description": description,
            "sample_illustration_prompt": sample_prompt.strip(),
            "photo_processed": True
        }
        
    except Exception as e:
        print(f"Error analyzing photo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze photo"
        )


@router.get("/story-templates")
async def get_story_templates(
    current_user: User = Depends(get_current_user),
    age_group: Optional[str] = None
):
    """
    Get story templates and common fears/challenges by age group
    """
    templates = {
        "toddler": {
            "age_range": "2-4 years",
            "common_challenges": [
                "Bedtime fears",
                "Separation anxiety",
                "Potty training",
                "Sharing toys",
                "First day at daycare",
                "Fear of loud noises",
                "Trying new foods"
            ],
            "recommended_tone": "calm"
        },
        "preschool": {
            "age_range": "4-6 years",
            "common_challenges": [
                "First day of school",
                "Making friends",
                "Fear of the dark",
                "Doctor/dentist visits",
                "Swimming lessons",
                "Sleeping alone",
                "Following rules"
            ],
            "recommended_tone": "empowering"
        },
        "early_elementary": {
            "age_range": "6-8 years",
            "common_challenges": [
                "Test anxiety",
                "Public speaking",
                "Bullying",
                "Making mistakes",
                "Team sports",
                "Sleepovers",
                "Pet loss"
            ],
            "recommended_tone": "adventure"
        },
        "elementary": {
            "age_range": "8-10 years",
            "common_challenges": [
                "Academic pressure",
                "Peer pressure",
                "Self-confidence",
                "Time management",
                "Competition anxiety",
                "Family changes",
                "Technology boundaries"
            ],
            "recommended_tone": "empowering"
        }
    }
    
    if age_group and age_group in templates:
        return templates[age_group]
    
    return templates


# TEMPORARY: Simple endpoint to retrieve generated stories
@router.get("/stories/{story_id}")
async def get_story(
    story_id: str,
    db: DatabaseSession
):
    """
    TEMPORARY: Get a story by ID without authentication
    For testing generated stories
    """
    from app.models.database_models import Story
    
    print(f"📖 Fetching story: {story_id}")
    
    story = db.query(Story).filter(Story.id == story_id).first()
    
    if not story:
        print(f"❌ Story not found: {story_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story not found: {story_id}"
        )
    
    print(f"✅ Found story: {story.title}")
    
    # ENSURE ALL FIELDS ARE SAFE FOR FRONTEND
    return {
        "id": story.id or "",  # Frontend might expect 'id'
        "story_id": story.id or "",
        "title": story.title or "Untitled Story",
        "story_text": story.story_text or "",  # CRITICAL: Never None
        "child_name": story.child_name or "",
        "age": story.age or 0,
        "fear_or_challenge": story.fear_or_challenge or "",
        "tone": story.tone.value if story.tone else "empowering",
        "scenes": story.scenes or [],
        "image_urls": story.image_urls or [],
        "reading_time": story.reading_time or 5,
        "word_count": story.word_count or 0,
        "created_at": story.created_at.isoformat() if story.created_at else "",
        "model_used": story.model_used or "gpt-4o"
    }


# TEMPORARY: Get recent stories without auth
@router.get("/stories/recent/test")
async def get_recent_stories(
    db: DatabaseSession,
    limit: int = 10
):
    """
    TEMPORARY: Get recent stories for testing
    """
    from app.models.database_models import Story
    
    stories = db.query(Story).order_by(Story.created_at.desc()).limit(limit).all()
    
    return [
        {
            "story_id": story.id,
            "title": story.title,
            "child_name": story.child_name,
            "created_at": story.created_at,
            "word_count": story.word_count,
            "image_count": len(story.image_urls) if story.image_urls else 0
        }
        for story in stories
    ]


@router.get("/character-consistency-tips")
async def get_character_consistency_tips():
    """
    Get tips for achieving better character consistency in generated stories
    """
    return {
        "photo_tips": {
            "quality": "Use clear, well-lit photos with visible facial features",
            "angle": "Front-facing or 3/4 angle photos work best",
            "expression": "Natural expressions help capture personality",
            "clothing": "Include typical clothing the child wears",
            "multiple_photos": "Upload 2-3 photos for better consistency"
        },
        "description_tips": {
            "personality_traits": "Add 3-5 personality traits to the Sunshine profile",
            "favorite_colors": "Include favorite colors for clothing in scenes",
            "distinctive_features": "Mention any distinctive features (glasses, freckles, etc.)",
            "comfort_items": "Upload photos of favorite toys or comfort items"
        },
        "story_tips": {
            "tone_selection": "Choose tone that matches child's temperament",
            "family_inclusion": "Include family members the child is close to",
            "familiar_settings": "Mention favorite places in custom elements",
            "age_appropriate": "Ensure challenge matches developmental stage"
        }
    }