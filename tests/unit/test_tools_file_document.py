"""
Tests for file_document tools module.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agenticaiframework.tools.file_document.file_tools import FileReadTool, FileWriteTool, DirectoryReadTool
from agenticaiframework.tools.base import ToolConfig


class TestFileReadTool:
    """Tests for FileReadTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = FileReadTool()
        assert tool.encoding == 'utf-8'
        assert tool.max_size_mb == 10.0
        assert tool.config.name == "FileReadTool"
    
    def test_init_custom(self):
        """Test custom initialization."""
        config = ToolConfig(name="CustomReader", description="Custom file reader")
        tool = FileReadTool(config=config, encoding='latin-1', max_size_mb=5.0)
        assert tool.encoding == 'latin-1'
        assert tool.max_size_mb == 5.0
        assert tool.config.name == "CustomReader"
    
    def test_read_text_file(self):
        """Test reading a text file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello, World!\nLine 2\nLine 3")
            temp_path = f.name
        
        try:
            tool = FileReadTool()
            result = tool._execute(file_path=temp_path)
            
            assert 'content' in result
            assert 'Hello, World!' in result['content']
            assert result['file_name'].endswith('.txt')
            assert result['extension'] == '.txt'
            assert 'size_bytes' in result
        finally:
            os.unlink(temp_path)
    
    def test_read_with_line_limit(self):
        """Test reading with line limit."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
            temp_path = f.name
        
        try:
            tool = FileReadTool()
            result = tool._execute(file_path=temp_path, lines=2, start_line=1)
            
            # Should read lines 2-3 (0-indexed)
            assert 'Line 2' in result['content']
            assert 'Line 3' in result['content']
        finally:
            os.unlink(temp_path)
    
    def test_read_nonexistent_file(self):
        """Test reading nonexistent file raises error."""
        tool = FileReadTool()
        with pytest.raises(FileNotFoundError):
            tool._execute(file_path="/nonexistent/path/file.txt")
    
    def test_read_directory_raises_error(self):
        """Test reading directory raises error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = FileReadTool()
            with pytest.raises(ValueError, match="Not a file"):
                tool._execute(file_path=temp_dir)
    
    def test_read_large_file_raises_error(self):
        """Test reading large file raises error."""
        tool = FileReadTool(max_size_mb=0.0001)  # Very small limit
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("x" * 1000)  # Write some content
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="File too large"):
                tool._execute(file_path=temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_read_with_different_encoding(self):
        """Test reading with different encoding."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Test content")
            temp_path = f.name
        
        try:
            tool = FileReadTool()
            result = tool._execute(file_path=temp_path, encoding='utf-8')
            assert 'Test content' in result['content']
        finally:
            os.unlink(temp_path)


class TestFileWriteTool:
    """Tests for FileWriteTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = FileWriteTool()
        assert tool.config.name == "FileWriteTool"
    
    def test_write_text_file(self):
        """Test writing a text file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            
            tool = FileWriteTool()
            result = tool._execute(file_path=file_path, content="Hello, World!")
            
            assert 'file_path' in result
            assert os.path.exists(file_path)
            
            with open(file_path, 'r') as f:
                assert f.read() == "Hello, World!"
    
    def test_write_creates_directory(self):
        """Test that writing creates parent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "subdir", "test.txt")
            
            tool = FileWriteTool(create_dirs=True)
            result = tool._execute(file_path=file_path, content="Test")
            
            assert 'file_path' in result
            assert os.path.exists(file_path)
    
    def test_write_append_mode(self):
        """Test appending to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Initial content\n")
            temp_path = f.name
        
        try:
            tool = FileWriteTool()
            result = tool._execute(file_path=temp_path, content="Appended content", mode='a')
            
            assert result['mode'] == 'a'
            
            with open(temp_path, 'r') as f:
                content = f.read()
                assert "Initial content" in content
                assert "Appended content" in content
        finally:
            os.unlink(temp_path)


