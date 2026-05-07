"""
Enterprise Adapters - Unified interfaces for cloud services and providers.

Adapters provide a consistent interface across different cloud providers
and services, enabling portable applications.

Usage:
    >>> from agenticaiframework.enterprise import AzureAdapter
    >>> 
    >>> adapter = AzureAdapter()
    >>> await adapter.storage.upload("file.txt", content)
    >>> response = await adapter.llm.generate("Hello")
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Base Adapter Interfaces
# =============================================================================

class StorageAdapter(ABC):
    """Abstract interface for storage operations."""
    
    @abstractmethod
    async def upload(self, path: str, content: Union[str, bytes], **kwargs) -> str:
        """Upload content to storage."""
        pass
    
    @abstractmethod
    async def download(self, path: str, **kwargs) -> Union[str, bytes]:
        """Download content from storage."""
        pass
    
    @abstractmethod
    async def delete(self, path: str, **kwargs) -> bool:
        """Delete content from storage."""
        pass
    
    @abstractmethod
    async def list(self, prefix: str = "", **kwargs) -> List[str]:
        """List files in storage."""
        pass
    
    @abstractmethod
    async def exists(self, path: str, **kwargs) -> bool:
        """Check if file exists."""
        pass


class LLMAdapter(ABC):
    """Abstract interface for LLM operations."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate text completion."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Chat completion."""
        pass
    
    @abstractmethod
    async def embed(
        self,
        text: Union[str, List[str]],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        """Generate embeddings."""
        pass


class VectorDBAdapter(ABC):
    """Abstract interface for vector database operations."""
    
    @abstractmethod
    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict] = None,
        **kwargs,
    ) -> bool:
        """Insert or update a vector."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        *,
        top_k: int = 10,
        filter: Optional[Dict] = None,
        **kwargs,
    ) -> List[Dict]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(self, id: str, **kwargs) -> bool:
        """Delete a vector."""
        pass


class QueueAdapter(ABC):
    """Abstract interface for message queue operations."""
    
    @abstractmethod
    async def send(self, message: Any, **kwargs) -> str:
        """Send a message to the queue."""
        pass
    
    @abstractmethod
    async def receive(self, max_messages: int = 1, **kwargs) -> List[Any]:
        """Receive messages from the queue."""
        pass
    
    @abstractmethod
    async def acknowledge(self, message_id: str, **kwargs) -> bool:
        """Acknowledge message processing."""
        pass


class CacheAdapter(ABC):
    """Abstract interface for cache operations."""
    
    @abstractmethod
    async def get(self, key: str, **kwargs) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        **kwargs,
    ) -> bool:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str, **kwargs) -> bool:
        """Delete value from cache."""
        pass


# =============================================================================
# Azure Implementations
# =============================================================================

class AzureBlobStorage(StorageAdapter):
    """Azure Blob Storage implementation."""
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "default",
    ):
        self.connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = container_name
        self._client = None
        self._rest_client = None
        self._using_rest = False
    
    def _get_client(self):
        if self._client is None:
            try:
                from azure.storage.blob import BlobServiceClient
                self._client = BlobServiceClient.from_connection_string(self.connection_string)
                self._using_rest = False
            except ImportError:
                from .._internal.clients.azure_blob_rest import (
                    BlobServiceClient as RestClient,
                )
                if not self.connection_string:
                    raise RuntimeError(
                        "Azure Blob requires AZURE_STORAGE_CONNECTION_STRING when azure-storage-blob is unavailable"
                    )
                self._client = RestClient.from_connection_string(self.connection_string)
                self._using_rest = True
        return self._client
    
    async def upload(self, path: str, content: Union[str, bytes], **kwargs) -> str:
        client = self._get_client()
        data = content.encode() if isinstance(content, str) else content
        if self._using_rest:
            await asyncio.to_thread(client.create_container, self.container_name)
            url = await asyncio.to_thread(client.upload, self.container_name, path, data)
            return url
        container = client.get_container_client(self.container_name)
        try:
            await asyncio.to_thread(container.create_container)
        except Exception:
            pass  # Container may already exist
        blob = container.get_blob_client(path)
        await asyncio.to_thread(blob.upload_blob, data, overwrite=True)
        return blob.url
    
    async def download(self, path: str, **kwargs) -> Union[str, bytes]:
        client = self._get_client()
        if self._using_rest:
            content = await asyncio.to_thread(client.download, self.container_name, path)
        else:
            container = client.get_container_client(self.container_name)
            blob = container.get_blob_client(path)
            downloader = await asyncio.to_thread(blob.download_blob)
            content = await asyncio.to_thread(downloader.readall)
        try:
            return content.decode()
        except UnicodeDecodeError:
            return content
    
    async def delete(self, path: str, **kwargs) -> bool:
        client = self._get_client()
        try:
            if self._using_rest:
                await asyncio.to_thread(client.delete, self.container_name, path)
            else:
                container = client.get_container_client(self.container_name)
                blob = container.get_blob_client(path)
                await asyncio.to_thread(blob.delete_blob)
            return True
        except Exception:
            return False
    
    async def list(self, prefix: str = "", **kwargs) -> List[str]:
        client = self._get_client()
        if self._using_rest:
            return await asyncio.to_thread(client.list_blobs, self.container_name, prefix)
        container = client.get_container_client(self.container_name)
        blobs = await asyncio.to_thread(
            lambda: list(container.list_blobs(name_starts_with=prefix))
        )
        return [blob.name for blob in blobs]
    
    async def exists(self, path: str, **kwargs) -> bool:
        client = self._get_client()
        if self._using_rest:
            return await asyncio.to_thread(client.exists, self.container_name, path)
        container = client.get_container_client(self.container_name)
        blob = container.get_blob_client(path)
        return await asyncio.to_thread(blob.exists)


