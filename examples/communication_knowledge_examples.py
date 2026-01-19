"""
Agent Communication and Knowledge Building Examples.

Demonstrates:
1. Multi-protocol agent-to-agent communication (STDIO, HTTP, SSE, MQTT)
2. Remote agent server/client patterns
3. Knowledge building from web, APIs, documents, images
4. Embedding generation and vector database storage
5. Semantic search over knowledge base
"""

import os
import asyncio
from typing import Dict, Any

# ============================================================================
# Example 1: Basic HTTP Agent Communication
# ============================================================================

def example_http_communication():
    """Demonstrate HTTP-based agent-to-agent communication."""
    from agenticaiframework import Agent
    from agenticaiframework.communication import (
        RemoteAgentClient,
        RemoteAgentServer,
        AgentEndpoint,
        ProtocolType,
    )
    
    print("=" * 60)
    print("Example 1: HTTP Agent Communication")
    print("=" * 60)
    
    # Create a local agent
    analyzer = Agent.quick("Analyzer", role="analyst")
    
    # Expose it as an HTTP server
    # In production, you would run this in a separate process
    server = RemoteAgentServer(analyzer, agent_id="analyzer")
    flask_app = server.create_flask_app()
    
    print("Created Flask app for Analyzer agent")
    print("Would run: flask_app.run(host='0.0.0.0', port=8080)")
    
    # Create a client to call remote agents
    client = RemoteAgentClient(agent_id="orchestrator")
    
    # Register the remote analyzer
    client.register_endpoint(AgentEndpoint(
        agent_id="analyzer",
        protocol=ProtocolType.HTTP,
        host="localhost",
        port=8080,
        path="/agent",
    ))
    
    print("Registered analyzer endpoint")
    print("Would call: client.call('analyzer', 'Analyze this data')")
    
    # Simulated response
    print("\nResponse: {'analysis': 'Data shows positive trend'}")


# ============================================================================
# Example 2: SSE Streaming Communication
# ============================================================================

def example_sse_streaming():
    """Demonstrate Server-Sent Events for streaming responses."""
    from agenticaiframework.communication import (
        SSEProtocol,
        AgentEndpoint,
        ProtocolType,
        RemoteAgentClient,
    )
    
    print("\n" + "=" * 60)
    print("Example 2: SSE Streaming Communication")
    print("=" * 60)
    
    # Create SSE client for streaming
    client = RemoteAgentClient(agent_id="streamer")
    
    # Register SSE endpoint
    client.register_endpoint(AgentEndpoint(
        agent_id="writer",
        protocol=ProtocolType.SSE,
        host="writer.example.com",
        port=443,
        path="/stream",
    ))
    
    print("Registered SSE streaming endpoint")
    print("\nStreaming example (simulated):")
    print(">>> for chunk in client.call_stream('writer', 'Write a poem'):")
    print("...     print(chunk, end='')")
    print("\nOnce upon a midnight dreary...")


# ============================================================================
# Example 3: MQTT Pub/Sub Communication
# ============================================================================

def example_mqtt_communication():
    """Demonstrate MQTT-based pub/sub agent communication."""
    from agenticaiframework.communication import (
        MQTTProtocol,
        AgentEndpoint,
        ProtocolType,
        RemoteAgentClient,
    )
    
    print("\n" + "=" * 60)
    print("Example 3: MQTT Pub/Sub Communication")
    print("=" * 60)
    
    # Create MQTT client
    client = RemoteAgentClient(agent_id="controller")
    
    # Register MQTT endpoints for IoT agents
    client.register_endpoint(AgentEndpoint(
        agent_id="sensor-agent",
        protocol=ProtocolType.MQTT,
        host="mqtt.example.com",
        port=1883,
        mqtt_topic="agents/sensors/temperature",
    ))
    
    print("Registered MQTT agent for sensor data")
    print("\nMQTT Topics:")
    print("  - agents/sensors/temperature (subscribe)")
    print("  - agents/sensors/commands (publish)")
    
    print("\nExample usage:")
    print(">>> response = client.call('sensor-agent', {'command': 'read'})")
    print(">>> # Returns: {'temperature': 22.5, 'unit': 'celsius'}")


# ============================================================================
# Example 4: STDIO Protocol (MCP-style)
# ============================================================================

