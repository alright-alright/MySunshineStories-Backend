import openai
import os
import requests
from typing import List, Optional, Dict
from PIL import Image
import io
import base64
from app.models.story import StoryScene

class PhotoProcessor:
    """Analyzes uploaded photos to extract character features for consistent AI generation"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def analyze_photo(self, image_bytes: bytes, person_name: str, relationship: str = "child") -> str:
        """Use GPT-4 Vision to analyze photo and return character description"""
        try:
            # Convert bytes to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at describing people's appearance for cartoon character creation. Focus on safe, positive features suitable for children's illustrations."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Please describe this {relationship} named {person_name} for creating a cartoon character. Focus on: hair color/style, eye color, skin tone, and any distinctive but appropriate features. Keep it positive and child-friendly. Respond in 2-3 sentences."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error analyzing photo for {person_name}: {e}")
            # Fallback generic description
            return f"{person_name} is a cheerful {relationship} with a warm smile and kind eyes."

class ImageGeneratorService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.photo_processor = PhotoProcessor()
        self.character_descriptions = {}  # Cache for consistent character rendering
    
    def set_character_from_photo(self, person_name: str, image_bytes: bytes, relationship: str = "child"):
        """Analyze uploaded photo and store character description for consistent rendering"""
        description = self.photo_processor.analyze_photo(image_bytes, person_name, relationship)
        self.character_descriptions[person_name.lower()] = description
        print(f"Character description for {person_name}: {description}")
    
    def generate_images(self, scenes: List[StoryScene], child_name: str, uploaded_photos: Optional[Dict[str, bytes]] = None) -> List[str]:
        """Generate images for each scene using DALL-E, incorporating uploaded photos for character likeness"""
        
        # Process uploaded photos first
        if uploaded_photos:
            for person_name, image_bytes in uploaded_photos.items():
                # Determine relationship (could be enhanced with metadata)
                relationship = "child" if person_name.lower() == child_name.lower() else "family member"
                self.set_character_from_photo(person_name, image_bytes, relationship)
        
        image_urls = []
        
        for scene in scenes:
            try:
                # Create character-aware prompt
                enhanced_prompt = self._create_character_aware_prompt(scene, child_name)
                
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )
                
                image_urls.append(response.data[0].url)
                
            except Exception as e:
                print(f"Error generating image for scene {scene.scene_number}: {e}")
                # Add placeholder URL
                image_urls.append("https://via.placeholder.com/1024x1024/87CEEB/FFFFFF?text=Story+Illustration")
        
        return image_urls
    
    def _create_character_aware_prompt(self, scene: StoryScene, child_name: str) -> str:
        """Create DALL-E prompt that incorporates character descriptions from photos"""
        
        # Start with base scene description
        base_prompt = scene.image_prompt
        
        # Add character descriptions if available
        character_details = ""
        child_name_lower = child_name.lower()
        
        if child_name_lower in self.character_descriptions:
            character_details = f"The main character {child_name} should look like: {self.character_descriptions[child_name_lower]}. "
        
        # Add other family members if mentioned in the scene
        for name, description in self.character_descriptions.items():
            if name != child_name_lower and name in base_prompt.lower():
                character_details += f"The character {name.title()} should look like: {description}. "
        
        # Build final prompt
        enhanced_prompt = f"""
Children's book illustration, warm cartoon style, soft colors:
{base_prompt}

Character Appearance Guidelines:
{character_details}

Style Requirements:
- Digital illustration, child-friendly cartoon style
- Warm, bright lighting and safe environment  
- Encouraging, positive mood
- Avoid photorealistic rendering - keep it stylized and appropriate for children
- Consistent character appearance throughout the story
"""
        
        return enhanced_prompt.strip()
    
    def download_image(self, url: str) -> bytes:
        """Download image from URL and return bytes"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error downloading image: {e}")
            return b""
    
    def clear_character_cache(self):
        """Clear stored character descriptions (useful for new stories)"""
        self.character_descriptions.clear()

# Utility functions for photo handling
def resize_uploaded_image(image_bytes: bytes, max_size: int = 512) -> bytes:
    """Resize uploaded image to reduce API costs while maintaining quality"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        if max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Save back to bytes
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=85)
        return output.getvalue()
        
    except Exception as e:
        print(f"Error resizing image: {e}")
        return image_bytes  # Return original if resize fails

def validate_image_file(image_bytes: bytes) -> bool:
    """Validate that uploaded file is a valid image"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Check if it's a valid image format
        return image.format in ['JPEG', 'JPG', 'PNG', 'WEBP']
    except Exception:
        return False
