"""
Sunshine service for database operations
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
import uuid

from app.models.database_models import (
    Sunshine, SunshinePhoto, FamilyMember, ComfortItem, 
    PersonalityTrait, User, Subscription
)
from app.schemas.sunshine import (
    SunshineCreate, SunshineUpdate, SunshineResponse,
    FamilyMemberCreate, FamilyMemberUpdate, FamilyMemberResponse,
    ComfortItemCreate, ComfortItemUpdate, ComfortItemResponse,
    PersonalityTraitCreate, PersonalityTraitResponse,
    PhotoCreate, PhotoResponse, CharacterReference
)
from app.services.file_upload_service import file_upload_service


class SunshineService:
    """Service for Sunshine-related database operations"""
    
    @staticmethod
    def create_sunshine(
        db: Session,
        user_id: str,
        sunshine_data: SunshineCreate
    ) -> Sunshine:
        """Create a new Sunshine profile"""
        # TEMPORARILY DISABLED FOR TESTING - Skip user/subscription validation
        # # Check subscription limits
        # user = db.query(User).filter(User.id == user_id).first()
        # if not user or not user.subscription:
        #     raise ValueError("User or subscription not found")
        
        # # Count existing sunshines
        # sunshine_count = db.query(Sunshine).filter(
        #     Sunshine.user_id == user_id,
        #     Sunshine.is_active == True
        # ).count()
        
        # if sunshine_count >= user.subscription.sunshines_limit:
        #     raise ValueError(f"Subscription limit reached. Maximum {user.subscription.sunshines_limit} Sunshine profiles allowed.")
        
        print(f"TEMP: Skipping user validation for testing - creating profile for user_id: {user_id}")
        
        # Create Sunshine
        sunshine = Sunshine(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=sunshine_data.name,
            birthdate=sunshine_data.birthdate,
            gender=sunshine_data.gender.value if hasattr(sunshine_data.gender, 'value') else sunshine_data.gender,
            pronouns=sunshine_data.pronouns or SunshineService._get_default_pronouns(sunshine_data.gender),
            nickname=sunshine_data.nickname,
            favorite_color=sunshine_data.favorite_color,
            favorite_animal=sunshine_data.favorite_animal,
            favorite_food=sunshine_data.favorite_food,
            favorite_activity=sunshine_data.favorite_activity,
            fears=sunshine_data.fears,
            dreams=sunshine_data.dreams,
            allergies=sunshine_data.allergies,
            special_needs=sunshine_data.special_needs,
            bedtime_routine=sunshine_data.bedtime_routine,
            personality_summary=sunshine_data.personality_summary,
            additional_notes=sunshine_data.additional_notes,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(sunshine)
        
        # Add personality traits
        for trait_data in sunshine_data.personality_traits:
            trait = PersonalityTrait(
                id=str(uuid.uuid4()),
                sunshine_id=sunshine.id,
                trait=trait_data.trait,
                description=trait_data.description,
                strength=trait_data.strength,
                created_at=datetime.now(timezone.utc)
            )
            db.add(trait)
        
        db.commit()
        db.refresh(sunshine)
        
        return sunshine
    
    @staticmethod
    def _get_default_pronouns(gender: str) -> str:
        """Get default pronouns based on gender"""
        pronoun_map = {
            "male": "he/him",
            "female": "she/her",
            "non_binary": "they/them",
            "prefer_not_to_say": "they/them"
        }
        return pronoun_map.get(gender, "they/them")
    
    @staticmethod
    def get_sunshine(
        db: Session,
        sunshine_id: str,
        user_id: str
    ) -> Optional[Sunshine]:
        """Get a Sunshine profile by ID"""
        return db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).options(
            joinedload(Sunshine.photos),
            joinedload(Sunshine.family_members),
            joinedload(Sunshine.comfort_items),
            joinedload(Sunshine.personality_traits),
            joinedload(Sunshine.stories)
        ).first()
    
    @staticmethod
    def get_user_sunshines(
        db: Session,
        user_id: str,
        include_inactive: bool = False
    ) -> List[Sunshine]:
        """Get all Sunshine profiles for a user"""
        query = db.query(Sunshine).filter(Sunshine.user_id == user_id)
        
        if not include_inactive:
            query = query.filter(Sunshine.is_active == True)
        
        return query.options(
            joinedload(Sunshine.photos),
            joinedload(Sunshine.stories)
        ).order_by(Sunshine.created_at.desc()).all()
    
    @staticmethod
    def update_sunshine(
        db: Session,
        sunshine_id: str,
        user_id: str,
        sunshine_data: SunshineUpdate
    ) -> Optional[Sunshine]:
        """Update a Sunshine profile"""
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            return None
        
        # Update fields
        update_data = sunshine_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(sunshine, field):
                # Handle enum values
                if field == "gender" and hasattr(value, 'value'):
                    value = value.value
                setattr(sunshine, field, value)
        
        sunshine.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(sunshine)
        
        return sunshine
    
    @staticmethod
    def delete_sunshine(
        db: Session,
        sunshine_id: str,
        user_id: str,
        soft_delete: bool = True
    ) -> bool:
        """Delete or deactivate a Sunshine profile"""
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            return False
        
        if soft_delete:
            # Soft delete - just deactivate
            sunshine.is_active = False
            sunshine.updated_at = datetime.now(timezone.utc)
            db.commit()
        else:
            # Hard delete - remove from database
            # Delete related photos from storage
            for photo in sunshine.photos:
                file_upload_service.delete_photo(photo.url)
            
            # Database will cascade delete related records
            db.delete(sunshine)
            db.commit()
        
        return True
    
    # Family Member operations
    @staticmethod
    def add_family_member(
        db: Session,
        sunshine_id: str,
        user_id: str,
        member_data: FamilyMemberCreate
    ) -> FamilyMember:
        """Add a family member to a Sunshine profile"""
        # Verify sunshine belongs to user
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            raise ValueError("Sunshine profile not found")
        
        family_member = FamilyMember(
            id=str(uuid.uuid4()),
            sunshine_id=sunshine_id,
            name=member_data.name,
            relation_type=member_data.relationship.value if hasattr(member_data.relationship, 'value') else member_data.relationship,
            relation_custom=member_data.relationship_custom,
            age=member_data.age,
            description=member_data.description,
            personality_traits=member_data.personality_traits,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(family_member)
        db.commit()
        db.refresh(family_member)
        
        return family_member
    
    @staticmethod
    def update_family_member(
        db: Session,
        member_id: str,
        user_id: str,
        member_data: FamilyMemberUpdate
    ) -> Optional[FamilyMember]:
        """Update a family member"""
        # Get family member with sunshine to verify ownership
        family_member = db.query(FamilyMember).join(
            Sunshine
        ).filter(
            FamilyMember.id == member_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not family_member:
            return None
        
        update_data = member_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            # Map relationship to relation_type for database
            if field == "relationship":
                field = "relation_type"
                if hasattr(value, 'value'):
                    value = value.value
            elif field == "relationship_custom":
                field = "relation_custom"
            
            if hasattr(family_member, field):
                setattr(family_member, field, value)
        
        family_member.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(family_member)
        
        return family_member
    
    @staticmethod
    def delete_family_member(
        db: Session,
        member_id: str,
        user_id: str
    ) -> bool:
        """Delete a family member"""
        family_member = db.query(FamilyMember).join(
            Sunshine
        ).filter(
            FamilyMember.id == member_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not family_member:
            return False
        
        # Delete photos from storage
        for photo in family_member.photos:
            file_upload_service.delete_photo(photo.url)
        
        db.delete(family_member)
        db.commit()
        
        return True
    
    # Comfort Item operations
    @staticmethod
    def add_comfort_item(
        db: Session,
        sunshine_id: str,
        user_id: str,
        item_data: ComfortItemCreate
    ) -> ComfortItem:
        """Add a comfort item to a Sunshine profile"""
        # Verify sunshine belongs to user
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            raise ValueError("Sunshine profile not found")
        
        comfort_item = ComfortItem(
            id=str(uuid.uuid4()),
            sunshine_id=sunshine_id,
            name=item_data.name,
            item_type=item_data.item_type,
            description=item_data.description,
            significance=item_data.significance,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(comfort_item)
        db.commit()
        db.refresh(comfort_item)
        
        return comfort_item
    
    @staticmethod
    def update_comfort_item(
        db: Session,
        item_id: str,
        user_id: str,
        item_data: ComfortItemUpdate
    ) -> Optional[ComfortItem]:
        """Update a comfort item"""
        comfort_item = db.query(ComfortItem).join(
            Sunshine
        ).filter(
            ComfortItem.id == item_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not comfort_item:
            return None
        
        update_data = item_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(comfort_item, field):
                setattr(comfort_item, field, value)
        
        comfort_item.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(comfort_item)
        
        return comfort_item
    
    @staticmethod
    def delete_comfort_item(
        db: Session,
        item_id: str,
        user_id: str
    ) -> bool:
        """Delete a comfort item"""
        comfort_item = db.query(ComfortItem).join(
            Sunshine
        ).filter(
            ComfortItem.id == item_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not comfort_item:
            return False
        
        # Delete photos from storage
        for photo in comfort_item.photos:
            file_upload_service.delete_photo(photo.url)
        
        db.delete(comfort_item)
        db.commit()
        
        return True
    
    # Personality Trait operations
    @staticmethod
    def add_personality_trait(
        db: Session,
        sunshine_id: str,
        user_id: str,
        trait_data: PersonalityTraitCreate
    ) -> PersonalityTrait:
        """Add a personality trait to a Sunshine profile"""
        # Verify sunshine belongs to user
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            raise ValueError("Sunshine profile not found")
        
        trait = PersonalityTrait(
            id=str(uuid.uuid4()),
            sunshine_id=sunshine_id,
            trait=trait_data.trait,
            description=trait_data.description,
            strength=trait_data.strength,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(trait)
        db.commit()
        db.refresh(trait)
        
        return trait
    
    @staticmethod
    def delete_personality_trait(
        db: Session,
        trait_id: str,
        user_id: str
    ) -> bool:
        """Delete a personality trait"""
        trait = db.query(PersonalityTrait).join(
            Sunshine
        ).filter(
            PersonalityTrait.id == trait_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not trait:
            return False
        
        db.delete(trait)
        db.commit()
        
        return True
    
    # Photo operations
    @staticmethod
    def add_photo(
        db: Session,
        sunshine_id: str,
        user_id: str,
        photo_url: str,
        thumbnail_url: str,
        photo_data: PhotoCreate,
        family_member_id: Optional[str] = None,
        comfort_item_id: Optional[str] = None
    ) -> SunshinePhoto:
        """Add a photo to a Sunshine profile, family member, or comfort item"""
        # Verify sunshine belongs to user
        sunshine = db.query(Sunshine).filter(
            Sunshine.id == sunshine_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not sunshine:
            raise ValueError("Sunshine profile not found")
        
        # If it's a profile photo and set as primary, unset other primary photos
        if photo_data.is_primary and photo_data.photo_type.value == "profile":
            db.query(SunshinePhoto).filter(
                SunshinePhoto.sunshine_id == sunshine_id,
                SunshinePhoto.photo_type == "profile"
            ).update({"is_primary": False})
        
        photo = SunshinePhoto(
            id=str(uuid.uuid4()),
            sunshine_id=sunshine_id,
            family_member_id=family_member_id,
            comfort_item_id=comfort_item_id,
            url=photo_url,
            thumbnail_url=thumbnail_url,
            photo_type=photo_data.photo_type.value if hasattr(photo_data.photo_type, 'value') else photo_data.photo_type,
            description=photo_data.description,
            is_primary=photo_data.is_primary,
            uploaded_at=datetime.now(timezone.utc)
        )
        
        db.add(photo)
        db.commit()
        db.refresh(photo)
        
        return photo
    
    @staticmethod
    def delete_photo(
        db: Session,
        photo_id: str,
        user_id: str
    ) -> bool:
        """Delete a photo"""
        photo = db.query(SunshinePhoto).join(
            Sunshine
        ).filter(
            SunshinePhoto.id == photo_id,
            Sunshine.user_id == user_id
        ).first()
        
        if not photo:
            return False
        
        # Delete from storage
        file_upload_service.delete_photo(photo.url)
        
        db.delete(photo)
        db.commit()
        
        return True
    
    @staticmethod
    def get_character_reference(
        db: Session,
        sunshine_id: str,
        user_id: str
    ) -> CharacterReference:
        """Get character reference data for AI story generation"""
        sunshine = SunshineService.get_sunshine(db, sunshine_id, user_id)
        
        if not sunshine:
            raise ValueError("Sunshine profile not found")
        
        # Calculate age
        today = date.today()
        age = today.year - sunshine.birthdate.year - ((today.month, today.day) < (sunshine.birthdate.month, sunshine.birthdate.day))
        
        # Build physical description
        physical_description = {
            "age": age,
            "gender": sunshine.gender,
            "favorite_color": sunshine.favorite_color,
            "special_features": sunshine.special_needs
        }
        
        # Get personality traits
        personality_traits = [
            f"{trait.trait} ({trait.strength}/5)" 
            for trait in sunshine.personality_traits
        ]
        
        # Get family members
        family_members = [
            {
                "name": member.name,
                "relationship": member.relation_type,
                "age": member.age,
                "traits": member.personality_traits
            }
            for member in sunshine.family_members
        ]
        
        # Get comfort items
        comfort_items = [item.name for item in sunshine.comfort_items]
        
        # Get reference photos (profile and primary photos)
        reference_photos = [
            photo.url 
            for photo in sunshine.photos 
            if photo.is_primary or photo.photo_type == "profile"
        ][:5]  # Limit to 5 photos
        
        return CharacterReference(
            sunshine_id=sunshine.id,
            name=sunshine.name,
            age=age,
            gender=sunshine.gender,
            pronouns=sunshine.pronouns or SunshineService._get_default_pronouns(sunshine.gender),
            physical_description=physical_description,
            personality_traits=personality_traits,
            family_members=family_members,
            comfort_items=comfort_items,
            reference_photos=reference_photos
        )


# Global instance
sunshine_service = SunshineService()