#!/usr/bin/env python3
"""
Single Agent Examples - Comprehensive Guide

This file demonstrates working examples for:
- Agent without LLM (pure task execution)
- Agent with LLM (text generation)
- Agent with various file/document tools

Requirements:
    pip install agenticaiframework
    export OPENAI_API_KEY="your-key"  # For LLM examples
"""

import os
import json
from pathlib import Path

# Create temp directory for examples
TEMP_DIR = Path("./temp_agent_examples")
TEMP_DIR.mkdir(exist_ok=True)


# =============================================================================
# 1.1 - Single Agent WITHOUT LLM (Pure Task Execution)
# =============================================================================

def example_1_1_agent_without_llm():
    """
    Agent can execute tasks without LLM - useful for:
    - Data processing
    - File operations
    - Calculations
    - Orchestration
    """
    print("\n" + "="*70)
    print("1.1 - AGENT WITHOUT LLM")
    print("="*70)
    
    from agenticaiframework import Agent
    
    # Create agent without LLM
    agent = Agent(
        name="DataProcessor",
        role="Data processing agent",
        capabilities=["processing", "calculation"],
        config={}  # No LLM configured
    )
    agent.start()
    
    # Execute pure Python tasks
    def process_data(data):
        """Process a list of numbers."""
        return {
            'sum': sum(data),
            'avg': sum(data) / len(data),
            'max': max(data),
            'min': min(data)
        }
    
    data = [10, 20, 30, 40, 50]
    result = agent.execute_task(process_data, data)
    
    print(f"📊 Processed data: {data}")
    print(f"📈 Results: {result}")
    print(f"✅ Agent executed task without LLM!")


# =============================================================================
# 1.2 - Single Agent WITH LLM
# =============================================================================

def example_1_2_agent_with_llm():
    """
    Agent with LLM for text generation and reasoning.
    Requires OPENAI_API_KEY environment variable.
    """
    print("\n" + "="*70)
    print("1.2 - AGENT WITH LLM")
    print("="*70)
    
    from agenticaiframework import Agent
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Skipping: OPENAI_API_KEY not set")
        return
    
    # Create agent with auto-configured LLM
    agent = Agent.quick("Assistant", role="assistant")
    
    # Simple LLM call
    result = agent.run(
        "What are the three laws of robotics? Keep it brief.",
        return_full=False  # Just get the response string
    )
    
    print(f"🤖 Agent response:\n{result}")
    print(f"✅ Agent successfully used LLM!")


# =============================================================================
# 1.3 - Single Agent with FileReadTool
# =============================================================================