def example_stdio_communication():
    """Demonstrate STDIO-based subprocess communication."""
    from agenticaiframework.communication import (
        STDIOProtocol,
        AgentEndpoint,
        ProtocolType,
    )
    
    print("\n" + "=" * 60)
    print("Example 4: STDIO Protocol (MCP-style)")
    print("=" * 60)
    
    # STDIO is used for local subprocess communication
    # Similar to MCP (Model Context Protocol) tool servers
    
    print("STDIO protocol for subprocess communication:")
    print("""
    # Start a subprocess agent
    protocol = STDIOProtocol(command=["python", "agent_server.py"])
    protocol.connect()
    
    # Send JSON messages via stdin, receive via stdout
    response = protocol.send({
        "type": "query",
        "content": "Analyze this code"
    })
    
    # Response comes as JSON via stdout
    print(response)  # {"type": "response", "content": "..."}
    """)


# ============================================================================
# Example 5: Agent with Built-in Communication
# ============================================================================

def example_agent_communication_methods():
    """Demonstrate Agent's built-in communication methods."""
    from agenticaiframework import Agent
    
    print("\n" + "=" * 60)
    print("Example 5: Agent Built-in Communication")
    print("=" * 60)
    
    # Create orchestrator agent
    orchestrator = Agent.quick("Orchestrator", role="assistant")
    
    # Connect to remote agents
    orchestrator.connect_remote(
        "analyzer",
        url="https://analyzer.example.com/agent"
    )
    
    orchestrator.connect_remote(
        "summarizer",
        protocol="sse",
        host="summarizer.example.com",
        port=443,
    )
    
    orchestrator.connect_remote(
        "iot-controller",
        protocol="mqtt",
        host="mqtt.example.com",
    )
    
    print("Connected to 3 remote agents:")
    print("  - analyzer (HTTPS)")
    print("  - summarizer (SSE)")
    print("  - iot-controller (MQTT)")
    
    print("\nUsage examples:")
    print("""
    # Send to specific agent
    response = orchestrator.send_to_agent("analyzer", "Analyze data")
    
    # Stream from agent
    for chunk in orchestrator.stream_from_agent("summarizer", "Summarize"):
        print(chunk)
    
    # Broadcast to all
    responses = orchestrator.broadcast_to_agents("System check")
    """)


# ============================================================================
# Example 6: Expose Agent as Server
# ============================================================================

def example_agent_as_server():
    """Demonstrate exposing an agent as a remote service."""
    from agenticaiframework import Agent
    
    print("\n" + "=" * 60)
    print("Example 6: Agent as Remote Server")
    print("=" * 60)
    
    # Create agent
    agent = Agent.quick("MyAgent", role="assistant")
    
    print("Flask server:")
    print("""
    app = agent.as_server("flask")
    app.run(host="0.0.0.0", port=8080)
    
    # Endpoints:
    # GET  /health      - Health check
    # POST /agent       - Query agent
    # POST /agent/stream - Stream response (SSE)
    """)
    
    print("FastAPI server:")
    print("""
    import uvicorn
    
    app = agent.as_server("fastapi")
    uvicorn.run(app, host="0.0.0.0", port=8080)
    """)


# ============================================================================
# Example 7: Knowledge Builder - Multiple Sources
# ============================================================================

def example_knowledge_builder():
    """Demonstrate knowledge building from various sources."""
    from agenticaiframework.knowledge import KnowledgeBuilder
    
    print("\n" + "=" * 60)
    print("Example 7: Knowledge Builder")
    print("=" * 60)
    
    # Create knowledge builder with OpenAI embeddings
    builder = KnowledgeBuilder(
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
    )
    
    print("Knowledge Builder initialized with OpenAI embeddings")
    print("\nSupported sources:")
    
    # Document sources
    print("\n📄 Documents:")
    print("  builder.add_from_file('docs/manual.pdf')")
    print("  builder.add_from_file('data/report.docx')")
    print("  builder.add_from_file('notes.md')")
    print("  builder.add_from_directory('docs/', extensions=['.pdf', '.md'])")
    
    # Web sources
    print("\n🌐 Web:")
    print("  builder.add_from_url('https://example.com/article')")
    print("  builder.add_from_web_search('machine learning best practices')")
    
    # API sources
    print("\n🔌 APIs:")
    print("  builder.add_from_api('https://api.example.com/data')")
    print("  builder.add_from_api(")
    print("      'https://api.example.com/items',")
    print("      headers={'Authorization': 'Bearer token'},")
    print("      json_path='data.items'")
    print("  )")
    
    # Image sources
    print("\n🖼️ Images (OCR/Vision):")
    print("  # Using Tesseract OCR")
    print("  builder.add_from_image('diagram.png', ocr_provider='pytesseract')")
    print("  # Using GPT-4 Vision")
    print("  builder.add_from_image('chart.png', ocr_provider='openai_vision')")
    
    # Data files
    print("\n📊 Data Files:")
    print("  builder.add('data.json')")
    print("  builder.add('spreadsheet.csv')")


# ============================================================================
# Example 8: Embedding Output for Vector Databases
# ============================================================================

def example_embedding_output():
    """Demonstrate embedding generation and vector DB formats."""
    from agenticaiframework.knowledge import EmbeddingOutput
    
    print("\n" + "=" * 60)
    print("Example 8: Embedding Output for Vector Databases")
    print("=" * 60)
    
    # Create sample embedding output
    embedding = EmbeddingOutput(
        id="doc-001",
        embedding=[0.1, 0.2, 0.3],  # Truncated for example
        content="This is a sample document text.",
        metadata={"source": "docs/sample.pdf", "page": 1}
    )
    
    print("EmbeddingOutput provides converters for all major vector DBs:\n")
    
    print("🔷 Qdrant:")
    print("  point = embedding.to_qdrant_point()")
    print("  qdrant_client.upsert(collection='docs', points=[point])")
    
    print("\n🌲 Pinecone:")
    print("  vector = embedding.to_pinecone_vector()")
    print("  index.upsert(vectors=[vector])")
    
    print("\n🌐 Weaviate:")
    print("  obj = embedding.to_weaviate_object(class_name='Document')")
    print("  client.data_object.create(obj)")
    
    print("\n🎨 ChromaDB:")
    print("  doc = embedding.to_chroma_document()")
    print("  collection.add(**doc)")
    
    print("\n🦅 Milvus:")
    print("  entity = embedding.to_milvus_entity()")
    print("  collection.insert([entity])")
    
    print("\n🍃 MongoDB Atlas:")
    print("  doc = embedding.to_mongodb_document()")
    print("  collection.insert_one(doc)")
    
    print("\n🐘 PostgreSQL (pgvector):")
    print("  row = embedding.to_pgvector_row()")
    print("  cursor.execute('INSERT INTO docs ...', row)")
    
    print("\n🔍 OpenSearch:")
    print("  doc = embedding.to_opensearch_document()")
    print("  client.index(body=doc['_source'], id=doc['_id'])")


# ============================================================================
# Example 9: Unified Vector DB Tool
# ============================================================================

def example_vector_db_tool():
    """Demonstrate unified vector database tool."""
    from agenticaiframework.knowledge import UnifiedVectorDBTool, create_vector_db_tool
    
    print("\n" + "=" * 60)
    print("Example 9: Unified Vector DB Tool")
    print("=" * 60)
    
    # Create tool for different databases
    print("Creating vector DB tools for different providers:\n")
    
    print("# In-memory (for testing)")
    print("db = UnifiedVectorDBTool(db_type='memory', collection_name='test')")
    
    print("\n# Qdrant")
    print("db = UnifiedVectorDBTool(")
    print("    db_type='qdrant',")
    print("    host='localhost',")
    print("    port=6333,")
    print("    collection_name='knowledge'")
    print(")")
    
    print("\n# Pinecone")
    print("db = UnifiedVectorDBTool(")
    print("    db_type='pinecone',")
    print("    api_key=os.getenv('PINECONE_API_KEY'),")
    print("    index_name='my-index'")
    print(")")
    
    print("\n# ChromaDB")
    print("db = UnifiedVectorDBTool(")
    print("    db_type='chroma',")
    print("    collection_name='documents'")
    print(")")
    
    # Demo operations
    print("\n📥 Insert:")
    print("db.insert(vectors=[[0.1, 0.2, ...]], payloads=[{'text': 'doc'}])")
    
    print("\n🔍 Search:")
    print("results = db.search(query_vector=[0.1, 0.2, ...], limit=10)")
    
    print("\n🗑️ Delete:")
    print("db.delete(ids=['doc-001', 'doc-002'])")


# ============================================================================
# Example 10: Agent Knowledge Building Pipeline
# ============================================================================

def example_agent_knowledge_pipeline():
    """Demonstrate complete agent knowledge building pipeline."""
    from agenticaiframework import Agent
    
    print("\n" + "=" * 60)
    print("Example 10: Agent Knowledge Building Pipeline")
    print("=" * 60)
    
    print("""
    # Create agent with knowledge building capabilities
    agent = Agent.quick("ResearchBot", role="researcher")
    
    # Build knowledge from multiple sources
    agent.create_knowledge_from([
        "docs/research_papers/",          # Directory of PDFs
        "https://example.com/article",    # Web page
        "search:AI best practices 2024",  # Web search
    ])
    
    # Add from specific sources
    agent.add_knowledge_from_web_search("machine learning trends", num_results=10)
    agent.add_knowledge_from_api("https://api.news.com/tech", json_path="articles")
    agent.add_knowledge_from_image("charts/revenue.png", ocr_provider="openai_vision")
    
    # Get embeddings for external storage
    embeddings = agent.get_knowledge_embeddings()
    
    # Or store directly in vector database
    agent.store_knowledge_in_vector_db(
        db_type="qdrant",
        host="localhost",
        collection_name="research_kb"
    )
    
    # Search knowledge
    results = agent.search_knowledge("What are the latest ML trends?")
    for r in results:
        print(f"Score: {r['score']:.3f} - {r['payload']['content'][:100]}...")
    """)


