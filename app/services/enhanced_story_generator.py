"""
Enhanced Story Generation Service with Photo-Based Character Consistency
Integrates authenticated users, Sunshine profiles, subscription validation, and DALL-E 3
"""
import openai
import os
import json
import base64
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from PIL import Image
import io

from app.models.database_models import User, Sunshine, Story, StoryTone, FamilyMember, ComfortItem
from app.models.story import StoryRequest, StoryResponse, StoryScene, FamilyMember as StoryFamilyMember
from app.services.usage_tracking_service import usage_tracking_service
from app.services.image_generator import PhotoProcessor, resize_uploaded_image


class CharacterProfile:
    """Stores detailed character information from photos and user input"""
    def __init__(self, name: str, relationship: str, photo_path: Optional[str] = None):
        self.name = name
        self.relationship = relationship
        self.photo_path = photo_path
        self.visual_description = ""
        self.personality_traits = []
        self.role_in_story = ""


class EnhancedStoryGenerator:
    """Advanced story generator with photo-based character consistency"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.photo_processor = PhotoProcessor()
        self.character_profiles: Dict[str, CharacterProfile] = {}
        
    def generate_personalized_story(
        self,
        user: User,
        sunshine: Sunshine,
        fear_or_challenge: str,
        tone: StoryTone,
        db: Session,
        include_family: bool = True,
        include_comfort_items: bool = True,
        custom_elements: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a fully personalized story using Sunshine profile data and photos
        """
        import time
        start_time = time.time()
        
        print(f"🚀 Starting AI story generation...")
        print(f"🚀 Sunshine: {sunshine.name}, Fear: {fear_or_challenge}, Tone: {tone}")
        
        # Check subscription and usage limits
        print(f"⏰ Step 1: Checking subscription...")
        can_generate, usage_type = usage_tracking_service.can_generate_story(user, db)
        if not can_generate:
            raise ValueError(f"Cannot generate story: {usage_type}")
        print(f"✅ Subscription check passed: {usage_type}")
        
        # Build character profiles from Sunshine data
        print(f"⏰ Step 2: Building character profiles...")
        self._build_character_profiles(sunshine, include_family)
        print(f"✅ Character profiles built")
        
        # Generate story text with GPT-4
        print(f"⏰ Step 3: Generating story with GPT-4...")
        gpt_start = time.time()
        try:
            story_content = self._generate_story_content(
                sunshine=sunshine,
                fear_or_challenge=fear_or_challenge,
                tone=tone,
                include_comfort_items=include_comfort_items,
                custom_elements=custom_elements
            )
            gpt_time = time.time() - gpt_start
            print(f"✅ Story generated in {gpt_time:.2f} seconds")
        except Exception as e:
            print(f"❌ GPT-4 generation failed: {e}")
            raise
        
        # Generate consistent character images with DALL-E 3
        print(f"⏰ Step 4: Generating images with DALL-E 3...")
        dalle_start = time.time()
        try:
            image_urls = self._generate_character_consistent_images(
                scenes=story_content["scenes"],
                sunshine=sunshine
            )
            dalle_time = time.time() - dalle_start
            print(f"✅ Images generated in {dalle_time:.2f} seconds")
        except Exception as e:
            print(f"❌ DALL-E 3 generation failed: {e}")
            # Don't fail the whole story if images fail
            image_urls = []
        
        # Calculate metadata
        word_count = len(story_content["story_text"].split())
        reading_time = max(1, word_count // 200)  # Assume 200 words per minute
        
        # Create story record
        story = Story(
            id=str(uuid.uuid4()),
            user_id=user.id,
            sunshine_id=sunshine.id,
            title=story_content["title"],
            story_text=story_content["story_text"],
            tone=tone,
            child_name=sunshine.name,
            age=self._calculate_age(sunshine.birthdate),
            fear_or_challenge=fear_or_challenge,
            favorite_items=[item.name for item in sunshine.comfort_items] if include_comfort_items else [],
            family_members={fm.name: fm.relation_type for fm in sunshine.family_members} if include_family else {},
            scenes=story_content["scenes"],
            image_urls=image_urls,
            reading_time=reading_time,
            word_count=word_count,
            model_used="gpt-4o",
            generation_time=story_content.get("generation_time", 0),
            prompt_tokens=story_content.get("prompt_tokens", 0),
            completion_tokens=story_content.get("completion_tokens", 0),
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(story)
        
        # Record usage
        usage_tracking_service.record_story_generation(
            user=user,
            story=story,
            db=db,
            usage_type=usage_type
        )
        
        db.commit()
        
        total_time = time.time() - start_time
        print(f"🎉 Story generation complete!")
        print(f"⏱️ Total time: {total_time:.2f} seconds")
        print(f"📖 Story ID: {story.id}")
        print(f"📖 Title: {story.title}")
        print(f"📖 Word count: {word_count}")
        print(f"🖼️ Images: {len(image_urls)}")
        
        return {
            "story_id": story.id,
            "title": story.title,
            "story_text": story.story_text,
            "scenes": story.scenes,
            "image_urls": image_urls,
            "reading_time": reading_time,
            "word_count": word_count,
            "usage_type": usage_type,
            "character_profiles": self._get_character_summaries()
        }
    
    def _build_character_profiles(self, sunshine: Sunshine, include_family: bool = True):
        """Build detailed character profiles from Sunshine data"""
        self.character_profiles.clear()
        
        # COMPREHENSIVE ATTRIBUTE CHECK
        print("🔍 CHECKING ALL SUNSHINE ATTRIBUTES...")
        required_attrs = [
            'name', 'age', 'gender', 'birthdate', 'pronouns', 'nickname',
            'favorite_color', 'favorite_animal', 'favorite_food', 'favorite_activity',
            'favorite_places', 'favorite_activities', 'favorite_foods', 'favorite_colors',
            'personality_traits', 'fears', 'dreams', 'comfort_items', 'family_members',
            'main_photo_url', 'bedtime_routine', 'allergies', 'special_needs',
            'personality_summary', 'additional_notes', 'photos', 'stories'
        ]
        
        missing_attrs = []
        for attr in required_attrs:
            if hasattr(sunshine, attr):
                value = getattr(sunshine, attr)
                # Show first 50 chars if it's a long value
                display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                print(f"✅ {attr}: {display_value}")
            else:
                print(f"❌ MISSING: {attr}")
                missing_attrs.append(attr)
        
        print(f"🔍 ATTRIBUTE CHECK COMPLETE - {len(missing_attrs)} missing attributes")
        
        # ADD DEFAULTS FOR ALL MISSING ATTRIBUTES
        if missing_attrs:
            print("🛠️ Adding defaults for missing attributes...")
            
            # Age calculation if missing
            if 'age' in missing_attrs and hasattr(sunshine, 'birthdate'):
                from datetime import date
                today = date.today()
                sunshine.age = today.year - sunshine.birthdate.year - ((today.month, today.day) < (sunshine.birthdate.month, sunshine.birthdate.day))
                print(f"  📝 Set age = {sunshine.age} (calculated from birthdate)")
            
            # Plural attributes that might be singular
            if 'favorite_places' in missing_attrs:
                sunshine.favorite_places = []
                print(f"  📝 Set favorite_places = []")
            
            if 'favorite_activities' in missing_attrs:
                if hasattr(sunshine, 'favorite_activity') and sunshine.favorite_activity:
                    sunshine.favorite_activities = [sunshine.favorite_activity]
                    print(f"  📝 Set favorite_activities from favorite_activity")
                else:
                    sunshine.favorite_activities = []
                    print(f"  📝 Set favorite_activities = []")
            
            if 'favorite_foods' in missing_attrs:
                if hasattr(sunshine, 'favorite_food') and sunshine.favorite_food:
                    sunshine.favorite_foods = [sunshine.favorite_food]
                    print(f"  📝 Set favorite_foods from favorite_food")
                else:
                    sunshine.favorite_foods = []
                    print(f"  📝 Set favorite_foods = []")
            
            if 'favorite_colors' in missing_attrs:
                if hasattr(sunshine, 'favorite_color') and sunshine.favorite_color:
                    sunshine.favorite_colors = [sunshine.favorite_color]
                    print(f"  📝 Set favorite_colors from favorite_color")
                else:
                    sunshine.favorite_colors = []
                    print(f"  📝 Set favorite_colors = []")
            
            # Other missing attributes with safe defaults
            defaults = {
                'pronouns': 'they/them',
                'nickname': getattr(sunshine, 'name', 'Sunshine'),
                'fears': None,
                'dreams': None,
                'bedtime_routine': None,
                'allergies': None,
                'special_needs': None,
                'personality_summary': None,
                'additional_notes': None,
                'main_photo_url': None,
                'photos': [],
                'stories': [],
                'comfort_items': [],
                'family_members': [],
                'personality_traits': []
            }
            
            for attr, default_value in defaults.items():
                if attr in missing_attrs:
                    setattr(sunshine, attr, default_value)
                    print(f"  📝 Set {attr} = {default_value}")
        
        print("✅ All attributes ready for story generation!")
        
        # Get main photo from photos relationship
        main_photo_url = None
        if hasattr(sunshine, 'photos') and sunshine.photos:
            # Find primary photo or first profile photo
            for photo in sunshine.photos:
                if photo.is_primary or photo.photo_type == "profile":
                    main_photo_url = photo.url
                    break
            # If no primary/profile photo, use first photo
            if not main_photo_url and sunshine.photos:
                main_photo_url = sunshine.photos[0].url
        
        print(f"📸 Main photo URL: {main_photo_url if main_photo_url else 'No photo found'}")
        
        # Main character (child)
        main_character = CharacterProfile(
            name=sunshine.name,
            relationship="main character",
            photo_path=main_photo_url  # Can be None, that's OK
        )
        
        # Analyze main photo if available
        if main_photo_url and os.path.exists(main_photo_url):
            try:
                with open(main_photo_url, 'rb') as f:
                    photo_bytes = f.read()
                    main_character.visual_description = self.photo_processor.analyze_photo(
                        photo_bytes, sunshine.name, "child"
                    )
            except Exception as e:
                print(f"Error analyzing main photo: {e}")
                main_character.visual_description = self._generate_default_child_description(sunshine)
        else:
            main_character.visual_description = self._generate_default_child_description(sunshine)
        
        # Add personality traits
        if sunshine.personality_traits:
            # Handle different types of personality traits data
            if isinstance(sunshine.personality_traits, str):
                # JSON string
                traits = json.loads(sunshine.personality_traits)
            elif isinstance(sunshine.personality_traits, list):
                # List of PersonalityTrait objects or dicts
                traits = []
                for trait in sunshine.personality_traits:
                    if hasattr(trait, 'trait'):
                        # PersonalityTrait object - get the trait string
                        traits.append(trait.trait)
                    elif isinstance(trait, dict) and 'trait' in trait:
                        # Dict with trait key
                        traits.append(trait['trait'])
                    elif isinstance(trait, str):
                        # Already a string
                        traits.append(trait)
                    else:
                        # Try to convert to string
                        traits.append(str(trait))
            else:
                # Fallback
                traits = []
            
            main_character.personality_traits = traits
        
        main_character.role_in_story = "brave protagonist who overcomes challenges"
        self.character_profiles[sunshine.name.lower()] = main_character
        
        # Family members
        if include_family and sunshine.family_members:
            for family_member in sunshine.family_members[:3]:  # Limit to 3 for story focus
                fm_profile = CharacterProfile(
                    name=family_member.name,
                    relationship=family_member.relation_type,
                    photo_path=family_member.photo_url
                )
                
                # Analyze family member photo
                if family_member.photo_url and os.path.exists(family_member.photo_url):
                    try:
                        with open(family_member.photo_url, 'rb') as f:
                            photo_bytes = f.read()
                            fm_profile.visual_description = self.photo_processor.analyze_photo(
                                photo_bytes, family_member.name, family_member.relation_type
                            )
                    except Exception as e:
                        print(f"Error analyzing family photo: {e}")
                        fm_profile.visual_description = f"A caring {family_member.relation_type}"
                else:
                    fm_profile.visual_description = f"A caring {family_member.relation_type}"
                
                fm_profile.role_in_story = f"supportive {family_member.relation_type} who helps {sunshine.name}"
                self.character_profiles[family_member.name.lower()] = fm_profile
    
    def _generate_story_content(
        self,
        sunshine: Sunshine,
        fear_or_challenge: str,
        tone: StoryTone,
        include_comfort_items: bool,
        custom_elements: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate story content with character consistency"""
        import time
        
        print(f"📝 _generate_story_content called")
        print(f"📝 Building prompt for GPT-4...")
        
        # Quick attribute check for story-specific fields
        story_attrs = ['name', 'age', 'gender', 'comfort_items', 'family_members']
        for attr in story_attrs:
            if hasattr(sunshine, attr):
                print(f"  ✅ Story attr {attr}: {getattr(sunshine, attr)}")
            else:
                print(f"  ❌ Story attr MISSING: {attr}")
                # Set default
                if attr == 'age':
                    setattr(sunshine, attr, 5)  # Default age
                else:
                    setattr(sunshine, attr, [] if attr.endswith('s') else None)
        
        # Build character descriptions for the prompt
        character_descriptions = []
        for name, profile in self.character_profiles.items():
            desc = f"- {profile.name} ({profile.relationship}): {profile.visual_description}"
            if profile.personality_traits:
                # Ensure all traits are strings
                trait_strings = [str(t) for t in profile.personality_traits]
                desc += f" Personality: {', '.join(trait_strings)}"
            character_descriptions.append(desc)
        
        # Build comfort items context
        comfort_items = []
        if include_comfort_items and sunshine.comfort_items:
            comfort_items = [item.name for item in sunshine.comfort_items[:2]]
        
        # Add custom elements
        if custom_elements:
            comfort_items.extend(custom_elements)
        
        # Age calculation
        age = self._calculate_age(sunshine.birthdate)
        
        # Tone guidance
        tone_guidance = {
            StoryTone.CALM: "gentle, soothing, and reassuring with soft transitions",
            StoryTone.EMPOWERING: "encouraging, brave, and confidence-building with triumphant moments",
            StoryTone.BEDTIME: "peaceful, dreamy, sleepy with gentle resolution",
            StoryTone.ADVENTURE: "exciting but safe, fun and engaging with positive outcomes"
        }
        
        prompt = f"""
Create a personalized children's social story for {sunshine.name} to help overcome: "{fear_or_challenge}"

CHARACTER PROFILES (maintain consistency throughout):
{chr(10).join(character_descriptions)}

STORY CONTEXT:
- Main character: {sunshine.name}, age {age}
- Comfort items/favorites: {', '.join(comfort_items) if comfort_items else 'None specified'}
- Story tone: {tone_guidance.get(tone, 'warm and supportive')}
- Setting: {sunshine.favorite_places if sunshine.favorite_places else 'familiar, safe environments'}

REQUIREMENTS:
1. Story length: 300-500 words, age-appropriate for {age}-year-old
2. Include {sunshine.name} as the brave protagonist who successfully overcomes the challenge
3. Naturally incorporate family members as supportive characters
4. Include comfort items as helpful tools or companions
5. Create 4-5 scenes showing clear progression from challenge to success
6. Use simple, encouraging language appropriate for the child's age
7. End with {sunshine.name} feeling proud and confident

IMPORTANT: Maintain exact character descriptions throughout for visual consistency.

Return as JSON:
{{
    "title": "Engaging, personalized title",
    "story_text": "Complete story with paragraphs separated by \\n\\n",
    "scenes": [
        {{
            "scene_number": 1,
            "description": "What happens in this scene",
            "characters_present": ["list of characters in scene"],
            "image_prompt": "Detailed visual description for DALL-E including exact character appearances"
        }}
    ],
    "key_message": "The main lesson or encouragement"
}}
"""
        
        try:
            import time
            start_time = time.time()
            
            print(f"🤖 Calling OpenAI GPT-4 API...")
            print(f"🤖 Prompt length: {len(prompt)} characters")
            print(f"🤖 Using model: gpt-4o")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert children's story writer and child psychologist who creates therapeutic social stories. Always maintain character consistency and respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            generation_time = time.time() - start_time
            print(f"✅ GPT-4 API responded in {generation_time:.2f} seconds")
            
            print(f"📝 Parsing JSON response...")
            story_data = json.loads(response.choices[0].message.content)
            print(f"✅ Story parsed: {story_data.get('title', 'No title')}")
            
            # Add metadata
            story_data["generation_time"] = generation_time
            story_data["prompt_tokens"] = response.usage.prompt_tokens
            story_data["completion_tokens"] = response.usage.completion_tokens
            
            return story_data
            
        except Exception as e:
            print(f"Error generating story content: {e}")
            return self._create_fallback_story_content(sunshine, fear_or_challenge)
    
    def _generate_character_consistent_images(
        self,
        scenes: List[Dict],
        sunshine: Sunshine
    ) -> List[str]:
        """Generate images with consistent character appearances using DALL-E 3"""
        
        print(f"🎨 Starting DALL-E 3 image generation for {len(scenes)} scenes...")
        image_urls = []
        
        # Create a consistent character reference
        character_reference = self._create_character_reference()
        print(f"🎨 Character reference created")
        
        for i, scene in enumerate(scenes):
            try:
                print(f"🎨 Generating image {i+1}/{len(scenes)}...")
                
                # Build character-aware prompt
                image_prompt = self._build_consistent_image_prompt(
                    scene=scene,
                    character_reference=character_reference,
                    sunshine_name=sunshine.name
                )
                print(f"🎨 Image prompt length: {len(image_prompt)} characters")
                
                import time
                dalle_start = time.time()
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="hd",  # Use HD quality for better character consistency
                    n=1,
                    style="vivid"  # More vibrant, child-friendly style
                )
                dalle_time = time.time() - dalle_start
                print(f"✅ Image {i+1} generated in {dalle_time:.2f} seconds")
                
                image_urls.append(response.data[0].url)
                
            except Exception as e:
                print(f"❌ Error generating image for scene {scene.get('scene_number', 'unknown')}: {e}")
                # Fallback to placeholder
                image_urls.append(self._get_placeholder_image_url())
        
        return image_urls
    
    def _build_consistent_image_prompt(
        self,
        scene: Dict,
        character_reference: str,
        sunshine_name: str
    ) -> str:
        """Build DALL-E prompt with character consistency instructions"""
        
        # Get characters in this scene
        characters_in_scene = scene.get("characters_present", [sunshine_name])
        
        # Build character descriptions for this scene
        character_details = []
        for character_name in characters_in_scene:
            profile = self.character_profiles.get(character_name.lower())
            if profile:
                character_details.append(
                    f"{profile.name}: {profile.visual_description}"
                )
        
        prompt = f"""
Children's book illustration in warm, friendly cartoon style:

SCENE: {scene.get('description', 'A moment in the story')}

CHARACTER APPEARANCES (MAINTAIN EXACT CONSISTENCY):
{chr(10).join(character_details)}

{character_reference}

STYLE REQUIREMENTS:
- Digital illustration in the style of modern children's picture books
- Soft, warm color palette with gentle gradients
- Characters should have friendly, expressive faces
- Background should be detailed but not distracting
- Lighting: bright and welcoming
- Mood: {scene.get('mood', 'positive and encouraging')}
- Perspective: eye-level with the child character
- Ensure all characters match their descriptions EXACTLY

IMPORTANT: This is scene {scene.get('scene_number', 1)} of a series. Maintain absolute character consistency.
"""
        
        return prompt.strip()
    
    def _create_character_reference(self) -> str:
        """Create a reference string for character consistency"""
        
        references = []
        for name, profile in self.character_profiles.items():
            ref = f"[{profile.name} REFERENCE: {profile.visual_description}]"
            references.append(ref)
        
        return "CHARACTER CONSISTENCY GUIDE:\n" + "\n".join(references)
    
    def _calculate_age(self, birthdate) -> int:
        """Calculate age from birthdate"""
        from datetime import date
        today = date.today()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    
    def _generate_default_child_description(self, sunshine: Sunshine) -> str:
        """Generate a default description when no photo is available"""
        age = self._calculate_age(sunshine.birthdate)
        return f"A cheerful {age}-year-old child with bright eyes and a warm smile, wearing comfortable, colorful clothing"
    
    def _create_fallback_story_content(self, sunshine: Sunshine, fear_or_challenge: str) -> Dict:
        """Create fallback content if generation fails"""
        return {
            "title": f"{sunshine.name}'s Brave Day",
            "story_text": f"Once upon a time, {sunshine.name} faced a challenge with {fear_or_challenge}. With courage and support from loved ones, {sunshine.name} discovered inner strength and overcame the fear. The end.",
            "scenes": [
                {
                    "scene_number": 1,
                    "description": f"{sunshine.name} encounters the challenge",
                    "characters_present": [sunshine.name],
                    "image_prompt": f"A young child named {sunshine.name} looking thoughtful"
                }
            ],
            "key_message": "You are braver than you think",
            "generation_time": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
    
    def _get_placeholder_image_url(self) -> str:
        """Return a placeholder image URL"""
        return "https://via.placeholder.com/1024x1024/E6F3FF/4A90E2?text=Story+Scene"
    
    def _get_character_summaries(self) -> Dict[str, str]:
        """Get summaries of character profiles for response"""
        summaries = {}
        for name, profile in self.character_profiles.items():
            summaries[profile.name] = {
                "relationship": profile.relationship,
                "description": profile.visual_description,
                "role": profile.role_in_story
            }
        return summaries


# Global instance
enhanced_story_generator = EnhancedStoryGenerator()