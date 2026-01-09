"""
Directory RAG Search Tool.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class DirectoryRAGSearchTool(BaseTool):
    """
    Tool for RAG search across all documents in a directory.
    
    Supports multiple file types:
    - PDF, DOCX, MD, TXT, JSON, CSV, XML
    - Recursive directory scanning
    - Unified search across all documents
    """
    
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'pdf',
        '.docx': 'docx',
        '.doc': 'docx',
        '.md': 'markdown',
        '.mdx': 'markdown',
        '.txt': 'text',
        '.json': 'json',
        '.csv': 'csv',
        '.xml': 'xml',
    }
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        super().__init__(config or ToolConfig(
            name="DirectoryRAGSearchTool",
            description="RAG search across documents in a directory"
        ))
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunks: List[Dict] = []
        self._indexed_files: List[str] = []
    
    def _execute(
        self,
        query: str,
        directory: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        top_k: int = 5,
        reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Search documents in directory.
        
        Args:
            query: Search query
            directory: Directory path to search
            extensions: File extensions to include
            recursive: Search subdirectories
            top_k: Number of results
            reindex: Force reindexing
            
        Returns:
            Dict with search results
        """
        if directory and (reindex or not self._chunks):
            self._index_directory(directory, extensions, recursive)
        
        if not self._chunks:
            return {
                'query': query,
                'results': [],
                'total_chunks': 0,
                'indexed_files': [],
            }
        
        results = self._search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
            'indexed_files': self._indexed_files,
        }
    
    def _index_directory(
        self,
        directory: str,
        extensions: Optional[List[str]],
        recursive: bool,
    ):
        """Index all documents in directory."""
        dir_path = Path(directory)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory}")
        
        self._chunks = []
        self._indexed_files = []
        
        # Get all files
        if recursive:
            files = list(dir_path.rglob('*'))
        else:
            files = list(dir_path.glob('*'))
        
        # Filter by extension
        valid_extensions = set(extensions or self.SUPPORTED_EXTENSIONS.keys())
        files = [
            f for f in files
            if f.is_file() and f.suffix.lower() in valid_extensions
        ]
        
        for file_path in files:
            try:
                chunks = self._extract_file_chunks(file_path)
                self._chunks.extend(chunks)
                self._indexed_files.append(str(file_path))
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
    
    def _extract_file_chunks(self, file_path: Path) -> List[Dict]:
        """Extract chunks from a file based on its type."""
        ext = file_path.suffix.lower()
        file_type = self.SUPPORTED_EXTENSIONS.get(ext)
        
        if file_type == 'pdf':
            return self._extract_pdf(file_path)
        elif file_type == 'docx':
            return self._extract_docx(file_path)
        elif file_type == 'markdown':
            return self._extract_text(file_path)
        elif file_type == 'text':
            return self._extract_text(file_path)
        elif file_type == 'json':
            return self._extract_json(file_path)
        elif file_type == 'csv':
            return self._extract_csv(file_path)
        elif file_type == 'xml':
            return self._extract_xml(file_path)
        
        return []
    
    def _extract_pdf(self, path: Path) -> List[Dict]:
        """Extract chunks from PDF."""
        try:
            import PyPDF2
        except ImportError:
            try:
                import pypdf as PyPDF2
            except ImportError:
                logger.warning("PDF support requires: pip install PyPDF2")
                return []
        
        chunks = []
        
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    page_chunks = self._chunk_text(text)
                    for chunk in page_chunks:
                        chunk['source'] = str(path)
                        chunk['page'] = i + 1
                        chunk['type'] = 'pdf'
                        chunks.append(chunk)
        
        return chunks
    
    def _extract_docx(self, path: Path) -> List[Dict]:
        """Extract chunks from DOCX."""
        try:
            from docx import Document
        except ImportError:
            logger.warning("DOCX support requires: pip install python-docx")
            return []
        
        doc = Document(path)
        full_text = '\n'.join(p.text for p in doc.paragraphs)
        
        chunks = self._chunk_text(full_text)
        for chunk in chunks:
            chunk['source'] = str(path)
            chunk['type'] = 'docx'
        
        return chunks
    
    def _extract_text(self, path: Path) -> List[Dict]:
        """Extract chunks from text file."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunks = self._chunk_text(content)
        for chunk in chunks:
            chunk['source'] = str(path)
            chunk['type'] = 'text'
        
        return chunks
    
    def _extract_json(self, path: Path) -> List[Dict]:
        """Extract chunks from JSON file."""
        import json
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to string representation
        text = json.dumps(data, indent=2)
        
        chunks = self._chunk_text(text)
        for chunk in chunks:
            chunk['source'] = str(path)
            chunk['type'] = 'json'
        
        return chunks
    
    def _extract_csv(self, path: Path) -> List[Dict]:
        """Extract chunks from CSV file."""
        import csv
        
        chunks = []
        
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Group rows into chunks
        chunk_size = 10
        for i in range(0, len(rows), chunk_size):
            batch = rows[i:i + chunk_size]
            text = '\n'.join(
                ' '.join(f"{k}: {v}" for k, v in row.items())
                for row in batch
            )
            chunks.append({
                'text': text,
                'source': str(path),
                'type': 'csv',
                'rows': f"{i+1}-{min(i+chunk_size, len(rows))}",
            })
        
        return chunks
    
    def _extract_xml(self, path: Path) -> List[Dict]:
        """Extract chunks from XML file."""
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(path)
        root = tree.getroot()
        
        text = ET.tostring(root, encoding='unicode', method='text')
        
        chunks = self._chunk_text(text)
        for chunk in chunks:
            chunk['source'] = str(path)
            chunk['type'] = 'xml'
        
        return chunks
    
    def _chunk_text(self, text: str) -> List[Dict]:
        """Chunk text into smaller pieces."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            if len(chunk_text) >= 50:
                chunks.append({'text': chunk_text})
        
        return chunks
    
    def _search(self, query: str, top_k: int) -> List[Dict]:
        """Search chunks for query."""
        query_terms = set(query.lower().split())
        results = []
        
        for chunk in self._chunks:
            chunk_terms = set(chunk['text'].lower().split())
            overlap = len(query_terms & chunk_terms)
            
            if overlap > 0:
                score = overlap / len(query_terms)
                result = {
                    'text': chunk['text'][:500],  # Truncate for readability
                    'source': chunk.get('source'),
                    'type': chunk.get('type'),
                    'score': score,
                }
                if 'page' in chunk:
                    result['page'] = chunk['page']
                results.append(result)
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def clear_index(self):
        """Clear the search index."""
        self._chunks = []
        self._indexed_files = []


__all__ = ['DirectoryRAGSearchTool']
