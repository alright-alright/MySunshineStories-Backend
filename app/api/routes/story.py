from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
from datetime import datetime
from typing import List, Optional, Dict
from app.models.story import StoryRequest, GeneratedStory, FamilyMember, StoryTone
from app.services.story_generator import StoryGeneratorService
from app.services.pdf_generator import PDFGeneratorService
from app.services.s3_service import S3Service
from app.services.image_generator import resize_uploaded_image, validate_image_file

router = APIRouter()

story_service = StoryGeneratorService()
pdf_service = PDFGeneratorService()
s3_service = S3Service()

@router.post("/story/generate", response_model=GeneratedStory)
async def generate_story(
    child_name: str = Form(...),
    fear_or_challenge: str = Form(...),
    age: int = Form(None),
    favorite_items: str = Form(""),
    family_members: str = Form(""),
    tone: str = Form("empowering"),
    language: str = Form("english"),
    # Photo uploads - can handle multiple files
    child_photo: UploadFile = File(None),
    family_photos: List[UploadFile] = File([]),
    toy_photos: List[UploadFile] = File([])
):
    """
    Generate a personalized children's story with illustrations based on uploaded photos
    """
    try:
        # Parse input data
        items_list = [item.strip() for item in favorite_items.split(",") if item.strip()]
        
        family_list = []
        family_names = []  # Track names for photo matching
        
        if family_members:
            # Parse format: "Mom (mother), Dad (father), Alex (brother)"
            for member in family_members.split(","):
                member = member.strip()
                if "(" in member and ")" in member:
                    name = member.split("(")[0].strip()
                    relationship = member.split("(")[1].replace(")", "").strip()
                    family_list.append(FamilyMember(name=name, relationship=relationship))
                    family_names.append(name)
                elif member:
                    # Default to generic relationship if format not followed
                    family_list.append(FamilyMember(name=member, relationship="family member"))
                    family_names.append(member)
        
        # Validate tone
        try:
            story_tone = StoryTone(tone.lower())
        except ValueError:
            story_tone = StoryTone.EMPOWERING
        
        # Process uploaded photos
        uploaded_photos = {}
        
        # Child photo
        if child_photo and child_photo.filename:
            photo_bytes = await child_photo.read()
            if validate_image_file(photo_bytes):
                # Resize for API efficiency
                resized_photo = resize_uploaded_image(photo_bytes)
                uploaded_photos[child_name] = resized_photo
                print(f"✅ Processed photo for {child_name}")
            else:
                print(f"⚠️  Invalid image file for child: {child_photo.filename}")
        
        # Family photos (match by filename or order)
        for i, family_photo in enumerate(family_photos):
            if family_photo and family_photo.filename:
                photo_bytes = await family_photo.read()
                if validate_image_file(photo_bytes):
                    resized_photo = resize_uploaded_image(photo_bytes)
                    
                    # Try to match photo to family member name
                    # Could be enhanced with metadata or better matching logic
                    if i < len(family_names):
                        person_name = family_names[i]
                        uploaded_photos[person_name] = resized_photo
                        print(f"✅ Processed photo for {person_name}")
                    else:
                        # Fallback name if no match
                        uploaded_photos[f"family_member_{i+1}"] = resized_photo
                        print(f"✅ Processed family photo {i+1}")
                else:
                    print(f"⚠️  Invalid family image file: {family_photo.filename}")
        
        # Toy photos (could be incorporated into favorite items)
        for i, toy_photo in enumerate(toy_photos):
            if toy_photo and toy_photo.filename:
                photo_bytes = await toy_photo.read()
                if validate_image_file(photo_bytes):
                    resized_photo = resize_uploaded_image(photo_bytes)
                    # Store toy photos with identifiable names
                    uploaded_photos[f"toy_{i+1}"] = resized_photo
                    print(f"✅ Processed toy photo {i+1}")
        
        # Create request object
        story_request = StoryRequest(
            child_name=child_name,
            age=age,
            fear_or_challenge=fear_or_challenge,
            favorite_items=items_list,
            family_members=family_list,
            tone=story_tone,
            language=language
        )
        
        # Generate story
        story_response = story_service.generate_story(story_request)
        
        # Create PDF with character-aware images
        pdf_path = pdf_service.create_storybook_pdf(story_response, uploaded_photos)
        
        # Try to upload to S3 (fallback to local URL)
        pdf_url = pdf_path  # Local URL by default
        if s3_service.s3_client:
            s3_url = s3_service.upload_pdf(
                f"static/{os.path.basename(pdf_path)}", 
                f"stories/{child_name.lower()}_{datetime.now().timestamp()}.pdf"
            )
            if s3_url:
                pdf_url = s3_url
        
        return GeneratedStory(
            story_response=story_response,
            pdf_url=pdf_url,
            created_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"Error generating story: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/story/example")
async def get_example_story():
    """Get an example story for testing"""
    from app.models.story import StoryScene
    
    example_response = {
        "story_response": {
            "story_title": "Emma's Brave Night",
            "story_text": "Emma used to be afraid of the dark, but with her teddy bear and mom's help, she learned that nighttime can be peaceful and safe.",
            "scenes": [
                {
                    "scene_number": 1,
                    "description": "Emma feeling scared at bedtime",
                    "image_prompt": "A young girl named Emma holding a teddy bear, looking a bit worried at bedtime"
                }
            ],
            "child_name": "Emma",
            "tone": "empowering"
        },
        "pdf_url": "/static/example.pdf",
        "created_at": datetime.now().isoformat()
    }
    
    return example_response

@router.post("/story/test-photo")
async def test_photo_upload(
    child_name: str = Form(...),
    photo: UploadFile = File(...)
):
    """Test endpoint for photo upload and analysis"""
    try:
        photo_bytes = await photo.read()
        
        if not validate_image_file(photo_bytes):
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Process photo
        from app.services.image_generator import PhotoProcessor
        processor = PhotoProcessor()
        description = processor.analyze_photo(photo_bytes, child_name, "child")
        
        return {
            "child_name": child_name,
            "filename": photo.filename,
            "file_size": len(photo_bytes),
            "character_description": description
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing photo: {str(e)}")
