"""
File upload service for handling images and files
"""
import os
import uuid
import hashlib
from typing import Optional, Tuple, List
from datetime import datetime
from pathlib import Path
from PIL import Image
import io
from fastapi import UploadFile, HTTPException
import aiofiles

from app.core.config import settings


class FileUploadService:
    """Service for handling file uploads and image processing"""
    
    # Allowed image extensions
    ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    
    # Max file sizes (in bytes)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_THUMBNAIL_SIZE = 500 * 1024  # 500KB
    
    # Image dimensions
    PROFILE_SIZE = (400, 400)
    THUMBNAIL_SIZE = (150, 150)
    GALLERY_SIZE = (800, 800)
    
    # Storage paths
    UPLOAD_BASE_PATH = Path("static/uploads")
    
    def __init__(self):
        """Initialize the file upload service"""
        # Create upload directories if they don't exist
        self.create_upload_directories()
    
    def create_upload_directories(self):
        """Create necessary upload directories"""
        directories = [
            self.UPLOAD_BASE_PATH / "profiles",
            self.UPLOAD_BASE_PATH / "thumbnails",
            self.UPLOAD_BASE_PATH / "galleries",
            self.UPLOAD_BASE_PATH / "family",
            self.UPLOAD_BASE_PATH / "comfort_items",
            self.UPLOAD_BASE_PATH / "objects",
            self.UPLOAD_BASE_PATH / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Generate a unique filename while preserving extension"""
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}{ext}"
    
    @staticmethod
    def get_file_hash(file_content: bytes) -> str:
        """Generate SHA256 hash of file content for duplicate detection"""
        return hashlib.sha256(file_content).hexdigest()
    
    async def validate_image(self, file: UploadFile) -> bool:
        """Validate uploaded image file"""
        # Check file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type {ext} not allowed. Allowed types: {', '.join(self.ALLOWED_IMAGE_EXTENSIONS)}"
            )
        
        # Check file size
        file_content = await file.read()
        await file.seek(0)  # Reset file pointer
        
        if len(file_content) > self.MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {self.MAX_IMAGE_SIZE / 1024 / 1024}MB"
            )
        
        # Verify it's a valid image
        try:
            image = Image.open(io.BytesIO(file_content))
            image.verify()
            return True
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid image file"
            )
    
    def process_image(
        self,
        image: Image.Image,
        target_size: Tuple[int, int],
        maintain_aspect: bool = True
    ) -> Image.Image:
        """Process and resize image"""
        # Convert RGBA to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        if maintain_aspect:
            # Maintain aspect ratio
            image.thumbnail(target_size, Image.Resampling.LANCZOS)
        else:
            # Crop to exact size
            image = self.crop_center(image, target_size)
        
        return image
    
    @staticmethod
    def crop_center(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """Crop image to center with target size"""
        width, height = image.size
        target_width, target_height = target_size
        
        # Calculate aspect ratios
        img_ratio = width / height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # Image is wider than target
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            image = image.crop((left, 0, left + new_width, height))
        else:
            # Image is taller than target
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            image = image.crop((0, top, width, top + new_height))
        
        # Resize to exact target size
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        return image
    
    async def upload_profile_photo(
        self,
        file: UploadFile,
        user_id: str,
        sunshine_id: str
    ) -> Tuple[str, str]:
        """Upload and process profile photo"""
        await self.validate_image(file)
        
        # Read file content
        file_content = await file.read()
        image = Image.open(io.BytesIO(file_content))
        
        # Generate unique filename
        filename = self.generate_unique_filename(file.filename)
        
        # Process profile image
        profile_image = self.process_image(image, self.PROFILE_SIZE, maintain_aspect=False)
        profile_path = self.UPLOAD_BASE_PATH / "profiles" / user_id / sunshine_id / filename
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_image.save(profile_path, quality=85, optimize=True)
        
        # Create thumbnail
        thumbnail_image = self.process_image(image, self.THUMBNAIL_SIZE, maintain_aspect=False)
        thumbnail_path = self.UPLOAD_BASE_PATH / "thumbnails" / user_id / sunshine_id / f"thumb_{filename}"
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        thumbnail_image.save(thumbnail_path, quality=80, optimize=True)
        
        # Return URLs
        profile_url = f"/static/uploads/profiles/{user_id}/{sunshine_id}/{filename}"
        thumbnail_url = f"/static/uploads/thumbnails/{user_id}/{sunshine_id}/thumb_{filename}"
        
        return profile_url, thumbnail_url
    
    async def upload_gallery_photo(
        self,
        file: UploadFile,
        user_id: str,
        sunshine_id: str,
        photo_type: str
    ) -> Tuple[str, str]:
        """Upload and process gallery photo"""
        await self.validate_image(file)
        
        # Read file content
        file_content = await file.read()
        image = Image.open(io.BytesIO(file_content))
        
        # Generate unique filename
        filename = self.generate_unique_filename(file.filename)
        
        # Determine folder based on photo type
        folder_map = {
            "gallery": "galleries",
            "family": "family",
            "comfort_item": "comfort_items",
            "object": "objects"
        }
        folder = folder_map.get(photo_type, "galleries")
        
        # Process gallery image
        gallery_image = self.process_image(image, self.GALLERY_SIZE, maintain_aspect=True)
        gallery_path = self.UPLOAD_BASE_PATH / folder / user_id / sunshine_id / filename
        gallery_path.parent.mkdir(parents=True, exist_ok=True)
        gallery_image.save(gallery_path, quality=90, optimize=True)
        
        # Create thumbnail
        thumbnail_image = self.process_image(image, self.THUMBNAIL_SIZE, maintain_aspect=True)
        thumbnail_path = self.UPLOAD_BASE_PATH / "thumbnails" / user_id / sunshine_id / f"thumb_{filename}"
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        thumbnail_image.save(thumbnail_path, quality=80, optimize=True)
        
        # Return URLs
        gallery_url = f"/static/uploads/{folder}/{user_id}/{sunshine_id}/{filename}"
        thumbnail_url = f"/static/uploads/thumbnails/{user_id}/{sunshine_id}/thumb_{filename}"
        
        return gallery_url, thumbnail_url
    
    async def upload_multiple_photos(
        self,
        files: List[UploadFile],
        user_id: str,
        sunshine_id: str,
        photo_type: str
    ) -> List[Tuple[str, str, str]]:
        """Upload multiple photos at once"""
        results = []
        
        for file in files:
            try:
                if photo_type == "profile":
                    url, thumbnail = await self.upload_profile_photo(file, user_id, sunshine_id)
                else:
                    url, thumbnail = await self.upload_gallery_photo(file, user_id, sunshine_id, photo_type)
                
                results.append((file.filename, url, thumbnail))
            except Exception as e:
                # Log error but continue with other files
                results.append((file.filename, None, str(e)))
        
        return results
    
    async def delete_photo(self, photo_url: str) -> bool:
        """Delete a photo and its thumbnail"""
        try:
            # Convert URL to file path
            if photo_url.startswith("/static/"):
                photo_url = photo_url.replace("/static/", "static/")
            
            photo_path = Path(photo_url)
            
            # Delete main photo
            if photo_path.exists():
                photo_path.unlink()
            
            # Try to delete thumbnail
            thumbnail_path = photo_path.parent.parent / "thumbnails" / photo_path.parent.name / f"thumb_{photo_path.name}"
            if thumbnail_path.exists():
                thumbnail_path.unlink()
            
            return True
        except Exception:
            return False
    
    async def get_photo_metadata(self, photo_path: str) -> dict:
        """Extract metadata from photo for AI processing"""
        try:
            image = Image.open(photo_path)
            
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": os.path.getsize(photo_path)
            }
            
            # Extract EXIF data if available
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                metadata["exif"] = {k: v for k, v in exif.items() if k in [271, 272, 274, 282, 283]}
            
            return metadata
        except Exception:
            return {}
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up temporary files older than specified hours"""
        import time
        temp_dir = self.UPLOAD_BASE_PATH / "temp"
        current_time = time.time()
        
        for file_path in temp_dir.iterdir():
            if file_path.is_file():
                file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
                if file_age_hours > max_age_hours:
                    file_path.unlink()


# Global instance
file_upload_service = FileUploadService()