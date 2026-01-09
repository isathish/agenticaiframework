"""
Document RAG Search Tools for various file formats.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import csv

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class BaseRAGSearchTool(BaseTool):
    """Base class for RAG search tools."""
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        super().__init__(config or ToolConfig(name="BaseRAGSearchTool"))
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunks: List[Dict] = []
    
    def _chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Chunk text into smaller pieces."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            if len(chunk_text) >= 50:
                chunk = {
                    'text': chunk_text,
                    'start_idx': i,
                    **(metadata or {}),
                }
                chunks.append(chunk)
        
        return chunks
    
    def _simple_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Simple keyword-based search."""
        query_terms = set(query.lower().split())
        results = []
        
        for chunk in self._chunks:
            chunk_terms = set(chunk['text'].lower().split())
            overlap = len(query_terms & chunk_terms)
            
            if overlap > 0:
                score = overlap / len(query_terms)
                results.append({**chunk, 'score': score})
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]


class DOCXRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for DOCX documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="DOCXRAGSearchTool",
                description="RAG search in DOCX documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        docx_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search DOCX documents."""
        if docx_paths:
            self._index_documents(docx_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, docx_paths: List[str]):
        """Index DOCX documents."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("DOCX support requires: pip install python-docx")
        
        self._chunks = []
        
        for docx_path in docx_paths:
            path = Path(docx_path)
            if not path.exists():
                continue
            
            doc = Document(path)
            full_text = '\n'.join(p.text for p in doc.paragraphs)
            
            chunks = self._chunk_text(full_text, {'source': str(path)})
            self._chunks.extend(chunks)


class MDXRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for Markdown/MDX documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="MDXRAGSearchTool",
                description="RAG search in Markdown documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        md_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search Markdown documents."""
        if md_paths:
            self._index_documents(md_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, md_paths: List[str]):
        """Index Markdown documents."""
        self._chunks = []
        
        for md_path in md_paths:
            path = Path(md_path)
            if not path.exists():
                continue
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by headers for better chunking
            sections = self._split_by_headers(content)
            
            for section in sections:
                chunks = self._chunk_text(
                    section['content'],
                    {'source': str(path), 'header': section['header']}
                )
                self._chunks.extend(chunks)
    
    def _split_by_headers(self, content: str) -> List[Dict]:
        """Split content by markdown headers."""
        import re
        
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')
        sections = []
        current = {'header': '', 'content': ''}
        
        for line in lines:
            match = re.match(header_pattern, line)
            if match:
                if current['content'].strip():
                    sections.append(current)
                current = {
                    'header': match.group(2),
                    'content': '',
                }
            else:
                current['content'] += line + '\n'
        
        if current['content'].strip():
            sections.append(current)
        
        return sections


class XMLRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for XML documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="XMLRAGSearchTool",
                description="RAG search in XML documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        xml_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search XML documents."""
        if xml_paths:
            self._index_documents(xml_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, xml_paths: List[str]):
        """Index XML documents."""
        import xml.etree.ElementTree as ET
        
        self._chunks = []
        
        for xml_path in xml_paths:
            path = Path(xml_path)
            if not path.exists():
                continue
            
            tree = ET.parse(path)
            root = tree.getroot()
            
            # Extract text from all elements
            texts = self._extract_xml_text(root)
            
            for text_item in texts:
                chunks = self._chunk_text(
                    text_item['text'],
                    {'source': str(path), 'xpath': text_item['path']}
                )
                self._chunks.extend(chunks)
    
    def _extract_xml_text(self, element, path='') -> List[Dict]:
        """Recursively extract text from XML elements."""
        texts = []
        current_path = f"{path}/{element.tag}"
        
        if element.text and element.text.strip():
            texts.append({
                'text': element.text.strip(),
                'path': current_path,
            })
        
        for child in element:
            texts.extend(self._extract_xml_text(child, current_path))
        
        return texts


class TXTRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for plain text documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="TXTRAGSearchTool",
                description="RAG search in text documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        txt_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search text documents."""
        if txt_paths:
            self._index_documents(txt_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, txt_paths: List[str]):
        """Index text documents."""
        self._chunks = []
        
        for txt_path in txt_paths:
            path = Path(txt_path)
            if not path.exists():
                continue
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = self._chunk_text(content, {'source': str(path)})
            self._chunks.extend(chunks)


class JSONRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for JSON documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="JSONRAGSearchTool",
                description="RAG search in JSON documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        json_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search JSON documents."""
        if json_paths:
            self._index_documents(json_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, json_paths: List[str]):
        """Index JSON documents."""
        self._chunks = []
        
        for json_path in json_paths:
            path = Path(json_path)
            if not path.exists():
                continue
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Flatten and extract text
            texts = self._flatten_json(data)
            
            for text_item in texts:
                chunks = self._chunk_text(
                    str(text_item['value']),
                    {'source': str(path), 'key': text_item['key']}
                )
                self._chunks.extend(chunks)
    
    def _flatten_json(self, obj, prefix='') -> List[Dict]:
        """Flatten JSON to key-value pairs."""
        items = []
        
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{prefix}.{k}" if prefix else k
                items.extend(self._flatten_json(v, new_key))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_key = f"{prefix}[{i}]"
                items.extend(self._flatten_json(v, new_key))
        else:
            items.append({'key': prefix, 'value': obj})
        
        return items


class CSVRAGSearchTool(BaseRAGSearchTool):
    """RAG search tool for CSV documents."""
    
    def __init__(self, config: Optional[ToolConfig] = None, **kwargs):
        super().__init__(
            config or ToolConfig(
                name="CSVRAGSearchTool",
                description="RAG search in CSV documents"
            ),
            **kwargs
        )
    
    def _execute(
        self,
        query: str,
        csv_paths: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Search CSV documents."""
        if csv_paths:
            self._index_documents(csv_paths)
        
        results = self._simple_search(query, top_k)
        
        return {
            'query': query,
            'results': results,
            'total_chunks': len(self._chunks),
        }
    
    def _index_documents(self, csv_paths: List[str]):
        """Index CSV documents."""
        self._chunks = []
        
        for csv_path in csv_paths:
            path = Path(csv_path)
            if not path.exists():
                continue
            
            with open(path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                
                for row_num, row in enumerate(reader, 1):
                    row_text = ' '.join(f"{k}: {v}" for k, v in row.items())
                    self._chunks.append({
                        'text': row_text,
                        'source': str(path),
                        'row': row_num,
                        'data': row,
                    })


__all__ = [
    'DOCXRAGSearchTool',
    'MDXRAGSearchTool',
    'XMLRAGSearchTool',
    'TXTRAGSearchTool',
    'JSONRAGSearchTool',
    'CSVRAGSearchTool',
]
