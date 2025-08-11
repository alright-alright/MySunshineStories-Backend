"""
Enhanced Story Generation API with Direct Photo Upload
Provides advanced story generation with real-time photo analysis
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import json

from app.core.dependencies import CurrentUser, DatabaseSession
from app.services.enhanced_story_generator import enhanced_story_generator, CharacterProfile
from app.services.usage_tracking_service import usage_tracking_service
from app.services.image_generator import resize_uploaded_image, validate_image_file
from app.models.database_models import Story, StoryTone, Sunshine
from pydantic import BaseModel, Field

router = APIRouter()


class EnhancedStoryResponse(BaseModel):
    """Response model for enhanced story generation"""
    story_id: str
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


@router.post("/generate-with-photos", response_model=EnhancedStoryResponse)
async def generate_story_with_photos(
    current_user: CurrentUser,
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
    """
    Generate an enhanced story with direct photo uploads for maximum personalization
    This endpoint allows uploading additional photos at generation time for better character consistency
    """
    # Get Sunshine profile
    sunshine = db.query(Sunshine).filter(
        Sunshine.id == sunshine_id,
        Sunshine.user_id == current_user.id
    ).first()
    
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
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
        
        # Determine generation quality based on subscription
        generation_quality = "premium" if current_user.subscription and current_user.subscription.tier.value in ["premium", "enterprise"] else "standard"
        
        # Get updated usage stats
        usage_stats = usage_tracking_service.get_usage_stats(current_user, db)
        
        return EnhancedStoryResponse(
            story_id=result["story_id"],
            title=result["title"],
            story_text=result["story_text"],
            scenes=result["scenes"],
            image_urls=result["image_urls"],
            reading_time=result["reading_time"],
            word_count=result["word_count"],
            usage_type=result["usage_type"],
            credits_remaining=usage_stats.get("stories_remaining", 0),
            character_profiles=result["character_profiles"],
            generation_quality=generation_quality
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
        print(f"Enhanced story generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate enhanced story. You have not been charged."
        )
    finally:
        # Clear character cache for next story
        enhanced_story_generator.character_profiles.clear()


@router.post("/analyze-photo-for-character")
async def analyze_photo_for_character(
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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