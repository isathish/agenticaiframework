"""
AI Generation Tools (DALL-E, Vision).
"""

import logging
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..base import BaseTool, AsyncBaseTool, ToolConfig

logger = logging.getLogger(__name__)


class DALLETool(AsyncBaseTool):
    """
    Tool for image generation using DALL-E.
    
    Features:
    - Text-to-image generation
    - Image variations
    - Image editing
    - Multiple sizes and quality options
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
        model: str = 'dall-e-3',
    ):
        super().__init__(config or ToolConfig(
            name="DALLETool",
            description="Generate images using DALL-E"
        ))
        self.api_key = api_key or self.config.api_key
        self.model = model
    
    async def _execute_async(
        self,
        prompt: str,
        size: str = '1024x1024',
        quality: str = 'standard',
        style: str = 'vivid',
        n: int = 1,
        response_format: str = 'url',
        save_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate image from prompt.
        
        Args:
            prompt: Image description
            size: Image size (1024x1024, 1792x1024, 1024x1792)
            quality: 'standard' or 'hd'
            style: 'vivid' or 'natural'
            n: Number of images (1 for dall-e-3)
            response_format: 'url' or 'b64_json'
            save_path: Path to save image
            
        Returns:
            Dict with generated images
        """
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
        except ImportError:
            raise ImportError("DALL-E requires: pip install openai")
        
        client = openai.OpenAI(api_key=self.api_key)
        
        response = client.images.generate(
            model=self.model,
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=n,
            response_format=response_format,
        )
        
        images = []
        for i, image in enumerate(response.data):
            img_data = {
                'revised_prompt': image.revised_prompt,
            }
            
            if response_format == 'url':
                img_data['url'] = image.url
            else:
                img_data['b64_json'] = image.b64_json
                
                # Save if path provided
                if save_path:
                    path = Path(save_path)
                    if n > 1:
                        path = path.with_stem(f"{path.stem}_{i}")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(path, 'wb') as f:
                        f.write(base64.b64decode(image.b64_json))
                    img_data['saved_path'] = str(path)
            
            images.append(img_data)
        
        return {
            'prompt': prompt,
            'model': self.model,
            'status': 'success',
            'images': images,
        }
    
    async def create_variation(
        self,
        image_path: str,
        n: int = 1,
        size: str = '1024x1024',
    ) -> Dict[str, Any]:
        """Create variations of an image."""
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        
        with open(image_path, 'rb') as f:
            response = client.images.create_variation(
                image=f,
                n=n,
                size=size,
            )
        
        return {
            'original': image_path,
            'status': 'success',
            'variations': [
                {'url': img.url} for img in response.data
            ],
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class VisionTool(BaseTool):
    """
    Tool for image analysis using vision models.
    
    Features:
    - Image description
    - Object detection
    - Text extraction
    - Visual Q&A
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
        model: str = 'gpt-4-vision-preview',
    ):
        super().__init__(config or ToolConfig(
            name="VisionTool",
            description="Analyze images using vision models"
        ))
        self.api_key = api_key or self.config.api_key
        self.model = model
    
    def _execute(
        self,
        image: Union[str, List[str]],
        prompt: str = "Describe this image in detail.",
        max_tokens: int = 1000,
        detail: str = 'auto',
    ) -> Dict[str, Any]:
        """
        Analyze image(s).
        
        Args:
            image: Image path, URL, or base64 string (or list)
            prompt: Question or instruction
            max_tokens: Maximum response tokens
            detail: 'auto', 'low', or 'high'
            
        Returns:
            Dict with analysis results
        """
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
        except ImportError:
            raise ImportError("Vision requires: pip install openai")
        
        client = openai.OpenAI(api_key=self.api_key)
        
        # Prepare image content
        images = image if isinstance(image, list) else [image]
        image_content = []
        
        for img in images:
            img_data = self._prepare_image(img, detail)
            image_content.append(img_data)
        
        # Build message content
        content = [{"type": "text", "text": prompt}]
        content.extend(image_content)
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
        )
        
        return {
            'prompt': prompt,
            'model': self.model,
            'status': 'success',
            'analysis': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
            },
        }
    
    def _prepare_image(self, image: str, detail: str) -> Dict:
        """Prepare image for API."""
        if image.startswith('http://') or image.startswith('https://'):
            return {
                "type": "image_url",
                "image_url": {"url": image, "detail": detail},
            }
        elif Path(image).exists():
            # Read and encode file
            with open(image, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = Path(image).suffix.lower()
            mime = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.gif': 'gif', '.webp': 'webp'}
            media_type = mime.get(ext, 'png')
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{media_type};base64,{b64}",
                    "detail": detail,
                },
            }
        else:
            # Assume base64
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image}",
                    "detail": detail,
                },
            }
    
    def extract_text(self, image: str) -> Dict[str, Any]:
        """Extract text from image."""
        return self._execute(
            image=image,
            prompt="Extract and return all text visible in this image. Format it clearly.",
        )
    
    def describe_objects(self, image: str) -> Dict[str, Any]:
        """Describe objects in image."""
        return self._execute(
            image=image,
            prompt="List and describe all objects visible in this image with their positions.",
        )


__all__ = ['DALLETool', 'VisionTool']
