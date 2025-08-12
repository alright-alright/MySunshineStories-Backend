"""
Sunshine profile API routes with comprehensive CRUD operations
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser, DatabaseSession
from app.services.sunshine_service import sunshine_service
from app.services.file_upload_service import file_upload_service
from app.schemas.sunshine import (
    SunshineCreate, SunshineUpdate, SunshineResponse, SunshineSummary,
    FamilyMemberCreate, FamilyMemberUpdate, FamilyMemberResponse,
    ComfortItemCreate, ComfortItemUpdate, ComfortItemResponse,
    PersonalityTraitCreate, PersonalityTraitResponse,
    PhotoCreate, PhotoResponse, BulkPhotoUpload, CharacterReference
)

router = APIRouter()


# ============== Sunshine Profile Endpoints ==============

@router.post("/", response_model=SunshineResponse)
async def create_sunshine(
    sunshine_data: SunshineCreate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Create a new Sunshine profile"""
    try:
        sunshine = sunshine_service.create_sunshine(
            db=db,
            user_id=current_user.id,
            sunshine_data=sunshine_data
        )
        return SunshineResponse.from_orm_model(sunshine)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[SunshineSummary])
async def get_my_sunshines(
    current_user: CurrentUser,
    db: DatabaseSession,
    include_inactive: bool = False
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
        profile_photo = next((p for p in sunshine.photos if p.is_primary), None)
        
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


@router.get("/{sunshine_id}", response_model=SunshineResponse)
async def get_sunshine(
    sunshine_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
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
    current_user: CurrentUser,
    db: DatabaseSession
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
    current_user: CurrentUser,
    db: DatabaseSession,
    permanent: bool = False
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


# ============== Photo Management Endpoints ==============

@router.post("/{sunshine_id}/photos/upload", response_model=PhotoResponse)
async def upload_sunshine_photo(
    sunshine_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    photo_type: str = Form("gallery"),
    description: Optional[str] = Form(None),
    is_primary: bool = Form(False)
):
    """Upload a photo for a Sunshine profile"""
    # Verify sunshine belongs to user
    sunshine = sunshine_service.get_sunshine(db, sunshine_id, current_user.id)
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    try:
        # Upload and process the photo
        if photo_type == "profile":
            photo_url, thumbnail_url = await file_upload_service.upload_profile_photo(
                file=file,
                user_id=current_user.id,
                sunshine_id=sunshine_id
            )
        else:
            photo_url, thumbnail_url = await file_upload_service.upload_gallery_photo(
                file=file,
                user_id=current_user.id,
                sunshine_id=sunshine_id,
                photo_type=photo_type
            )
        
        # Save to database
        photo_data = PhotoCreate(
            photo_type=photo_type,
            description=description,
            is_primary=is_primary
        )
        
        photo = sunshine_service.add_photo(
            db=db,
            sunshine_id=sunshine_id,
            user_id=current_user.id,
            photo_url=photo_url,
            thumbnail_url=thumbnail_url,
            photo_data=photo_data
        )
        
        return PhotoResponse.model_validate(photo)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{sunshine_id}/photos/bulk-upload", response_model=BulkPhotoUpload)
async def bulk_upload_photos(
    sunshine_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    files: List[UploadFile] = File(...),
    photo_type: str = Form("gallery")
):
    """Upload multiple photos at once"""
    # Verify sunshine belongs to user
    sunshine = sunshine_service.get_sunshine(db, sunshine_id, current_user.id)
    if not sunshine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sunshine profile not found"
        )
    
    # Upload photos
    results = await file_upload_service.upload_multiple_photos(
        files=files,
        user_id=current_user.id,
        sunshine_id=sunshine_id,
        photo_type=photo_type
    )
    
    uploaded_photos = []
    failed_uploads = []
    
    for filename, url, thumbnail in results:
        if url:
            # Save to database
            photo_data = PhotoCreate(photo_type=photo_type)
            photo = sunshine_service.add_photo(
                db=db,
                sunshine_id=sunshine_id,
                user_id=current_user.id,
                photo_url=url,
                thumbnail_url=thumbnail,
                photo_data=photo_data
            )
            uploaded_photos.append(PhotoResponse.model_validate(photo))
        else:
            failed_uploads.append({"filename": filename, "error": thumbnail})
    
    return BulkPhotoUpload(
        sunshine_id=sunshine_id,
        uploaded_photos=uploaded_photos,
        failed_uploads=failed_uploads
    )


@router.delete("/{sunshine_id}/photos/{photo_id}")
async def delete_photo(
    sunshine_id: str,
    photo_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Delete a photo"""
    success = sunshine_service.delete_photo(
        db=db,
        photo_id=photo_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found"
        )
    
    return {"message": "Photo deleted successfully"}


# ============== Family Member Endpoints ==============

@router.post("/{sunshine_id}/family", response_model=FamilyMemberResponse)
async def add_family_member(
    sunshine_id: str,
    member_data: FamilyMemberCreate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Add a family member to a Sunshine profile"""
    try:
        family_member = sunshine_service.add_family_member(
            db=db,
            sunshine_id=sunshine_id,
            user_id=current_user.id,
            member_data=member_data
        )
        return FamilyMemberResponse.from_orm_model(family_member)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/family/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: str,
    member_data: FamilyMemberUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update a family member"""
    family_member = sunshine_service.update_family_member(
        db=db,
        member_id=member_id,
        user_id=current_user.id,
        member_data=member_data
    )
    
    if not family_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family member not found"
        )
    
    return FamilyMemberResponse.model_validate(family_member)


@router.delete("/family/{member_id}")
async def delete_family_member(
    member_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Delete a family member"""
    success = sunshine_service.delete_family_member(
        db=db,
        member_id=member_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family member not found"
        )
    
    return {"message": "Family member deleted successfully"}


@router.post("/family/{member_id}/photos/upload", response_model=PhotoResponse)
async def upload_family_member_photo(
    member_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload a photo for a family member"""
    # Get family member and verify ownership
    from app.models.database_models import FamilyMember, Sunshine
    family_member = db.query(FamilyMember).join(
        Sunshine
    ).filter(
        FamilyMember.id == member_id,
        Sunshine.user_id == current_user.id
    ).first()
    
    if not family_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family member not found"
        )
    
    try:
        # Upload photo
        photo_url, thumbnail_url = await file_upload_service.upload_gallery_photo(
            file=file,
            user_id=current_user.id,
            sunshine_id=family_member.sunshine_id,
            photo_type="family"
        )
        
        # Save to database
        photo_data = PhotoCreate(
            photo_type="family",
            description=description
        )
        
        photo = sunshine_service.add_photo(
            db=db,
            sunshine_id=family_member.sunshine_id,
            user_id=current_user.id,
            photo_url=photo_url,
            thumbnail_url=thumbnail_url,
            photo_data=photo_data,
            family_member_id=member_id
        )
        
        return PhotoResponse.model_validate(photo)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============== Comfort Item Endpoints ==============

@router.post("/{sunshine_id}/comfort-items", response_model=ComfortItemResponse)
async def add_comfort_item(
    sunshine_id: str,
    item_data: ComfortItemCreate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Add a comfort item to a Sunshine profile"""
    try:
        comfort_item = sunshine_service.add_comfort_item(
            db=db,
            sunshine_id=sunshine_id,
            user_id=current_user.id,
            item_data=item_data
        )
        return ComfortItemResponse.model_validate(comfort_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/comfort-items/{item_id}", response_model=ComfortItemResponse)
async def update_comfort_item(
    item_id: str,
    item_data: ComfortItemUpdate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Update a comfort item"""
    comfort_item = sunshine_service.update_comfort_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id,
        item_data=item_data
    )
    
    if not comfort_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comfort item not found"
        )
    
    return ComfortItemResponse.model_validate(comfort_item)


@router.delete("/comfort-items/{item_id}")
async def delete_comfort_item(
    item_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Delete a comfort item"""
    success = sunshine_service.delete_comfort_item(
        db=db,
        item_id=item_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comfort item not found"
        )
    
    return {"message": "Comfort item deleted successfully"}


@router.post("/comfort-items/{item_id}/photos/upload", response_model=PhotoResponse)
async def upload_comfort_item_photo(
    item_id: str,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Upload a photo for a comfort item"""
    # Get comfort item and verify ownership
    from app.models.database_models import ComfortItem, Sunshine
    comfort_item = db.query(ComfortItem).join(
        Sunshine
    ).filter(
        ComfortItem.id == item_id,
        Sunshine.user_id == current_user.id
    ).first()
    
    if not comfort_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comfort item not found"
        )
    
    try:
        # Upload photo
        photo_url, thumbnail_url = await file_upload_service.upload_gallery_photo(
            file=file,
            user_id=current_user.id,
            sunshine_id=comfort_item.sunshine_id,
            photo_type="comfort_item"
        )
        
        # Save to database
        photo_data = PhotoCreate(
            photo_type="comfort_item",
            description=description
        )
        
        photo = sunshine_service.add_photo(
            db=db,
            sunshine_id=comfort_item.sunshine_id,
            user_id=current_user.id,
            photo_url=photo_url,
            thumbnail_url=thumbnail_url,
            photo_data=photo_data,
            comfort_item_id=item_id
        )
        
        return PhotoResponse.model_validate(photo)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============== Personality Trait Endpoints ==============

@router.post("/{sunshine_id}/personality-traits", response_model=PersonalityTraitResponse)
async def add_personality_trait(
    sunshine_id: str,
    trait_data: PersonalityTraitCreate,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Add a personality trait to a Sunshine profile"""
    try:
        trait = sunshine_service.add_personality_trait(
            db=db,
            sunshine_id=sunshine_id,
            user_id=current_user.id,
            trait_data=trait_data
        )
        return PersonalityTraitResponse.model_validate(trait)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/personality-traits/{trait_id}")
async def delete_personality_trait(
    trait_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Delete a personality trait"""
    success = sunshine_service.delete_personality_trait(
        db=db,
        trait_id=trait_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personality trait not found"
        )
    
    return {"message": "Personality trait deleted successfully"}


# ============== Character Reference Endpoint ==============

@router.get("/{sunshine_id}/character-reference", response_model=CharacterReference)
async def get_character_reference(
    sunshine_id: str,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Get character reference data for AI story generation"""
    try:
        reference = sunshine_service.get_character_reference(
            db=db,
            sunshine_id=sunshine_id,
            user_id=current_user.id
        )
        return reference
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )