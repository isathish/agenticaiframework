"""
PDF Tools for reading, writing, and searching PDFs.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class PDFTextWritingTool(BaseTool):
    """
    Tool for creating and writing PDF documents.
    
    Supports:
    - Create new PDFs with text
    - Add pages to existing PDFs
    - Text formatting (font, size, color)
    - Tables and simple layouts
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        font_name: str = 'Helvetica',
        font_size: int = 12,
    ):
        super().__init__(config or ToolConfig(
            name="PDFTextWritingTool",
            description="Create and write PDF documents"
        ))
        self.font_name = font_name
        self.font_size = font_size
    
    def _execute(
        self,
        output_path: str,
        content: str,
        title: Optional[str] = None,
        font_name: Optional[str] = None,
        font_size: Optional[int] = None,
        page_size: str = 'A4',
    ) -> Dict[str, Any]:
        """
        Create PDF with text content.
        
        Args:
            output_path: Path for output PDF
            content: Text content to write
            title: PDF title/header
            font_name: Font name
            font_size: Font size in points
            page_size: Page size (A4, Letter, etc.)
            
        Returns:
            Dict with creation result
        """
        try:
            from reportlab.lib.pagesizes import A4, LETTER
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        except ImportError:
            raise ImportError("PDF writing requires: pip install reportlab")
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        sizes = {'A4': A4, 'LETTER': LETTER}
        size = sizes.get(page_size.upper(), A4)
        
        doc = SimpleDocTemplate(str(path), pagesize=size)
        styles = getSampleStyleSheet()
        
        story = []
        
        if title:
            title_style = styles['Title']
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 0.5 * inch))
        
        # Split content into paragraphs
        paragraphs = content.split('\n\n')
        normal_style = styles['Normal']
        
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.replace('\n', '<br/>'), normal_style))
                story.append(Spacer(1, 0.2 * inch))
        
        doc.build(story)
        
        return {
            'output_path': str(path.absolute()),
            'file_name': path.name,
            'page_size': page_size,
            'title': title,
            'paragraphs': len(paragraphs),
        }


class PDFRAGSearchTool(BaseTool):
    """
    Tool for RAG (Retrieval-Augmented Generation) search in PDFs.
    
    Supports:
    - Extract text from PDFs
    - Chunk text for embedding
    - Semantic search with embeddings
    - Multiple PDF processing
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        embedding_model: str = 'text-embedding-ada-002',
    ):
        super().__init__(config or ToolConfig(
            name="PDFRAGSearchTool",
            description="RAG search in PDF documents"
        ))
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self._index: Dict[str, List[Dict]] = {}
    
    def _execute(
        self,
        query: str,
        pdf_paths: Optional[List[str]] = None,
        top_k: int = 5,
        min_score: float = 0.5,
        reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Search PDFs using RAG.
        
        Args:
            query: Search query
            pdf_paths: List of PDF paths to search
            top_k: Number of results to return
            min_score: Minimum similarity score
            reindex: Force reindexing of PDFs
            
        Returns:
            Dict with search results
        """
        if pdf_paths and (reindex or not self._index):
            self._build_index(pdf_paths)
        
        if not self._index:
            return {
                'query': query,
                'results': [],
                'total_chunks': 0,
                'message': 'No PDFs indexed',
            }
        
        # Get query embedding
        query_embedding = self._get_embedding(query)
        
        # Search all chunks
        results = []
        for pdf_path, chunks in self._index.items():
            for chunk in chunks:
                score = self._cosine_similarity(
                    query_embedding, chunk['embedding']
                )
                if score >= min_score:
                    results.append({
                        'pdf_path': pdf_path,
                        'text': chunk['text'],
                        'page': chunk['page'],
                        'score': score,
                    })
        
        # Sort by score and limit
        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:top_k]
        
        return {
            'query': query,
            'results': results,
            'total_chunks': sum(len(c) for c in self._index.values()),
            'pdfs_searched': len(self._index),
        }
    
    def _build_index(self, pdf_paths: List[str]):
        """Build search index from PDFs."""
        self._index = {}
        
        for pdf_path in pdf_paths:
            path = Path(pdf_path)
            if not path.exists():
                logger.warning(f"PDF not found: {pdf_path}")
                continue
            
            text_by_page = self._extract_pdf_text(path)
            chunks = self._chunk_text(text_by_page)
            
            # Get embeddings for chunks
            for chunk in chunks:
                chunk['embedding'] = self._get_embedding(chunk['text'])
            
            self._index[str(path)] = chunks
    
    def _extract_pdf_text(self, path: Path) -> Dict[int, str]:
        """Extract text from PDF by page."""
        try:
            import PyPDF2
        except ImportError:
            try:
                import pypdf as PyPDF2
            except ImportError:
                raise ImportError(
                    "PDF extraction requires: pip install PyPDF2 or pip install pypdf"
                )
        
        text_by_page = {}
        
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    text_by_page[i + 1] = text
        
        return text_by_page
    
    def _chunk_text(self, text_by_page: Dict[int, str]) -> List[Dict]:
        """Chunk text with page tracking."""
        chunks = []
        
        for page, text in text_by_page.items():
            words = text.split()
            
            for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                chunk_words = words[i:i + self.chunk_size]
                chunk_text = ' '.join(chunk_words)
                
                if len(chunk_text) >= 50:  # Minimum chunk length
                    chunks.append({
                        'text': chunk_text,
                        'page': page,
                        'start_idx': i,
                    })
        
        return chunks
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        api_key = self.config.api_key
        
        if api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model=self.embedding_model,
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(f"OpenAI embedding failed: {e}")
        
        # Fallback to simple hash-based embedding
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        return [b / 255.0 for b in hash_bytes]  # Normalize to [0, 1]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        import math
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def add_pdf(self, pdf_path: str):
        """Add a PDF to the index."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        text_by_page = self._extract_pdf_text(path)
        chunks = self._chunk_text(text_by_page)
        
        for chunk in chunks:
            chunk['embedding'] = self._get_embedding(chunk['text'])
        
        self._index[str(path)] = chunks
    
    def clear_index(self):
        """Clear the search index."""
        self._index.clear()


__all__ = ['PDFTextWritingTool', 'PDFRAGSearchTool']