class TestDirectoryReadTool:
    """Tests for DirectoryReadTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = DirectoryReadTool()
        assert tool.config.name == "DirectoryReadTool"
    
    def test_list_directory(self):
        """Test listing directory contents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files and directories
            Path(temp_dir, "file1.txt").touch()
            Path(temp_dir, "file2.py").touch()
            Path(temp_dir, "subdir").mkdir()
            
            tool = DirectoryReadTool()
            result = tool._execute(directory=temp_dir)
            
            # Result should have items
            assert 'items' in result
            assert result['total_items'] == 3
    
    def test_list_with_pattern(self):
        """Test listing with pattern filter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "file1.txt").touch()
            Path(temp_dir, "file2.py").touch()
            Path(temp_dir, "file3.txt").touch()
            
            tool = DirectoryReadTool()
            result = tool._execute(directory=temp_dir, pattern="*.txt")
            
            assert result['total_items'] == 2
    
    def test_list_nonexistent_directory(self):
        """Test listing nonexistent directory."""
        tool = DirectoryReadTool()
        with pytest.raises(FileNotFoundError):
            tool._execute(directory="/nonexistent/path")


class TestDocumentTools:
    """Tests for document processing tools."""
    
    def test_document_tool_import(self):
        """Test that document tools can be imported."""
        from agenticaiframework.tools.file_document.document_tools import (
            DOCXRAGSearchTool,
            MDXRAGSearchTool,
            XMLRAGSearchTool,
            TXTRAGSearchTool,
            JSONRAGSearchTool,
            CSVRAGSearchTool,
        )
        assert DOCXRAGSearchTool is not None
        assert MDXRAGSearchTool is not None
        assert XMLRAGSearchTool is not None
        assert TXTRAGSearchTool is not None
        assert JSONRAGSearchTool is not None
        assert CSVRAGSearchTool is not None
    
    def test_docx_tool_init(self):
        """Test DOCXRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import DOCXRAGSearchTool
        tool = DOCXRAGSearchTool()
        assert tool.config.name == "DOCXRAGSearchTool"
    
    def test_txt_tool_init(self):
        """Test TXTRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import TXTRAGSearchTool
        tool = TXTRAGSearchTool()
        assert tool.config.name == "TXTRAGSearchTool"
    
    def test_json_tool_init(self):
        """Test JSONRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.document_tools import JSONRAGSearchTool
        tool = JSONRAGSearchTool()
        assert tool.config.name == "JSONRAGSearchTool"


class TestPDFTools:
    """Tests for PDF tools."""
    
    def test_pdf_tool_import(self):
        """Test that PDF tools can be imported."""
        from agenticaiframework.tools.file_document.pdf_tools import (
            PDFTextWritingTool,
            PDFRAGSearchTool,
        )
        assert PDFTextWritingTool is not None
        assert PDFRAGSearchTool is not None
    
    def test_pdf_text_writing_init(self):
        """Test PDFTextWritingTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFTextWritingTool
        tool = PDFTextWritingTool()
        assert tool.config.name == "PDFTextWritingTool"
    
    def test_pdf_rag_search_init(self):
        """Test PDFRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.pdf_tools import PDFRAGSearchTool
        tool = PDFRAGSearchTool()
        assert tool.config.name == "PDFRAGSearchTool"


class TestDirectoryRAGSearchTool:
    """Tests for directory RAG search tool."""
    
    def test_directory_rag_import(self):
        """Test that directory RAG tools can be imported."""
        from agenticaiframework.tools.file_document.directory_tools import (
            DirectoryRAGSearchTool,
        )
        assert DirectoryRAGSearchTool is not None
    
    def test_directory_rag_init(self):
        """Test DirectoryRAGSearchTool initialization."""
        from agenticaiframework.tools.file_document.directory_tools import DirectoryRAGSearchTool
        tool = DirectoryRAGSearchTool()
        assert tool.config.name == "DirectoryRAGSearchTool"


class TestOCRTools:
    """Tests for OCR tools."""
    
    def test_ocr_tool_import(self):
        """Test that OCR tools can be imported."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        assert OCRTool is not None
    
    def test_ocr_tool_init(self):
        """Test OCRTool initialization."""
        from agenticaiframework.tools.file_document.ocr_tools import OCRTool
        tool = OCRTool()
        assert tool.config.name == "OCRTool"


class TestToolBaseInheritance:
    """Tests for tool base class inheritance."""
    
    def test_file_read_inherits_base_tool(self):
        """Test FileReadTool inherits from BaseTool."""
        from agenticaiframework.tools.base import BaseTool
        tool = FileReadTool()
        assert isinstance(tool, BaseTool)
    
    def test_file_write_inherits_base_tool(self):
        """Test FileWriteTool inherits from BaseTool."""
        from agenticaiframework.tools.base import BaseTool
        tool = FileWriteTool()
        assert isinstance(tool, BaseTool)
    
    def test_directory_read_inherits_base_tool(self):
        """Test DirectoryReadTool inherits from BaseTool."""
        from agenticaiframework.tools.base import BaseTool
        tool = DirectoryReadTool()
        assert isinstance(tool, BaseTool)
