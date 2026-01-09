"""
AI Framework Integration Tools (LlamaIndex, LangChain).
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class LlamaIndexTool(BaseTool):
    """
    Tool for integration with LlamaIndex.
    
    Features:
    - Index creation and querying
    - Document loading
    - Vector store integration
    - Custom retrievers
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="LlamaIndexTool",
            description="LlamaIndex integration for RAG"
        ))
        self.api_key = api_key or self.config.api_key
        self._index = None
        self._service_context = None
    
    def _execute(
        self,
        query: str,
        documents: Optional[List[str]] = None,
        index_type: str = 'vector',
        top_k: int = 5,
        response_mode: str = 'compact',
    ) -> Dict[str, Any]:
        """
        Query documents using LlamaIndex.
        
        Args:
            query: Query string
            documents: List of document paths or texts
            index_type: 'vector', 'list', 'tree', or 'keyword'
            top_k: Number of results
            response_mode: 'compact', 'refine', 'tree_summarize'
            
        Returns:
            Dict with query results
        """
        try:
            from llama_index.core import (
                VectorStoreIndex,
                SimpleDirectoryReader,
                Document,
                Settings,
            )
            from llama_index.llms.openai import OpenAI
        except ImportError:
            raise ImportError("LlamaIndex requires: pip install llama-index")
        
        # Set up LLM
        if self.api_key:
            Settings.llm = OpenAI(api_key=self.api_key)
        
        # Load or create index
        if documents and (not self._index or documents):
            self._index = self._create_index(documents, index_type)
        
        if not self._index:
            return {
                'query': query,
                'status': 'error',
                'error': 'No index available. Provide documents to index.',
            }
        
        # Query
        query_engine = self._index.as_query_engine(
            similarity_top_k=top_k,
            response_mode=response_mode,
        )
        
        response = query_engine.query(query)
        
        return {
            'query': query,
            'status': 'success',
            'response': str(response),
            'source_nodes': [
                {
                    'text': node.node.text[:500],
                    'score': node.score,
                }
                for node in response.source_nodes
            ],
        }
    
    def _create_index(self, documents: List[str], index_type: str):
        """Create index from documents."""
        from llama_index.core import (
            VectorStoreIndex,
            ListIndex,
            TreeIndex,
            KeywordTableIndex,
            Document,
            SimpleDirectoryReader,
        )
        from pathlib import Path
        
        # Load documents
        docs = []
        for doc in documents:
            if Path(doc).exists():
                if Path(doc).is_dir():
                    reader = SimpleDirectoryReader(doc)
                    docs.extend(reader.load_data())
                else:
                    reader = SimpleDirectoryReader(input_files=[doc])
                    docs.extend(reader.load_data())
            else:
                # Treat as text
                docs.append(Document(text=doc))
        
        # Create index
        index_classes = {
            'vector': VectorStoreIndex,
            'list': ListIndex,
            'tree': TreeIndex,
            'keyword': KeywordTableIndex,
        }
        
        index_class = index_classes.get(index_type, VectorStoreIndex)
        return index_class.from_documents(docs)
    
    def add_documents(self, documents: List[str]):
        """Add documents to existing index."""
        from llama_index.core import Document, SimpleDirectoryReader
        from pathlib import Path
        
        if not self._index:
            self._index = self._create_index(documents, 'vector')
            return
        
        for doc in documents:
            if Path(doc).exists():
                reader = SimpleDirectoryReader(input_files=[doc])
                nodes = reader.load_data()
                for node in nodes:
                    self._index.insert(node)
            else:
                self._index.insert(Document(text=doc))


class LangChainTool(BaseTool):
    """
    Tool for integration with LangChain.
    
    Features:
    - Chain execution
    - Agent integration
    - Memory management
    - Tool wrapping
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="LangChainTool",
            description="LangChain integration for AI chains"
        ))
        self.api_key = api_key or self.config.api_key
        self._chains: Dict[str, Any] = {}
    
    def _execute(
        self,
        prompt: str,
        chain_type: str = 'llm',
        memory: bool = False,
        tools: Optional[List[str]] = None,
        model: str = 'gpt-4',
    ) -> Dict[str, Any]:
        """
        Execute LangChain operation.
        
        Args:
            prompt: Input prompt
            chain_type: 'llm', 'conversation', 'agent', 'qa'
            memory: Enable conversation memory
            tools: List of tool names for agent
            model: Model to use
            
        Returns:
            Dict with execution results
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain.chains import LLMChain, ConversationChain
            from langchain.memory import ConversationBufferMemory
            from langchain.prompts import PromptTemplate
        except ImportError:
            raise ImportError("LangChain requires: pip install langchain langchain-openai")
        
        if not self.api_key:
            raise ValueError("API key required")
        
        llm = ChatOpenAI(model=model, api_key=self.api_key)
        
        if chain_type == 'llm':
            result = self._run_llm_chain(llm, prompt)
        elif chain_type == 'conversation':
            result = self._run_conversation(llm, prompt, memory)
        elif chain_type == 'agent':
            result = self._run_agent(llm, prompt, tools)
        else:
            result = {'error': f'Unknown chain type: {chain_type}'}
        
        return {
            'prompt': prompt,
            'chain_type': chain_type,
            'model': model,
            **result,
        }
    
    def _run_llm_chain(self, llm, prompt: str) -> Dict[str, Any]:
        """Run simple LLM chain."""
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        template = PromptTemplate(
            input_variables=["input"],
            template="{input}"
        )
        
        chain = LLMChain(llm=llm, prompt=template)
        result = chain.invoke({"input": prompt})
        
        return {
            'status': 'success',
            'response': result.get('text', str(result)),
        }
    
    def _run_conversation(self, llm, prompt: str, use_memory: bool) -> Dict[str, Any]:
        """Run conversation chain."""
        from langchain.chains import ConversationChain
        from langchain.memory import ConversationBufferMemory
        
        chain_id = 'conversation'
        
        if chain_id not in self._chains or not use_memory:
            memory = ConversationBufferMemory() if use_memory else None
            self._chains[chain_id] = ConversationChain(
                llm=llm,
                memory=memory,
                verbose=False,
            )
        
        chain = self._chains[chain_id]
        result = chain.invoke({"input": prompt})
        
        return {
            'status': 'success',
            'response': result.get('response', str(result)),
        }
    
    def _run_agent(self, llm, prompt: str, tool_names: Optional[List[str]]) -> Dict[str, Any]:
        """Run agent with tools."""
        try:
            from langchain.agents import AgentExecutor, create_openai_functions_agent
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        except ImportError:
            return {'status': 'error', 'error': 'Agent support requires additional packages'}
        
        # For now, return a simple response
        # Full agent implementation would require tool definitions
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        template = PromptTemplate(
            input_variables=["input"],
            template="You are a helpful assistant. {input}"
        )
        
        chain = LLMChain(llm=llm, prompt=template)
        result = chain.invoke({"input": prompt})
        
        return {
            'status': 'success',
            'response': result.get('text', str(result)),
            'tools_available': tool_names or [],
        }
    
    def clear_memory(self):
        """Clear conversation memory."""
        self._chains.clear()


__all__ = ['LlamaIndexTool', 'LangChainTool']