def example_1_3_agent_with_file_read_tool():
    """Read file content using FileReadTool."""
    print("\n" + "="*70)
    print("1.3 - AGENT WITH FileReadTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import FileReadTool
    
    # Create test file
    test_file = TEMP_DIR / "sample.txt"
    test_file.write_text("Hello from FileReadTool!\nThis is line 2.\nThis is line 3.")
    
    # Create agent
    agent = Agent(
        name="FileReader",
        role="File reading specialist",
        capabilities=["file-read"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(FileReadTool())
    
    # Execute tool
    result = agent.execute_tool(
        "FileReadTool",
        file_path=str(test_file)
    )
    
    print(f"📄 Reading file: {test_file}")
    print(f"📝 Content:\n{result.data}")
    print(f"✅ Status: {result.status.value}")


# =============================================================================
# 1.4 - Single Agent with FileWriteTool
# =============================================================================

def example_1_4_agent_with_file_write_tool():
    """Write content to file using FileWriteTool."""
    print("\n" + "="*70)
    print("1.4 - AGENT WITH FileWriteTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import FileWriteTool
    
    # Create agent
    agent = Agent(
        name="FileWriter",
        role="File writing specialist",
        capabilities=["file-write"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(FileWriteTool())
    
    # Write to file
    output_file = TEMP_DIR / "output.txt"
    content = "This content was written by FileWriteTool!\nLine 2\nLine 3"
    
    result = agent.execute_tool(
        "FileWriteTool",
        file_path=str(output_file),
        content=content
    )
    
    print(f"✍️  Writing to: {output_file}")
    print(f"📝 Content: {content[:50]}...")
    print(f"✅ Result: {result.data}")
    
    # Verify
    if output_file.exists():
        print(f"✓ File created successfully: {output_file.stat().st_size} bytes")


# =============================================================================
# 1.5 - Single Agent with DirectoryReadTool
# =============================================================================

def example_1_5_agent_with_directory_read_tool():
    """List directory contents using DirectoryReadTool."""
    print("\n" + "="*70)
    print("1.5 - AGENT WITH DirectoryReadTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import DirectoryReadTool
    
    # Create some test files
    for i in range(3):
        (TEMP_DIR / f"file_{i}.txt").write_text(f"Content {i}")
    
    # Create agent
    agent = Agent(
        name="DirectoryReader",
        role="Directory listing specialist",
        capabilities=["directory-read"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(DirectoryReadTool())
    
    # Read directory
    result = agent.execute_tool(
        "DirectoryReadTool",
        directory=str(TEMP_DIR)
    )
    
    print(f"📁 Listing directory: {TEMP_DIR}")
    print(f"📋 Files found ({result.data.get('total_items', 0)} items):")
    
    # result.data is a dict with 'items' key
    items = result.data.get('items', []) if isinstance(result.data, dict) else []
    for item in items:
        name = item.get('name', item) if isinstance(item, dict) else item
        print(f"   • {name}")
    
    print(f"✅ Status: {result.status.value}")


# =============================================================================
# 1.6 - Single Agent with OCRTool
# =============================================================================

def example_1_6_agent_with_ocr_tool():
    """Extract text from images using OCRTool."""
    print("\n" + "="*70)
    print("1.6 - AGENT WITH OCRTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import OCRTool
    
    print("⚠️  OCRTool requires pytesseract or OpenAI Vision API")
    print("⚠️  Tesseract must be installed: brew install tesseract (macOS)")
    print("📝 This example shows the setup")
    
    # Create agent
    agent = Agent(
        name="OCRAgent",
        role="Text extraction from images",
        capabilities=["ocr", "vision"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(OCRTool())
    
    print(f"✅ Agent created with OCRTool")
    print(f"💡 Usage: agent.execute_tool('OCRTool', image_path='test_image.jpeg')")
    
    # Check if tesseract is available before attempting execution
    import shutil
    if shutil.which('tesseract'):
        # Execute OCR if tesseract is installed
        result = agent.execute_tool("OCRTool", image_path=str(TEMP_DIR / "test_txt.jpg"))
        if result.data:
            print(f"📝 Extracted text: {result.data.get('text', result.data)}")
        else:
            print(f"⚠️  OCR execution failed")
    else:
        print(f"⚠️  Skipping execution - tesseract not installed")
        print(f"💡 Install: brew install tesseract && pip install pytesseract")


# =============================================================================
# 1.7 - Single Agent with PDFTextWritingTool
# =============================================================================

def example_1_7_agent_with_pdf_text_writing_tool():
    """Create PDF from text using PDFTextWritingTool."""
    print("\n" + "="*70)
    print("1.7 - AGENT WITH PDFTextWritingTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import PDFTextWritingTool
    
    print("⚠️  PDFTextWritingTool requires reportlab library")
    print("📝 This example shows the setup")
    
    # Create agent
    agent = Agent(
        name="PDFWriter",
        role="PDF document creation",
        capabilities=["pdf-write"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(PDFTextWritingTool())
    
    print(f"✅ Agent created with PDFTextWritingTool")
    print(f"💡 Usage: agent.execute_tool('PDFTextWritingTool',")
    print(f"          output_path='output.pdf', content='Your content here')")
    
    # Example structure (would need reportlab)
    result = agent.execute_tool(
        "PDFTextWritingTool",
        output_path=str(TEMP_DIR / "samplex.pdf"),
        content="This is a PDF document created by an agent!"
    )
    print(f"✅ PDF created at: {result.data}")


# =============================================================================
# 1.8 - Single Agent with PDFRAGSearchTool
# =============================================================================

def example_1_8_agent_with_pdf_rag_search_tool():
    """Search PDF content using PDFRAGSearchTool."""
    print("\n" + "="*70)
    print("1.8 - AGENT WITH PDFRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import PDFRAGSearchTool
    
    print("⚠️  PDFRAGSearchTool requires PyPDF2/pdfplumber and embeddings")
    print("📝 This example shows the setup")
    
    # Create agent
    agent = Agent(
        name="PDFSearcher",
        role="PDF content search and retrieval",
        capabilities=["pdf-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(PDFRAGSearchTool())
    
    print(f"✅ Agent created with PDFRAGSearchTool")
    print(f"💡 Usage: agent.execute_tool('PDFRAGSearchTool',")
    print(f"          query='search term', pdf_paths=['document.pdf'])")


# =============================================================================
# 1.9 - Single Agent with DOCXRAGSearchTool
# =============================================================================

def example_1_9_agent_with_docx_rag_search_tool():
    """Search DOCX content using DOCXRAGSearchTool."""
    print("\n" + "="*70)
    print("1.9 - AGENT WITH DOCXRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import DOCXRAGSearchTool
    
    print("⚠️  DOCXRAGSearchTool requires python-docx library")
    
    # Create agent
    agent = Agent(
        name="DOCXSearcher",
        role="Word document search",
        capabilities=["docx-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(DOCXRAGSearchTool())
    
    print(f"✅ Agent created with DOCXRAGSearchTool")
    print(f"💡 Usage: agent.execute_tool('DOCXRAGSearchTool',")
    print(f"          query='search term', docx_paths=['document.docx'])")


# =============================================================================
# 1.10 - Single Agent with MDXRAGSearchTool
# =============================================================================

def example_1_10_agent_with_mdx_rag_search_tool():
    """Search Markdown content using MDXRAGSearchTool."""
    print("\n" + "="*70)
    print("1.10 - AGENT WITH MDXRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import MDXRAGSearchTool
    
    # Create test markdown file
    md_file = TEMP_DIR / "sample.md"
    md_file.write_text("""# Sample Document

## Introduction
This is a markdown document for testing.

## Features
- Feature 1: Easy to read
- Feature 2: Plain text
- Feature 3: Structured content

## Conclusion
Markdown is great for documentation.
""")
    
    # Create agent
    agent = Agent(
        name="MarkdownSearcher",
        role="Markdown content search",
        capabilities=["markdown-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(MDXRAGSearchTool())
    
    print(f"✅ Agent created with MDXRAGSearchTool")
    print(f"📄 Sample markdown file: {md_file}")
    print(f"💡 Usage: agent.execute_tool('MDXRAGSearchTool',")
    print(f"          query='features', md_paths=['{md_file}'])")


# =============================================================================
# 1.11 - Single Agent with XMLRAGSearchTool
# =============================================================================

def example_1_11_agent_with_xml_rag_search_tool():
    """Search XML content using XMLRAGSearchTool."""
    print("\n" + "="*70)
    print("1.11 - AGENT WITH XMLRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import XMLRAGSearchTool
    
    # Create test XML file
    xml_file = TEMP_DIR / "sample.xml"
    xml_file.write_text("""<?xml version="1.0"?>
<catalog>
    <book id="1">
        <title>Python Programming</title>
        <author>John Doe</author>
        <year>2024</year>
    </book>
    <book id="2">
        <title>AI Fundamentals</title>
        <author>Jane Smith</author>
        <year>2023</year>
    </book>
</catalog>
""")
    
    # Create agent
    agent = Agent(
        name="XMLSearcher",
        role="XML content search",
        capabilities=["xml-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(XMLRAGSearchTool())
    
    print(f"✅ Agent created with XMLRAGSearchTool")
    print(f"📄 Sample XML file: {xml_file}")
    print(f"💡 Usage: agent.execute_tool('XMLRAGSearchTool',")
    print(f"          query='Python', xml_paths=['{xml_file}'])")


# =============================================================================
# 1.12 - Single Agent with TXTRAGSearchTool
# =============================================================================

def example_1_12_agent_with_txt_rag_search_tool():
    """Search text file content using TXTRAGSearchTool."""
    print("\n" + "="*70)
    print("1.12 - AGENT WITH TXTRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import TXTRAGSearchTool
    
    # Create test text file
    txt_file = TEMP_DIR / "knowledge.txt"
    txt_file.write_text("""Machine Learning Concepts

Supervised Learning:
- Classification: Predict discrete labels
- Regression: Predict continuous values

Unsupervised Learning:
- Clustering: Group similar data points
- Dimensionality Reduction: Reduce feature space

Deep Learning:
- Neural Networks: Layers of interconnected neurons
- Convolutional Neural Networks: For image processing
- Recurrent Neural Networks: For sequential data
""")
    
    # Create agent
    agent = Agent(
        name="TextSearcher",
        role="Text file search and retrieval",
        capabilities=["text-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(TXTRAGSearchTool())
    
    print(f"✅ Agent created with TXTRAGSearchTool")
    print(f"📄 Sample text file: {txt_file}")
    print(f"💡 Usage: agent.execute_tool('TXTRAGSearchTool',")
    print(f"          query='neural networks', txt_paths=['{txt_file}'])")


# =============================================================================
# 1.13 - Single Agent with JSONRAGSearchTool
# =============================================================================

def example_1_13_agent_with_json_rag_search_tool():
    """Search JSON content using JSONRAGSearchTool."""
    print("\n" + "="*70)
    print("1.13 - AGENT WITH JSONRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import JSONRAGSearchTool
    
    # Create test JSON file
    json_file = TEMP_DIR / "data.json"
    data = {
        "users": [
            {"id": 1, "name": "Alice", "role": "Engineer", "skills": ["Python", "AI"]},
            {"id": 2, "name": "Bob", "role": "Designer", "skills": ["UI", "UX"]},
            {"id": 3, "name": "Charlie", "role": "Manager", "skills": ["Leadership", "Strategy"]}
        ],
        "projects": [
            {"name": "Project A", "status": "active", "team": [1, 2]},
            {"name": "Project B", "status": "completed", "team": [2, 3]}
        ]
    }
    json_file.write_text(json.dumps(data, indent=2))
    
    # Create agent
    agent = Agent(
        name="JSONSearcher",
        role="JSON data search",
        capabilities=["json-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(JSONRAGSearchTool())
    
    print(f"✅ Agent created with JSONRAGSearchTool")
    print(f"📄 Sample JSON file: {json_file}")
    print(f"💡 Usage: agent.execute_tool('JSONRAGSearchTool',")
    print(f"          query='Engineer', json_paths=['{json_file}'])")


# =============================================================================
# 1.14 - Single Agent with CSVRAGSearchTool
# =============================================================================

def example_1_14_agent_with_csv_rag_search_tool():
    """Search CSV content using CSVRAGSearchTool."""
    print("\n" + "="*70)
    print("1.14 - AGENT WITH CSVRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import CSVRAGSearchTool
    
    # Create test CSV file
    csv_file = TEMP_DIR / "sales.csv"
    csv_file.write_text("""product,category,price,quantity,revenue
Laptop,Electronics,999.99,50,49999.50
Mouse,Electronics,29.99,200,5998.00
Keyboard,Electronics,79.99,150,11998.50
Desk,Furniture,299.99,30,8999.70
Chair,Furniture,199.99,45,8999.55
""")
    
    # Create agent
    agent = Agent(
        name="CSVSearcher",
        role="CSV data search and analysis",
        capabilities=["csv-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(CSVRAGSearchTool())
    
    print(f"✅ Agent created with CSVRAGSearchTool")
    print(f"📄 Sample CSV file: {csv_file}")
    print(f"💡 Usage: agent.execute_tool('CSVRAGSearchTool',")
    print(f"          query='Electronics', csv_paths=['{csv_file}'])")


# =============================================================================
# 1.15 - Single Agent with DirectoryRAGSearchTool
# =============================================================================

def example_1_15_agent_with_directory_rag_search_tool():
    """Search across directory files using DirectoryRAGSearchTool."""
    print("\n" + "="*70)
    print("1.15 - AGENT WITH DirectoryRAGSearchTool")
    print("="*70)
    
    from agenticaiframework import Agent
    from agenticaiframework.tools import DirectoryRAGSearchTool
    
    # Create multiple test files
    docs_dir = TEMP_DIR / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    (docs_dir / "api.txt").write_text("API Documentation: REST endpoints for user management")
    (docs_dir / "guide.txt").write_text("User Guide: How to use the application features")
    (docs_dir / "faq.txt").write_text("FAQ: Common questions about authentication and security")
    
    # Create agent
    agent = Agent(
        name="DirectorySearcher",
        role="Multi-file search across directories",
        capabilities=["directory-search", "rag"],
        config={}
    )
    agent.start()
    
    # Add tool (registers and binds automatically)
    agent.add_tool(DirectoryRAGSearchTool())
    
    print(f"✅ Agent created with DirectoryRAGSearchTool")
    print(f"📁 Sample directory: {docs_dir}")
    print(f"📄 Files: api.txt, guide.txt, faq.txt")
    print(f"💡 Usage: agent.execute_tool('DirectoryRAGSearchTool',")
    print(f"          query='authentication', directory='{docs_dir}')")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("SINGLE AGENT EXAMPLES - COMPREHENSIVE GUIDE")
    print("="*70)
    print(f"📁 Temporary directory: {TEMP_DIR}")
    
    examples = [
        # example_1_1_agent_without_llm,
        # example_1_2_agent_with_llm,
        # example_1_3_agent_with_file_read_tool,
        # example_1_4_agent_with_file_write_tool,
        # example_1_5_agent_with_directory_read_tool,
        example_1_6_agent_with_ocr_tool,
        # example_1_7_agent_with_pdf_text_writing_tool,
        # example_1_8_agent_with_pdf_rag_search_tool,
        # example_1_9_agent_with_docx_rag_search_tool,
        # example_1_10_agent_with_mdx_rag_search_tool,
        # example_1_11_agent_with_xml_rag_search_tool,
        # example_1_12_agent_with_txt_rag_search_tool,
        # example_1_13_agent_with_json_rag_search_tool,
        # example_1_14_agent_with_csv_rag_search_tool,
        # example_1_15_agent_with_directory_rag_search_tool,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"❌ Error in {example.__name__}: {e}")
    
    print("\n" + "="*70)
    print("✅ ALL EXAMPLES COMPLETED")
    print("="*70)
    print(f"📁 Generated files in: {TEMP_DIR}")
    print(f"🧹 To cleanup: rm -rf {TEMP_DIR}")


if __name__ == "__main__":
    main()
