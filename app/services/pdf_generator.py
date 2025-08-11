from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import os
from typing import List, Optional, Dict
from app.models.story import StoryResponse
from app.services.image_generator import ImageGeneratorService

class PDFGeneratorService:
    def __init__(self):
        self.image_service = ImageGeneratorService()
        
    def create_storybook_pdf(self, story: StoryResponse, uploaded_photos: Optional[Dict[str, bytes]] = None) -> str:
        """Create a beautiful PDF storybook with character likeness from uploaded photos"""
        
        # Clear any previous character cache
        self.image_service.clear_character_cache()
        
        # Generate images for scenes with character awareness
        print(f"Generating {len(story.scenes)} images with character awareness...")
        if uploaded_photos:
            print(f"Using {len(uploaded_photos)} uploaded photos for character likeness")
        
        image_urls = self.image_service.generate_images(
            story.scenes, 
            story.child_name, 
            uploaded_photos
        )
        
        # Create PDF
        filename = f"story_{story.child_name.lower().replace(' ', '_')}.pdf"
        filepath = os.path.join("static", filename)
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Enhanced styles for better readability
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.HexColor('#2E4057'),
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,  # Center
            textColor=colors.HexColor('#5A7A95'),
            fontName='Helvetica-Oblique'
        )
        
        story_style = ParagraphStyle(
            'StoryText',
            parent=styles['Normal'],
            fontSize=14,
            leading=20,
            spaceAfter=12,
            textColor=colors.HexColor('#333333'),
            fontName='Helvetica'
        )
        
        # Build PDF content
        story_content = []
        
        # Title page
        story_content.append(Paragraph(story.story_title, title_style))
        story_content.append(Spacer(1, 20))
        story_content.append(Paragraph(f"A special story for {story.child_name}", subtitle_style))
        
        # Add character info if photos were used
        if uploaded_photos:
            photo_count = len(uploaded_photos)
            photo_text = f"Created with {photo_count} personal photo{'s' if photo_count > 1 else ''}"
            story_content.append(Spacer(1, 10))
            story_content.append(Paragraph(photo_text, styles['Normal']))
        
        story_content.append(Spacer(1, 40))
        
        # Story text with images - improved layout
        paragraphs = story.story_text.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                story_content.append(Paragraph(paragraph.strip(), story_style))
                story_content.append(Spacer(1, 15))
                
                # Add image if available - better sizing and positioning
                if i < len(image_urls):
                    try:
                        image_bytes = self.image_service.download_image(image_urls[i])
                        if image_bytes:
                            img_buffer = io.BytesIO(image_bytes)
                            
                            # Create image with better sizing
                            img = RLImage(img_buffer, width=4.5*inch, height=4.5*inch)
                            
                            # Center the image
                            story_content.append(Spacer(1, 10))
                            story_content.append(img)
                            story_content.append(Spacer(1, 20))
                            
                            # Add scene caption if desired
                            if i < len(story.scenes):
                                scene_caption = f"Scene {i+1}: {story.scenes[i].description}"
                                caption_style = ParagraphStyle(
                                    'Caption',
                                    parent=styles['Normal'],
                                    fontSize=10,
                                    alignment=1,  # Center
                                    textColor=colors.HexColor('#666666'),
                                    spaceAfter=20
                                )
                                story_content.append(Paragraph(scene_caption, caption_style))
                        
                    except Exception as e:
                        print(f"Error adding image {i}: {e}")
                        # Add placeholder text instead of broken image
                        placeholder_style = ParagraphStyle(
                            'Placeholder',
                            parent=styles['Normal'],
                            fontSize=12,
                            alignment=1,
                            textColor=colors.HexColor('#999999'),
                            spaceAfter=20
                        )
                        story_content.append(Paragraph("[Illustration would appear here]", placeholder_style))
        
        # Add footer with creation timestamp
        story_content.append(Spacer(1, 40))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,
            textColor=colors.HexColor('#888888')
        )
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%B %d, %Y")
        story_content.append(Paragraph(f"Created by LucianTales • {timestamp}", footer_style))
        
        # Build PDF
        try:
            doc.build(story_content)
            print(f"✅ PDF created successfully: {filepath}")
        except Exception as e:
            print(f"❌ Error building PDF: {e}")
            raise
        
        return f"/static/{filename}"
    
    def create_test_pdf(self, child_name: str, uploaded_photos: Dict[str, bytes]) -> str:
        """Create a test PDF to verify photo processing works"""
        
        # Simple test story
        from app.models.story import StoryResponse, StoryScene
        
        test_story = StoryResponse(
            story_title=f"{child_name}'s Photo Test",
            story_text=f"This is a test story for {child_name} to see how uploaded photos are processed into cartoon characters.",
            scenes=[
                StoryScene(
                    scene_number=1,
                    description=f"{child_name} testing photo upload",
                    image_prompt=f"A cartoon illustration of {child_name} waving hello, child-friendly style"
                )
            ],
            child_name=child_name,
            tone="empowering"
        )
        
        return self.create_storybook_pdf(test_story, uploaded_photos)