class AzureOpenAILLM(LLMAdapter):
    """Azure OpenAI implementation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_version: str = "2024-02-01",
        default_model: str = "gpt-4o",
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version
        self.default_model = default_model
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                from openai import AzureOpenAI  # type: ignore
                self._client = AzureOpenAI(
                    api_key=self.api_key,
                    azure_endpoint=self.endpoint,
                    api_version=self.api_version,
                )
                self._azure_rest = False
            except ImportError:
                from .._internal.clients.openai_rest import OpenAIClient
                base = (self.endpoint or "").rstrip("/") + f"/openai/deployments/{self.default_model}"
                self._client = OpenAIClient(
                    api_key=self.api_key or "",
                    base_url=base,
                    extra_headers={"api-key": self.api_key or ""},
                )
                self._azure_query = f"?api-version={self.api_version}"
                self._azure_rest = True
        return self._client
    
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        client = self._get_client()
        model_name = model or self.default_model
        
        # Build params
        params = {
            "model": model_name,
            "messages": messages,
        }
        
        # Handle model-specific parameters
        if "gpt-5" in model_name.lower():
            params["max_completion_tokens"] = max_tokens or 4096
            # gpt-5.x only supports temperature=1
            params["temperature"] = 1
        else:
            if max_tokens:
                params["max_tokens"] = max_tokens
            params["temperature"] = temperature
        
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(**params)
        ) if not getattr(self, "_azure_rest", False) else await asyncio.to_thread(
            lambda: client._client.post(  # noqa: SLF001
                f"/chat/completions{getattr(self, '_azure_query', '')}",
                json=params,
            ).raise_for_status().json()
        )

        if getattr(self, "_azure_rest", False):
            return response["choices"][0]["message"]["content"]
        return response.choices[0].message.content
    
    async def embed(
        self,
        text: Union[str, List[str]],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        client = self._get_client()
        
        texts = [text] if isinstance(text, str) else text
        embed_model = model or "text-embedding-ada-002"
        
        if getattr(self, "_azure_rest", False):
            response = await asyncio.to_thread(
                lambda: client._client.post(  # noqa: SLF001
                    f"/embeddings{getattr(self, '_azure_query', '')}",
                    json={"input": texts, "model": embed_model},
                ).raise_for_status().json()
            )
            return [item["embedding"] for item in response["data"]]

        response = await asyncio.to_thread(
            lambda: client.embeddings.create(input=texts, model=embed_model)
        )
        return [item.embedding for item in response.data]


class AzureCosmosVectorDB(VectorDBAdapter):
    """Azure Cosmos DB for vector search."""
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        database_name: str = "vectors",
        container_name: str = "embeddings",
    ):
        self.connection_string = connection_string or os.getenv("COSMOS_CONNECTION_STRING")
        self.database_name = database_name
        self.container_name = container_name
        self._client = None
    
    def _get_container(self):
        if self._client is None:
            try:
                from azure.cosmos import CosmosClient, PartitionKey
                client = CosmosClient.from_connection_string(self.connection_string)
                database = client.create_database_if_not_exists(self.database_name)
                self._client = database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path="/id"),
                )
                self._using_rest = False
            except ImportError:
                from .._internal.clients.cosmos_rest import CosmosClient as RestCosmos
                if not self.connection_string:
                    raise RuntimeError("Cosmos requires COSMOS_CONNECTION_STRING when azure-cosmos is unavailable")
                rest = RestCosmos.from_connection_string(self.connection_string)
                rest.create_database_if_not_exists(self.database_name)
                rest.create_container_if_not_exists(self.database_name, self.container_name, "/id")
                self._client = rest
                self._using_rest = True
        return self._client
    
    async def upsert(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict] = None,
        **kwargs,
    ) -> bool:
        container = self._get_container()
        
        item = {
            "id": id,
            "vector": vector,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if getattr(self, "_using_rest", False):
            await asyncio.to_thread(
                container.upsert_item,
                self.database_name,
                self.container_name,
                item,
            )
        else:
            await asyncio.to_thread(container.upsert_item, item)
        return True
    
    async def search(
        self,
        query_vector: List[float],
        *,
        top_k: int = 10,
        filter: Optional[Dict] = None,
        **kwargs,
    ) -> List[Dict]:
        container = self._get_container()
        
        # Basic implementation - for production use Cosmos DB vector search
        query = "SELECT * FROM c"
        if getattr(self, "_using_rest", False):
            items = list(await asyncio.to_thread(
                container.query_items,
                self.database_name,
                self.container_name,
                query,
                enable_cross_partition_query=True,
            ))
        else:
            items = list(await asyncio.to_thread(
                lambda: container.query_items(query=query, enable_cross_partition_query=True)
            ))
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            import math
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0
        
        # Score and sort
        results = []
        for item in items:
            if "vector" in item:
                score = cosine_similarity(query_vector, item["vector"])
                results.append({**item, "score": score})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    async def delete(self, id: str, **kwargs) -> bool:
        container = self._get_container()
        
        try:
            await asyncio.to_thread(container.delete_item, id, id)
            return True
        except Exception:
            return False


class AzureServiceBusQueue(QueueAdapter):
    """Azure Service Bus queue implementation."""
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        queue_name: str = "default",
    ):
        self.connection_string = connection_string or os.getenv("SERVICE_BUS_CONNECTION_STRING")
        self.queue_name = queue_name
    
    async def send(self, message: Any, **kwargs) -> str:
        try:
            from azure.servicebus import ServiceBusClient, ServiceBusMessage
            import json
            
            client = ServiceBusClient.from_connection_string(self.connection_string)
            
            async with client:
                sender = client.get_queue_sender(self.queue_name)
                async with sender:
                    msg_content = json.dumps(message) if not isinstance(message, str) else message
                    msg = ServiceBusMessage(msg_content)
                    await asyncio.to_thread(sender.send_messages, msg)
                    return msg.message_id or "sent"
        except ImportError:
            from .._internal.clients.azure_servicebus_rest import ServiceBusClient as RestSB
            rest = RestSB.from_connection_string(self.connection_string or "")
            return await asyncio.to_thread(rest.send, self.queue_name, message)
    
    async def receive(self, max_messages: int = 1, **kwargs) -> List[Any]:
        try:
            from azure.servicebus import ServiceBusClient
            import json
            
            client = ServiceBusClient.from_connection_string(self.connection_string)
            
            async with client:
                receiver = client.get_queue_receiver(self.queue_name)
                async with receiver:
                    messages = await asyncio.to_thread(
                        lambda: receiver.receive_messages(max_message_count=max_messages)
                    )
                    
                    results = []
                    for msg in messages:
                        try:
                            content = json.loads(str(msg))
                        except json.JSONDecodeError:
                            content = str(msg)
                        results.append({"id": msg.message_id, "content": content})
                    
                    return results
        except ImportError:
            from .._internal.clients.azure_servicebus_rest import ServiceBusClient as RestSB
            rest = RestSB.from_connection_string(self.connection_string or "")
            return await asyncio.to_thread(rest.receive, self.queue_name, max_messages=max_messages)
    
    async def acknowledge(self, message_id: str, **kwargs) -> bool:
        # In Service Bus, messages are completed when received with auto-complete
        return True


class AzureRedisCache(CacheAdapter):
    """Azure Cache for Redis implementation."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 6380,
        password: Optional[str] = None,
        ssl: bool = True,
    ):
        self.host = host or os.getenv("REDIS_HOST")
        self.port = port
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.ssl = ssl
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                import redis  # type: ignore
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    ssl=self.ssl,
                )
            except ImportError:
                from .._internal.redis_resp import RedisClient
                self._client = RedisClient(
                    host=self.host or "127.0.0.1",
                    port=self.port,
                    password=self.password,
                )
        return self._client
    
    async def get(self, key: str, **kwargs) -> Optional[Any]:
        import json
        client = self._get_client()
        value = await asyncio.to_thread(client.get, key)
        
        if value is None:
            return None
        
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value.decode() if isinstance(value, bytes) else value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        **kwargs,
    ) -> bool:
        import json
        client = self._get_client()
        
        data = json.dumps(value) if not isinstance(value, str) else value
        
        if ttl:
            await asyncio.to_thread(client.setex, key, ttl, data)
        else:
            await asyncio.to_thread(client.set, key, data)
        
        return True
    
    async def delete(self, key: str, **kwargs) -> bool:
        client = self._get_client()
        result = await asyncio.to_thread(client.delete, key)
        return result > 0


