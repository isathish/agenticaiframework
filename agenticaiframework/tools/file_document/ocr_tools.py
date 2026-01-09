"""
OCR (Optical Character Recognition) Tools.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class OCRTool(BaseTool):
    """
    Tool for extracting text from images using OCR.
    
    Supports multiple backends:
    - Tesseract OCR (local)
    - Azure Computer Vision
    - Google Cloud Vision
    - AWS Textract
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        backend: str = 'tesseract',
        language: str = 'eng',
    ):
        super().__init__(config or ToolConfig(
            name="OCRTool",
            description="Extract text from images using OCR"
        ))
        self.backend = backend
        self.language = language
        self._backends = {
            'tesseract': self._ocr_tesseract,
            'azure': self._ocr_azure,
            'google': self._ocr_google,
            'aws': self._ocr_aws,
        }
    
    def _execute(
        self,
        image_path: str,
        backend: Optional[str] = None,
        language: Optional[str] = None,
        preprocess: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract text from image.
        
        Args:
            image_path: Path to image file
            backend: OCR backend to use
            language: OCR language code
            preprocess: Apply image preprocessing
            
        Returns:
            Dict with extracted text and metadata
        """
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        valid_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported image format: {path.suffix}")
        
        backend_name = backend or self.backend
        lang = language or self.language
        
        if backend_name not in self._backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        
        ocr_func = self._backends[backend_name]
        result = ocr_func(path, lang, preprocess)
        
        return {
            'text': result['text'],
            'confidence': result.get('confidence', 0.0),
            'image_path': str(path.absolute()),
            'backend': backend_name,
            'language': lang,
            'blocks': result.get('blocks', []),
        }
    
    def _ocr_tesseract(
        self, path: Path, language: str, preprocess: bool
    ) -> Dict[str, Any]:
        """Use Tesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError(
                "Tesseract OCR requires: pip install pytesseract Pillow"
            )
        
        img = Image.open(path)
        
        if preprocess:
            # Convert to grayscale
            img = img.convert('L')
        
        # Get detailed OCR data
        data = pytesseract.image_to_data(
            img, lang=language, output_type=pytesseract.Output.DICT
        )
        
        text = pytesseract.image_to_string(img, lang=language)
        
        # Calculate average confidence
        confidences = [c for c in data['conf'] if c != -1]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Extract text blocks
        blocks = []
        for i, word in enumerate(data['text']):
            if word.strip():
                blocks.append({
                    'text': word,
                    'confidence': data['conf'][i],
                    'bbox': {
                        'x': data['left'][i],
                        'y': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i],
                    },
                })
        
        return {
            'text': text,
            'confidence': avg_confidence / 100,
            'blocks': blocks,
        }
    
    def _ocr_azure(
        self, path: Path, language: str, preprocess: bool
    ) -> Dict[str, Any]:
        """Use Azure Computer Vision."""
        endpoint = self.config.extra_config.get('azure_endpoint')
        api_key = self.config.api_key
        
        if not endpoint or not api_key:
            raise ValueError(
                "Azure OCR requires endpoint and api_key in config"
            )
        
        try:
            from azure.cognitiveservices.vision.computervision import (
                ComputerVisionClient
            )
            from msrest.authentication import CognitiveServicesCredentials
        except ImportError:
            raise ImportError(
                "Azure OCR requires: pip install azure-cognitiveservices-vision-computervision"
            )
        
        client = ComputerVisionClient(
            endpoint,
            CognitiveServicesCredentials(api_key)
        )
        
        with open(path, 'rb') as f:
            result = client.read_in_stream(f, raw=True)
        
        # Get operation location
        operation_location = result.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]
        
        # Wait for result
        import time
        while True:
            read_result = client.get_read_result(operation_id)
            if read_result.status.lower() not in ['notstarted', 'running']:
                break
            time.sleep(1)
        
        text_lines = []
        blocks = []
        
        if read_result.status.lower() == 'succeeded':
            for page in read_result.analyze_result.read_results:
                for line in page.lines:
                    text_lines.append(line.text)
                    blocks.append({
                        'text': line.text,
                        'confidence': line.confidence if hasattr(line, 'confidence') else 1.0,
                        'bbox': line.bounding_box,
                    })
        
        return {
            'text': '\n'.join(text_lines),
            'confidence': 0.9,
            'blocks': blocks,
        }
    
    def _ocr_google(
        self, path: Path, language: str, preprocess: bool
    ) -> Dict[str, Any]:
        """Use Google Cloud Vision."""
        try:
            from google.cloud import vision
        except ImportError:
            raise ImportError(
                "Google OCR requires: pip install google-cloud-vision"
            )
        
        client = vision.ImageAnnotatorClient()
        
        with open(path, 'rb') as f:
            content = f.read()
        
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        
        texts = response.text_annotations
        
        if not texts:
            return {'text': '', 'confidence': 0.0, 'blocks': []}
        
        full_text = texts[0].description
        
        blocks = []
        for text in texts[1:]:
            vertices = text.bounding_poly.vertices
            blocks.append({
                'text': text.description,
                'confidence': 0.9,
                'bbox': {
                    'x': vertices[0].x,
                    'y': vertices[0].y,
                    'width': vertices[1].x - vertices[0].x,
                    'height': vertices[2].y - vertices[0].y,
                },
            })
        
        return {
            'text': full_text,
            'confidence': 0.9,
            'blocks': blocks,
        }
    
    def _ocr_aws(
        self, path: Path, language: str, preprocess: bool
    ) -> Dict[str, Any]:
        """Use AWS Textract."""
        try:
            import boto3
        except ImportError:
            raise ImportError("AWS OCR requires: pip install boto3")
        
        client = boto3.client('textract')
        
        with open(path, 'rb') as f:
            image_bytes = f.read()
        
        response = client.detect_document_text(
            Document={'Bytes': image_bytes}
        )
        
        lines = []
        blocks = []
        
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                lines.append(block['Text'])
                geo = block['Geometry']['BoundingBox']
                blocks.append({
                    'text': block['Text'],
                    'confidence': block['Confidence'] / 100,
                    'bbox': {
                        'x': geo['Left'],
                        'y': geo['Top'],
                        'width': geo['Width'],
                        'height': geo['Height'],
                    },
                })
        
        avg_conf = sum(b['confidence'] for b in blocks) / len(blocks) if blocks else 0
        
        return {
            'text': '\n'.join(lines),
            'confidence': avg_conf,
            'blocks': blocks,
        }


__all__ = ['OCRTool']
