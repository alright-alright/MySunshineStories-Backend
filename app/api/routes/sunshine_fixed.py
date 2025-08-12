"""
Fixed Sunshine profile API routes
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request, Form, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import json
from datetime import date, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.database_models import User
from app.services.sunshine_service import sunshine_service
from app.schemas.sunshine import (
    SunshineCreate, SunshineUpdate, SunshineResponse, SunshineSummary,
    FamilyMemberCreate, FamilyMemberUpdate, FamilyMemberResponse,
    ComfortItemCreate, ComfortItemUpdate, ComfortItemResponse,
    PersonalityTraitCreate, PersonalityTraitResponse,
    PhotoCreate, PhotoResponse, BulkPhotoUpload, CharacterReference
)

router = APIRouter()

# ============== Test Endpoints ==============

@router.post("/test")
async def test_post_endpoint():
    """Simple test endpoint to verify POST works"""
    return {"message": "Test POST endpoint is working", "status": "success"}

@router.post("/test-form")
async def test_form_endpoint(
    name: str = Form(...),
    age: str = Form(...)
):
    """Test endpoint with Form parameters"""
    return {
        "message": "Form POST endpoint is working",
        "received": {
            "name": name,
            "age": age
        }
    }

@router.get("/test")
async def test_get_endpoint():
    """Simple test endpoint to verify GET works"""
    return {"message": "Test GET endpoint is working", "status": "success"}

# ============== Main Endpoints ==============

@router.get("/", response_model=List[SunshineSummary])
async def get_my_sunshines(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all Sunshine profiles for the current user"""
    sunshines = sunshine_service.get_user_sunshines(
        db=db,
        user_id=current_user.id,
        include_inactive=include_inactive
    )
    
    # Convert to summary format
    summaries = []
    for sunshine in sunshines:
        # Calculate age
        from datetime import date
        today = date.today()
        age = today.year - sunshine.birthdate.year - ((today.month, today.day) < (sunshine.birthdate.month, sunshine.birthdate.day))
        
        # Get profile photo
        profile_photo = next((p for p in sunshine.photos if p.is_primary), None) if hasattr(sunshine, 'photos') else None
        
        summaries.append(SunshineSummary(
            id=sunshine.id,
            name=sunshine.name,
            nickname=sunshine.nickname,
            age=age,
            gender=sunshine.gender,
            profile_photo_url=profile_photo.url if profile_photo else None,
            stories_count=len(sunshine.stories) if hasattr(sunshine, 'stories') else 0,
            is_active=sunshine.is_active,
            created_at=sunshine.created_at
        ))
    
    return summaries


@router.post("/")
async def create_sunshine(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    name: str = Form(...),
    age: str = Form(...),
    gender: str = Form("prefer_not_to_say"),
    interests: str = Form("[]"),  # JSON string
    personality_traits: str = Form("[]"),  # JSON string
    family_members: str = Form("[]"),  # JSON string
    comfort_items: str = Form("[]"),  # JSON string
    fears_or_challenges: Optional[str] = Form(None),
    favorite_things: Optional[str] = Form(None),
    photos: Optional[List[UploadFile]] = File(default=None)
):
    """Create a new Sunshine profile with form data"""
    try:
        # Calculate birthdate from age
        try:
            age_int = int(age) if age else 5  # Default to 5 if not provided
        except ValueError:
            age_int = 5
        birthdate = date.today() - timedelta(days=age_int * 365)
        
        # Parse JSON strings
        try:
            interests_list = json.loads(interests) if interests and interests != "[]" else []
            traits_list = json.loads(personality_traits) if personality_traits and personality_traits != "[]" else []
            family_list = json.loads(family_members) if family_members and family_members != "[]" else []
            comfort_list = json.loads(comfort_items) if comfort_items and comfort_items != "[]" else []
        except json.JSONDecodeError:
            interests_list = []
            traits_list = []
            family_list = []
            comfort_list = []
        
        # Create the sunshine data object
        sunshine_data = SunshineCreate(
            name=name,
            birthdate=birthdate,
            gender=gender if gender in ["male", "female", "non_binary"] else "prefer_not_to_say",
            favorite_activity=", ".join(interests_list) if interests_list else None,
            favorite_food=favorite_things,
            fears=[item.strip() for item in fears_or_challenges.split(",") if item.strip()] if fears_or_challenges else [],
            personality_traits=[
                PersonalityTraitCreate(trait=trait, strength=3) 
                for trait in traits_list if trait
            ]
        )
        
        # Create the sunshine profile
        sunshine = sunshine_service.create_sunshine(
            db=db,
            user_id=current_user.id,
            sunshine_data=sunshine_data
        )
        
        # Add family members
        for member in family_list:
            if isinstance(member, dict) and member.get('name'):
                try:
                    member_data = FamilyMemberCreate(
                        name=member['name'],
                        relationship=member.get('relation_type', 'other'),
                        age=int(member['age']) if member.get('age') else None
                    )
                    sunshine_service.add_family_member(
                        db=db,
                        sunshine_id=sunshine.id,
                        user_id=current_user.id,
                        member_data=member_data
                    )
                except Exception as e:
                    print(f"Failed to add family member: {e}")
        
        # Add comfort items
        for item in comfort_list:
            if isinstance(item, dict) and item.get('name'):
                try:
                    item_data = ComfortItemCreate(
                        name=item['name'],
                        item_type='other',
                        description=item.get('description', '')
                    )
                    sunshine_service.add_comfort_item(
                        db=db,
                        sunshine_id=sunshine.id,
                        user_id=current_user.id,
                        item_data=item_data
                    )
                except Exception as e:
                    print(f"Failed to add comfort item: {e}")
        
        # Return the created sunshine profile
        db.refresh(sunshine)
        return SunshineResponse.from_orm_model(sunshine)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating sunshine: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create profile: {str(e)}"
        )


@router.get("/{sunshine_id}", response_model=SunshineResponse)
async def get_sunshine(
    sunshine_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific Sunshine profile"""
    sunshine = sunshine_service.get_sunshine(
        db=db,
        sunshine_id=sunshine_id,
        user_id=current_user.id
    )
    
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    return SunshineResponse.from_orm_model(sunshine)


@router.put("/{sunshine_id}", response_model=SunshineResponse)
async def update_sunshine(
    sunshine_id: str,
    sunshine_data: SunshineUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a Sunshine profile"""
    sunshine = sunshine_service.update_sunshine(
        db=db,
        sunshine_id=sunshine_id,
        user_id=current_user.id,
        sunshine_data=sunshine_data
    )
    
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    return SunshineResponse.from_orm_model(sunshine)


@router.delete("/{sunshine_id}")
async def delete_sunshine(
    sunshine_id: str,
    permanent: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete or deactivate a Sunshine profile"""
    success = sunshine_service.delete_sunshine(
        db=db,
        sunshine_id=sunshine_id,
        user_id=current_user.id,
        soft_delete=not permanent
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    return {"message": "Sunshine profile deleted successfully"}