# ============================================================================
# Example 11: Multi-Agent Communication Hub
# ============================================================================

def example_multi_agent_hub():
    """Demonstrate a multi-agent communication hub."""
    from agenticaiframework.communication import AgentCommunicationManager
    
    print("\n" + "=" * 60)
    print("Example 11: Multi-Agent Communication Hub")
    print("=" * 60)
    
    print("""
    from agenticaiframework.communication import AgentCommunicationManager
    from agenticaiframework import Agent
    
    # Create communication manager
    manager = AgentCommunicationManager(agent_id="hub")
    
    # Register local agents
    analyzer = Agent.quick("Analyzer", role="analyst")
    writer = Agent.quick("Writer", role="writer")
    manager.register_agent("analyzer", agent_instance=analyzer)
    manager.register_agent("writer", agent_instance=writer)
    
    # Register remote agents
    manager.register_agent("coder", url="https://coder.example.com/agent")
    manager.register_agent("sensor", protocol="mqtt", host="mqtt.example.com")
    
    # Send to any agent (local or remote)
    response = manager.send("analyzer", "Analyze this data")
    response = manager.send("coder", "Review this code")
    
    # Stream from agents
    for chunk in manager.stream("writer", "Write a story"):
        print(chunk, end="")
    
    # Broadcast to all
    responses = manager.broadcast("System status check")
    
    # Get statistics
    stats = manager.get_stats()
    print(f"Messages sent: {stats['messages_sent']}")
    print(f"Local agents: {stats['local_agents']}")
    print(f"Remote agents: {stats['remote_agents']}")
    """)


# ============================================================================
# Example 12: Complete Integration Example
# ============================================================================

def example_complete_integration():
    """Demonstrate complete integration of all features."""
    from agenticaiframework import Agent
    
    print("\n" + "=" * 60)
    print("Example 12: Complete Integration Example")
    print("=" * 60)
    
    print("""
    from agenticaiframework import Agent
    
    # Create an intelligent research agent
    agent = (
        Agent.quick("ResearchAssistant", role="researcher")
        
        # Build knowledge base
        .create_knowledge_from([
            "docs/company_data.pdf",
            "https://industry.news/latest",
            "search:market analysis 2024",
        ])
        .add_knowledge_from_api(
            "https://api.stocks.com/data",
            headers={"API-Key": os.getenv("STOCKS_API_KEY")}
        )
        .store_knowledge_in_vector_db(db_type="qdrant")
        
        # Connect to specialist agents
        .connect_remote("analyst", url="https://analyst.example.com/agent")
        .connect_remote("writer", url="https://writer.example.com/agent")
    )
    
    # Use the agent
    def research_task(topic: str):
        # Search internal knowledge
        knowledge = agent.search_knowledge(topic)
        
        # Get analysis from specialist
        analysis = agent.send_to_agent("analyst", {
            "topic": topic,
            "context": knowledge[:3]
        })
        
        # Generate report with writer agent
        report = ""
        for chunk in agent.stream_from_agent("writer", {
            "task": "Generate research report",
            "analysis": analysis,
            "topic": topic
        }):
            report += chunk.get("content", "")
            print(chunk.get("content", ""), end="")
        
        return report
    
    # Run research
    report = research_task("AI industry trends Q4 2024")
    """)


# ============================================================================
# Run Examples
# ============================================================================

def main():
    """Run all examples."""
    print("=" * 60)
    print("AGENT COMMUNICATION & KNOWLEDGE BUILDING EXAMPLES")
    print("=" * 60)
    
    examples = [
        example_http_communication,
        example_sse_streaming,
        example_mqtt_communication,
        example_stdio_communication,
        example_agent_communication_methods,
        example_agent_as_server,
        example_knowledge_builder,
        example_embedding_output,
        example_vector_db_tool,
        example_agent_knowledge_pipeline,
        example_multi_agent_hub,
        example_complete_integration,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\nNote: {e}")
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