# =============================================================================
# AWS Implementations (Stubs for portability)
# =============================================================================

class AWSS3Storage(StorageAdapter):
    """AWS S3 Storage implementation."""
    
    def __init__(
        self,
        bucket_name: str = "default",
        region: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._rest_client = None

    def _get_rest(self):
        if self._rest_client is None:
            from .._internal.clients.s3_rest import S3Client
            from .._internal.clients.aws_sigv4 import AWSCredentials
            self._rest_client = S3Client(
                credentials=AWSCredentials.from_env(),
                region=self.region,
            )
        return self._rest_client

    async def upload(self, path: str, content: Union[str, bytes], **kwargs) -> str:
        data = content.encode() if isinstance(content, str) else content
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            await asyncio.to_thread(s3.put_object, Bucket=self.bucket_name, Key=path, Body=data)
        except ImportError:
            client = self._get_rest()
            await asyncio.to_thread(client.upload, self.bucket_name, path, data)
        return f"s3://{self.bucket_name}/{path}"
    
    async def download(self, path: str, **kwargs) -> Union[str, bytes]:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            response = await asyncio.to_thread(s3.get_object, Bucket=self.bucket_name, Key=path)
            content = response["Body"].read()
        except ImportError:
            client = self._get_rest()
            content = await asyncio.to_thread(client.download, self.bucket_name, path)
        
        try:
            return content.decode()
        except UnicodeDecodeError:
            return content
    
    async def delete(self, path: str, **kwargs) -> bool:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            try:
                await asyncio.to_thread(s3.delete_object, Bucket=self.bucket_name, Key=path)
                return True
            except Exception:
                return False
        except ImportError:
            try:
                await asyncio.to_thread(self._get_rest().delete, self.bucket_name, path)
                return True
            except Exception:
                return False
    
    async def list(self, prefix: str = "", **kwargs) -> List[str]:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            response = await asyncio.to_thread(
                s3.list_objects_v2, Bucket=self.bucket_name, Prefix=prefix
            )
            return [obj["Key"] for obj in response.get("Contents", [])]
        except ImportError:
            return await asyncio.to_thread(self._get_rest().list_objects, self.bucket_name, prefix)
    
    async def exists(self, path: str, **kwargs) -> bool:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            try:
                await asyncio.to_thread(s3.head_object, Bucket=self.bucket_name, Key=path)
                return True
            except Exception:
                return False
        except ImportError:
            try:
                return await asyncio.to_thread(self._get_rest().exists, self.bucket_name, path)
            except Exception:
                return False


class AWSBedrockLLM(LLMAdapter):
    """AWS Bedrock LLM implementation."""
    
    def __init__(
        self,
        region: Optional[str] = None,
        default_model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
    ):
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.default_model = default_model
    
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        try:
            import boto3
            import json
            
            client = boto3.client("bedrock-runtime", region_name=self.region)
            model_id = model or self.default_model
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": messages,
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
            }
            
            response = await asyncio.to_thread(
                client.invoke_model,
                modelId=model_id,
                body=json.dumps(body),
            )
            
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except ImportError:
            return await asyncio.to_thread(
                self._chat_rest, messages, model, temperature, max_tokens
            )

    def _chat_rest(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        import json
        from .._internal.clients.aws_sigv4 import AWSCredentials, sign_request
        from .._internal import http as _http
        creds = AWSCredentials.from_env()
        model_id = model or self.default_model
        url = (
            f"https://bedrock-runtime.{self.region}.amazonaws.com/model/{model_id}/invoke"
        )
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }).encode("utf-8")
        headers = sign_request(
            method="POST",
            url=url,
            region=self.region,
            service="bedrock",
            credentials=creds,
            headers={"Content-Type": "application/json"},
            body=body,
        )
        resp = _http.Client(timeout=120.0).post(url, data=body, headers=headers).raise_for_status()
        result = resp.json()
        # Anthropic-Bedrock response shape
        if "content" in result and result["content"]:
            return result["content"][0].get("text", "")
        return result.get("completion", "")
    
    async def embed(
        self,
        text: Union[str, List[str]],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        texts = [text] if isinstance(text, str) else list(text)
        try:
            import boto3
            import json
            
            client = boto3.client("bedrock-runtime", region_name=self.region)
            model_id = model or "amazon.titan-embed-text-v1"
            
            embeddings = []
            for t in texts:
                body = {"inputText": t}
                response = await asyncio.to_thread(
                    client.invoke_model,
                    modelId=model_id,
                    body=json.dumps(body),
                )
                result = json.loads(response["body"].read())
                embeddings.append(result["embedding"])
            return embeddings
        except ImportError:
            return await asyncio.to_thread(self._embed_rest, texts, model)

    def _embed_rest(self, texts: List[str], model: Optional[str]) -> List[List[float]]:
        import json
        from .._internal.clients.aws_sigv4 import AWSCredentials, sign_request
        from .._internal import http as _http
        creds = AWSCredentials.from_env()
        model_id = model or "amazon.titan-embed-text-v1"
        url = (
            f"https://bedrock-runtime.{self.region}.amazonaws.com/model/{model_id}/invoke"
        )
        client = _http.Client(timeout=120.0)
        out: List[List[float]] = []
        for t in texts:
            body = json.dumps({"inputText": t}).encode("utf-8")
            headers = sign_request(
                method="POST",
                url=url,
                region=self.region,
                service="bedrock",
                credentials=creds,
                headers={"Content-Type": "application/json"},
                body=body,
            )
            resp = client.post(url, data=body, headers=headers).raise_for_status()
            out.append(resp.json().get("embedding", []))
        return out


# =============================================================================
# GCP Implementations (Stubs for portability)
# =============================================================================

class GCPCloudStorage(StorageAdapter):
    """Google Cloud Storage implementation."""
    
    def __init__(
        self,
        bucket_name: str = "default",
        project: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._rest_client = None

    def _get_rest(self):
        if self._rest_client is None:
            from .._internal.clients.gcp_rest import (
                ServiceAccountCredentials,
                GCSClient,
            )
            self._rest_client = GCSClient(credentials=ServiceAccountCredentials.from_env())
        return self._rest_client

    async def upload(self, path: str, content: Union[str, bytes], **kwargs) -> str:
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client(project=self.project)
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(path)

            data = content.encode() if isinstance(content, str) else content
            await asyncio.to_thread(blob.upload_from_string, data)

            return f"gs://{self.bucket_name}/{path}"
        except ImportError:
            data = content.encode() if isinstance(content, str) else content
            await asyncio.to_thread(self._get_rest().upload, self.bucket_name, path, data)
            return f"gs://{self.bucket_name}/{path}"

    async def download(self, path: str, **kwargs) -> Union[str, bytes]:
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client(project=self.project)
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(path)

            content = await asyncio.to_thread(blob.download_as_bytes)
        except ImportError:
            content = await asyncio.to_thread(self._get_rest().download, self.bucket_name, path)

        try:
            return content.decode()
        except UnicodeDecodeError:
            return content

    async def delete(self, path: str, **kwargs) -> bool:
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client(project=self.project)
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(path)

            try:
                await asyncio.to_thread(blob.delete)
                return True
            except Exception:
                return False
        except ImportError:
            try:
                await asyncio.to_thread(self._get_rest().delete, self.bucket_name, path)
                return True
            except Exception:
                return False

    async def list(self, prefix: str = "", **kwargs) -> List[str]:
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client(project=self.project)
            bucket = client.bucket(self.bucket_name)

            blobs = await asyncio.to_thread(lambda: list(bucket.list_blobs(prefix=prefix)))
            return [blob.name for blob in blobs]
        except ImportError:
            return await asyncio.to_thread(self._get_rest().list_objects, self.bucket_name, prefix)

    async def exists(self, path: str, **kwargs) -> bool:
        try:
            from google.cloud import storage  # type: ignore

            client = storage.Client(project=self.project)
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(path)

            return await asyncio.to_thread(blob.exists)
        except ImportError:
            return await asyncio.to_thread(self._get_rest().exists, self.bucket_name, path)


class GCPVertexAILLM(LLMAdapter):
    """Google Vertex AI LLM implementation."""
    
    def __init__(
        self,
        project: Optional[str] = None,
        location: str = "us-central1",
        default_model: str = "gemini-1.5-pro",
    ):
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.default_model = default_model
    
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            
            vertexai.init(project=self.project, location=self.location)
            
            model_instance = GenerativeModel(model or self.default_model)
            
            # Convert messages to Vertex AI format
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            
            config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens or 4096,
            }
            
            response = await asyncio.to_thread(
                model_instance.generate_content,
                prompt,
                generation_config=config,
            )
            
            return response.text
        except ImportError:
            return await asyncio.to_thread(
                self._chat_rest, messages, model, temperature, max_tokens
            )

    def _chat_rest(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        from .._internal.clients.gcp_rest import (
            ServiceAccountCredentials,
            VertexAIClient,
        )

        creds = ServiceAccountCredentials.from_env()
        project = self.project or creds.project_id
        if not project:
            raise RuntimeError("Vertex AI requires a GCP project (via constructor or service account)")
        client = VertexAIClient(credentials=creds, project=project, location=self.location)
        # Map roles: assistant -> model, others -> user
        contents = [
            {
                "role": "model" if m.get("role") == "assistant" else "user",
                "parts": [{"text": m.get("content", "")}],
            }
            for m in messages
        ]
        resp = client.generate_content(
            model or self.default_model,
            contents,
            temperature=temperature,
            max_output_tokens=max_tokens or 4096,
        )
        try:
            return resp["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:  # noqa: BLE001
            raise RuntimeError(f"Unexpected Vertex AI response: {resp}") from exc
    
    async def embed(
        self,
        text: Union[str, List[str]],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> List[List[float]]:
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel
            
            vertexai.init(project=self.project, location=self.location)
            
            model_instance = TextEmbeddingModel.from_pretrained(model or "textembedding-gecko@003")
            
            texts = [text] if isinstance(text, str) else text
            embeddings = await asyncio.to_thread(model_instance.get_embeddings, texts)
            
            return [e.values for e in embeddings]
        except ImportError:
            texts = [text] if isinstance(text, str) else list(text)
            return await asyncio.to_thread(self._embed_rest, texts, model)

    def _embed_rest(self, texts: List[str], model: Optional[str]) -> List[List[float]]:
        from .._internal.clients.gcp_rest import (
            ServiceAccountCredentials,
            VertexAIClient,
        )

        creds = ServiceAccountCredentials.from_env()
        project = self.project or creds.project_id
        if not project:
            raise RuntimeError("Vertex AI requires a GCP project (via constructor or service account)")
        client = VertexAIClient(credentials=creds, project=project, location=self.location)
        return client.predict_embeddings(model or "textembedding-gecko@003", texts)


# =============================================================================
# Unified Adapter Classes
# =============================================================================

class AzureAdapter:
    """
    Unified Azure services adapter.
    
    Usage:
        >>> adapter = AzureAdapter()
        >>> await adapter.storage.upload("file.txt", "content")
        >>> response = await adapter.llm.generate("Hello")
    """
    
    def __init__(
        self,
        *,
        storage_container: str = "default",
        cosmos_database: str = "vectors",
        queue_name: str = "default",
        llm_model: str = "gpt-4o",
    ):
        self._storage = None
        self._llm = None
        self._vectordb = None
        self._queue = None
        self._cache = None
        
        self.storage_container = storage_container
        self.cosmos_database = cosmos_database
        self.queue_name = queue_name
        self.llm_model = llm_model
    
    @property
    def storage(self) -> AzureBlobStorage:
        if self._storage is None:
            self._storage = AzureBlobStorage(container_name=self.storage_container)
        return self._storage
    
    @property
    def llm(self) -> AzureOpenAILLM:
        if self._llm is None:
            self._llm = AzureOpenAILLM(default_model=self.llm_model)
        return self._llm
    
    @property
    def vectordb(self) -> AzureCosmosVectorDB:
        if self._vectordb is None:
            self._vectordb = AzureCosmosVectorDB(database_name=self.cosmos_database)
        return self._vectordb
    
    @property
    def queue(self) -> AzureServiceBusQueue:
        if self._queue is None:
            self._queue = AzureServiceBusQueue(queue_name=self.queue_name)
        return self._queue
    
    @property
    def cache(self) -> AzureRedisCache:
        if self._cache is None:
            self._cache = AzureRedisCache()
        return self._cache


class AWSAdapter:
    """
    Unified AWS services adapter.
    
    Usage:
        >>> adapter = AWSAdapter(bucket="my-bucket")
        >>> await adapter.storage.upload("file.txt", "content")
        >>> response = await adapter.llm.generate("Hello")
    """
    
    def __init__(
        self,
        *,
        bucket: str = "default",
        region: Optional[str] = None,
        llm_model: str = "anthropic.claude-3-sonnet-20240229-v1:0",
    ):
        self._storage = None
        self._llm = None
        
        self.bucket = bucket
        self.region = region
        self.llm_model = llm_model
    
    @property
    def storage(self) -> AWSS3Storage:
        if self._storage is None:
            self._storage = AWSS3Storage(bucket_name=self.bucket, region=self.region)
        return self._storage
    
    @property
    def llm(self) -> AWSBedrockLLM:
        if self._llm is None:
            self._llm = AWSBedrockLLM(region=self.region, default_model=self.llm_model)
        return self._llm


class GCPAdapter:
    """
    Unified GCP services adapter.
    
    Usage:
        >>> adapter = GCPAdapter(bucket="my-bucket")
        >>> await adapter.storage.upload("file.txt", "content")
        >>> response = await adapter.llm.generate("Hello")
    """
    
    def __init__(
        self,
        *,
        bucket: str = "default",
        project: Optional[str] = None,
        location: str = "us-central1",
        llm_model: str = "gemini-1.5-pro",
    ):
        self._storage = None
        self._llm = None
        
        self.bucket = bucket
        self.project = project
        self.location = location
        self.llm_model = llm_model
    
    @property
    def storage(self) -> GCPCloudStorage:
        if self._storage is None:
            self._storage = GCPCloudStorage(bucket_name=self.bucket, project=self.project)
        return self._storage
    
    @property
    def llm(self) -> GCPVertexAILLM:
        if self._llm is None:
            self._llm = GCPVertexAILLM(
                project=self.project,
                location=self.location,
                default_model=self.llm_model,
            )
        return self._llm


# =============================================================================
# Auto-detect Adapter
# =============================================================================

def get_adapter(provider: Optional[str] = None) -> Union[AzureAdapter, AWSAdapter, GCPAdapter]:
    """
    Get the appropriate cloud adapter based on provider or environment.
    
    Args:
        provider: Explicit provider ("azure", "aws", "gcp")
        
    Returns:
        Cloud adapter instance
        
    Example:
        >>> adapter = get_adapter()  # Auto-detect
        >>> adapter = get_adapter("azure")  # Explicit
    """
    if provider:
        provider = provider.lower()
        if provider == "azure":
            return AzureAdapter()
        elif provider == "aws":
            return AWSAdapter()
        elif provider == "gcp":
            return GCPAdapter()
    
    # Auto-detect based on environment variables
    if os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        return AzureAdapter()
    elif os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_REGION"):
        return AWSAdapter()
    elif os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return GCPAdapter()
    
    # Default to Azure
    logger.warning("No cloud provider detected, defaulting to Azure")
    return AzureAdapter()
