"""
MongoDB Atlas Data API REST client - stdlib HTTP fallback for ``pymongo``.

Targets the Atlas Data API (https://www.mongodb.com/docs/atlas/api/data-api/),
which exposes ``/action/{find|findOne|insertOne|insertMany|updateOne|deleteOne
|aggregate}`` endpoints over HTTPS using either an API key or an Atlas App
Services bearer token. Vector search is performed via the standard
``$vectorSearch`` aggregation stage available on Atlas vector indexes.

Connection-string-based access to self-hosted MongoDB is *not* supported here
(that requires the binary wire protocol). The Data API is intended for cloud
Atlas deployments which is the documented target of ``MongoDBVectorSearchTool``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .. import http as _http


class MongoDataAPIError(Exception):
    """Raised when the Atlas Data API returns an error."""


class MongoDataAPIClient:
    """Atlas Data API REST client."""

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
        data_source: str = "Cluster0",
        database: str = "default",
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.data_source = data_source
        self.database = database
        self.timeout = timeout

    # --------------------------------------------------------------- helpers
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Access-Control-Request-Headers": "*",
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def _action(
        self,
        action: str,
        collection: str,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "dataSource": self.data_source,
            "database": self.database,
            "collection": collection,
            **body,
        }
        url = f"{self.endpoint}/action/{action}"
        resp = _http.request(
            "POST",
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise MongoDataAPIError(
                f"action {action} -> {resp.status_code}: {resp.text}"
            )
        try:
            return resp.json() or {}
        except Exception:
            return {}

    # --------------------------------------------------------------- crud
    def find(
        self,
        collection: str,
        filter: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        limit: int = 0,
        sort: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {"filter": filter or {}}
        if projection:
            body["projection"] = projection
        if limit:
            body["limit"] = limit
        if sort:
            body["sort"] = sort
        return self._action("find", collection, body).get("documents", [])

    def find_one(
        self,
        collection: str,
        filter: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        body: Dict[str, Any] = {"filter": filter}
        if projection:
            body["projection"] = projection
        return self._action("findOne", collection, body).get("document")

    def insert_one(self, collection: str, document: Dict[str, Any]) -> str:
        result = self._action("insertOne", collection, {"document": document})
        return result.get("insertedId", "")

    def insert_many(self, collection: str, documents: List[Dict[str, Any]]) -> List[str]:
        result = self._action("insertMany", collection, {"documents": documents})
        return result.get("insertedIds", [])

    def update_one(
        self,
        collection: str,
        filter: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
    ) -> Dict[str, Any]:
        return self._action(
            "updateOne",
            collection,
            {"filter": filter, "update": update, "upsert": upsert},
        )

    def delete_one(self, collection: str, filter: Dict[str, Any]) -> int:
        return self._action("deleteOne", collection, {"filter": filter}).get(
            "deletedCount", 0
        )

    # --------------------------------------------------------------- search
    def aggregate(
        self,
        collection: str,
        pipeline: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return self._action(
            "aggregate", collection, {"pipeline": pipeline}
        ).get("documents", [])

    def vector_search(
        self,
        collection: str,
        query_vector: List[float],
        index_name: str = "vector_index",
        path: str = "embedding",
        num_candidates: int = 100,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run an Atlas ``$vectorSearch`` pipeline."""
        stage: Dict[str, Any] = {
            "$vectorSearch": {
                "index": index_name,
                "path": path,
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit,
            }
        }
        if filter:
            stage["$vectorSearch"]["filter"] = filter
        # Project the search score into the result.
        score_stage = {
            "$addFields": {"_score": {"$meta": "vectorSearchScore"}}
        }
        return self.aggregate(collection, [stage, score_stage])


__all__ = ["MongoDataAPIClient", "MongoDataAPIError"]
