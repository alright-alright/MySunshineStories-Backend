import openai
import os
import json
from typing import Dict, Any
from app.models.story import StoryRequest, StoryResponse, StoryScene

class StoryGeneratorService:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_story(self, request: StoryRequest) -> StoryResponse:
        """Generate a personalized children's story using OpenAI GPT-4"""
        
        prompt = self._build_story_prompt(request)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert children's story writer who creates warm, encouraging social stories that help children overcome fears and challenges. Always respond with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            story_data = json.loads(response.choices[0].message.content)
            
            # Convert to our StoryResponse model
            scenes = [
                StoryScene(
                    scene_number=i+1,
                    description=scene["description"],
                    image_prompt=scene["image_prompt"]
                )
                for i, scene in enumerate(story_data.get("scenes", []))
            ]
            
            return StoryResponse(
                story_title=story_data["story_title"],
                story_text=story_data["story_text"],
                scenes=scenes,
                child_name=request.child_name,
                tone=request.tone.value
            )
            
        except Exception as e:
            print(f"Error generating story: {e}")
            # Fallback story
            return self._create_fallback_story(request)
    
    def _build_story_prompt(self, request: StoryRequest) -> str:
        """Build the GPT prompt for story generation"""
        
        family_context = ""
        if request.family_members:
            family_names = [f"{fm.name} ({fm.relationship})" for fm in request.family_members]
            family_context = f"Family members who support {request.child_name}: {', '.join(family_names)}."
        
        items_context = ""
        if request.favorite_items:
            items_context = f"{request.child_name}'s favorite things: {', '.join(request.favorite_items)}."
        
        age_context = f"Age: approximately {request.age} years old." if request.age else "Age: young child."
        
        tone_guidance = {
            "calm": "gentle, soothing, and reassuring",
            "empowering": "encouraging, brave, and confidence-building", 
            "bedtime": "peaceful, dreamy, and sleepy",
            "adventure": "exciting but safe, fun and engaging"
        }
        
        tone_desc = tone_guidance.get(request.tone.value, "warm and supportive")
        
        return f"""
Create a personalized children's social story to help {request.child_name} overcome their challenge: "{request.fear_or_challenge}".

Context:
- {age_context}
- {family_context}
- {items_context}
- Tone should be: {tone_desc}

Requirements:
1. Story should be 200-400 words, appropriate for young children
2. Include {request.child_name} as the main character who successfully overcomes the challenge
3. Incorporate their favorite items and supportive family members naturally
4. Create 3-4 scenes that show progression from challenge to success
5. End on a positive, empowering note

Return your response as JSON in this exact format:
{{
    "story_title": "A descriptive title for the story",
    "story_text": "The complete story text with proper paragraphs",
    "scenes": [
        {{
            "description": "Description of what happens in this scene",
            "image_prompt": "Detailed prompt for AI image generation showing {request.child_name} in this scene"
        }}
    ]
}}

Make sure the image prompts describe {request.child_name} as a child with diverse, inclusive features and show them in positive, brave situations.
"""
    
    def _create_fallback_story(self, request: StoryRequest) -> StoryResponse:
        """Create a simple fallback story if OpenAI fails"""
        return StoryResponse(
            story_title=f"{request.child_name} and the Big Challenge",
            story_text=f"Once upon a time, there was a brave child named {request.child_name} who faced a challenge with {request.fear_or_challenge}. With the help of family and favorite things, {request.child_name} learned to be brave and overcome this fear. The end.",
            scenes=[
                StoryScene(
                    scene_number=1,
                    description=f"{request.child_name} faces the challenge",
                    image_prompt=f"A young child named {request.child_name} looking thoughtful"
                )
            ],
            child_name=request.child_name,
            tone=request.tone.value
        )
