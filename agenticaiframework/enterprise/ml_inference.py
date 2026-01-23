"""
Enterprise ML Inference Service Module.

Machine learning model inference, batch predictions,
model versioning, and A/B testing for ML models.

Example:
    # Create inference service
    ml = create_ml_inference()
    
    # Register model
    await ml.register_model(
        name="sentiment",
        version="1.0.0",
        predictor=my_model_predict,
    )
    
    # Make prediction
    result = await ml.predict(
        model="sentiment",
        input={"text": "This is great!"},
    )
    
    # Batch prediction
    results = await ml.predict_batch(
        model="sentiment",
        inputs=[{"text": "Good"}, {"text": "Bad"}],
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class InferenceError(Exception):
    """Inference error."""
    pass


class ModelNotFoundError(InferenceError):
    """Model not found error."""
    pass


class ModelStatus(str, Enum):
    """Model status."""
    LOADING = "loading"
    READY = "ready"
    SERVING = "serving"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class ModelType(str, Enum):
    """Model type."""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    NLP = "nlp"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    GENERATIVE = "generative"
    CUSTOM = "custom"


class BatchStrategy(str, Enum):
    """Batch strategy."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DYNAMIC = "dynamic"


@dataclass
class ModelConfig:
    """Model configuration."""
    name: str = ""
    version: str = "1.0.0"
    model_type: ModelType = ModelType.CUSTOM
    
    # Resources
    max_batch_size: int = 32
    timeout_seconds: float = 30.0
    max_concurrent: int = 10
    
    # Preprocessing
    preprocess_fn: Optional[str] = None
    postprocess_fn: Optional[str] = None
    
    # Configuration
    warm_up: bool = True
    cache_predictions: bool = False
    cache_ttl_seconds: int = 300
    
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInfo:
    """Model information."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    model_type: ModelType = ModelType.CUSTOM
    
    # Status
    status: ModelStatus = ModelStatus.LOADING
    
    # Statistics
    total_predictions: int = 0
    avg_latency_ms: float = 0.0
    error_count: int = 0
    
    # Traffic
    traffic_weight: float = 100.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None


@dataclass
class PredictionRequest:
    """Prediction request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str = ""
    model_version: Optional[str] = None
    
    input: Any = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PredictionResult:
    """Prediction result."""
    request_id: str = ""
    model_name: str = ""
    model_version: str = ""
    
    output: Any = None
    confidence: Optional[float] = None
    
    # Metadata
    latency_ms: float = 0.0
    cached: bool = False
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BatchResult:
    """Batch prediction result."""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str = ""
    
    results: List[PredictionResult] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    total_count: int = 0
    success_count: int = 0
    error_count: int = 0
    
    latency_ms: float = 0.0


@dataclass
class ModelExperiment:
    """A/B test experiment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    
    # Models
    control_model: str = ""
    control_version: str = ""
    treatment_model: str = ""
    treatment_version: str = ""
    
    # Traffic split
    treatment_percentage: float = 50.0
    
    # Status
    active: bool = True
    
    # Metrics
    control_count: int = 0
    treatment_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


@dataclass
class InferenceStats:
    """Inference statistics."""
    total_models: int = 0
    active_models: int = 0
    total_predictions: int = 0
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    active_experiments: int = 0


# Model predictor
class ModelPredictor(ABC):
    """Model predictor interface."""
    
    @abstractmethod
    async def predict(
        self,
        input: Any,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make prediction."""
        pass
    
    async def predict_batch(
        self,
        inputs: List[Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """Make batch predictions."""
        results = []
        for inp in inputs:
            result = await self.predict(inp, parameters)
            results.append(result)
        return results
    
    async def warm_up(self) -> None:
        """Warm up model."""
        pass
    
    async def shutdown(self) -> None:
        """Shutdown model."""
        pass


class CallablePredictor(ModelPredictor):
    """Callable-based predictor."""
    
    def __init__(
        self,
        predictor: Callable,
        preprocess: Optional[Callable] = None,
        postprocess: Optional[Callable] = None,
    ):
        self._predictor = predictor
        self._preprocess = preprocess
        self._postprocess = postprocess
    
    async def predict(
        self,
        input: Any,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make prediction."""
        # Preprocess
        if self._preprocess:
            if asyncio.iscoroutinefunction(self._preprocess):
                input = await self._preprocess(input)
            else:
                input = self._preprocess(input)
        
        # Predict
        if asyncio.iscoroutinefunction(self._predictor):
            result = await self._predictor(input, **(parameters or {}))
        else:
            result = self._predictor(input, **(parameters or {}))
        
        # Postprocess
        if self._postprocess:
            if asyncio.iscoroutinefunction(self._postprocess):
                result = await self._postprocess(result)
            else:
                result = self._postprocess(result)
        
        return result


# Model registry
class ModelRegistry:
    """Model registry."""
    
    def __init__(self):
        self._models: Dict[str, Dict[str, ModelInfo]] = defaultdict(dict)
        self._predictors: Dict[str, Dict[str, ModelPredictor]] = defaultdict(dict)
        self._configs: Dict[str, Dict[str, ModelConfig]] = defaultdict(dict)
    
    async def register(
        self,
        name: str,
        version: str,
        predictor: ModelPredictor,
        config: Optional[ModelConfig] = None,
    ) -> ModelInfo:
        """Register model."""
        config = config or ModelConfig(name=name, version=version)
        
        info = ModelInfo(
            name=name,
            version=version,
            model_type=config.model_type,
            status=ModelStatus.LOADING,
        )
        
        self._models[name][version] = info
        self._predictors[name][version] = predictor
        self._configs[name][version] = config
        
        # Warm up
        if config.warm_up:
            try:
                await predictor.warm_up()
            except Exception as e:
                logger.warning(f"Warm up failed: {e}")
        
        info.status = ModelStatus.READY
        
        return info
    
    async def unregister(self, name: str, version: str) -> bool:
        """Unregister model."""
        if name in self._models and version in self._models[name]:
            predictor = self._predictors[name].pop(version, None)
            if predictor:
                await predictor.shutdown()
            
            self._models[name].pop(version, None)
            self._configs[name].pop(version, None)
            
            return True
        return False
    
    def get_model(self, name: str, version: Optional[str] = None) -> Optional[ModelInfo]:
        """Get model info."""
        versions = self._models.get(name, {})
        
        if version:
            return versions.get(version)
        
        # Get latest version
        if versions:
            return max(versions.values(), key=lambda m: m.version)
        
        return None
    
    def get_predictor(self, name: str, version: str) -> Optional[ModelPredictor]:
        """Get model predictor."""
        return self._predictors.get(name, {}).get(version)
    
    def get_config(self, name: str, version: str) -> Optional[ModelConfig]:
        """Get model config."""
        return self._configs.get(name, {}).get(version)
    
    def list_models(self) -> List[ModelInfo]:
        """List all models."""
        models = []
        for versions in self._models.values():
            models.extend(versions.values())
        return models
    
    def list_versions(self, name: str) -> List[str]:
        """List model versions."""
        return list(self._models.get(name, {}).keys())


# Prediction cache
class PredictionCache:
    """Prediction cache."""
    
    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def _make_key(
        self,
        model_name: str,
        model_version: str,
        input: Any,
    ) -> str:
        """Make cache key."""
        input_str = str(input)
        key_data = f"{model_name}:{model_version}:{input_str}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(
        self,
        model_name: str,
        model_version: str,
        input: Any,
        ttl_seconds: int,
    ) -> Optional[Any]:
        """Get cached prediction."""
        key = self._make_key(model_name, model_version, input)
        
        cached = self._cache.get(key)
        if cached:
            result, timestamp = cached
            age = (datetime.utcnow() - timestamp).total_seconds()
            
            if age < ttl_seconds:
                self._hits += 1
                return result
        
        self._misses += 1
        return None
    
    def set(
        self,
        model_name: str,
        model_version: str,
        input: Any,
        result: Any,
    ) -> None:
        """Cache prediction."""
        key = self._make_key(model_name, model_version, input)
        
        # Evict if full
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[key] = (result, datetime.utcnow())
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
    
    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return (self._hits / total * 100) if total > 0 else 0.0


# ML inference service
class MLInferenceService:
    """ML inference service."""
    
    def __init__(
        self,
        cache_enabled: bool = True,
        cache_size: int = 10000,
        default_timeout: float = 30.0,
    ):
        self._registry = ModelRegistry()
        self._cache = PredictionCache(cache_size) if cache_enabled else None
        self._default_timeout = default_timeout
        
        self._experiments: Dict[str, ModelExperiment] = {}
        
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        
        self._prediction_history: List[PredictionResult] = []
        self._listeners: List[Callable] = []
    
    async def register_model(
        self,
        name: str,
        version: str = "1.0.0",
        predictor: Optional[Union[ModelPredictor, Callable]] = None,
        model_type: Union[str, ModelType] = ModelType.CUSTOM,
        preprocess: Optional[Callable] = None,
        postprocess: Optional[Callable] = None,
        **kwargs,
    ) -> ModelInfo:
        """Register model."""
        if isinstance(model_type, str):
            model_type = ModelType(model_type)
        
        # Wrap callable
        if predictor and not isinstance(predictor, ModelPredictor):
            predictor = CallablePredictor(predictor, preprocess, postprocess)
        
        if not predictor:
            raise InferenceError("Predictor required")
        
        config = ModelConfig(
            name=name,
            version=version,
            model_type=model_type,
            **kwargs,
        )
        
        info = await self._registry.register(name, version, predictor, config)
        
        # Create semaphore
        key = f"{name}:{version}"
        self._semaphores[key] = asyncio.Semaphore(config.max_concurrent)
        
        logger.info(f"Model registered: {name}:{version}")
        
        return info
    
    async def unregister_model(
        self,
        name: str,
        version: str,
    ) -> bool:
        """Unregister model."""
        key = f"{name}:{version}"
        self._semaphores.pop(key, None)
        
        return await self._registry.unregister(name, version)
    
    async def get_model(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> Optional[ModelInfo]:
        """Get model info."""
        return self._registry.get_model(name, version)
    
    async def list_models(
        self,
        model_type: Optional[ModelType] = None,
    ) -> List[ModelInfo]:
        """List models."""
        models = self._registry.list_models()
        
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        
        return models
    
    async def predict(
        self,
        model: str,
        input: Any,
        version: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> PredictionResult:
        """Make prediction."""
        # Get model info
        model_info = self._registry.get_model(model, version)
        
        if not model_info:
            raise ModelNotFoundError(f"Model not found: {model}")
        
        if model_info.status not in (ModelStatus.READY, ModelStatus.SERVING):
            raise InferenceError(f"Model not ready: {model}")
        
        version = model_info.version
        
        # Check experiment
        experiment = self._get_active_experiment(model)
        if experiment:
            version = self._route_experiment(experiment)
            model_info = self._registry.get_model(model, version)
        
        config = self._registry.get_config(model, version)
        predictor = self._registry.get_predictor(model, version)
        
        if not predictor:
            raise InferenceError(f"Predictor not found: {model}:{version}")
        
        # Check cache
        if self._cache and config and config.cache_predictions:
            cached = self._cache.get(model, version, input, config.cache_ttl_seconds)
            if cached is not None:
                return PredictionResult(
                    request_id=str(uuid.uuid4()),
                    model_name=model,
                    model_version=version,
                    output=cached,
                    cached=True,
                )
        
        # Make prediction
        start_time = time.monotonic()
        timeout = timeout or (config.timeout_seconds if config else self._default_timeout)
        
        key = f"{model}:{version}"
        semaphore = self._semaphores.get(key, asyncio.Semaphore(10))
        
        async with semaphore:
            try:
                output = await asyncio.wait_for(
                    predictor.predict(input, parameters),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                model_info.error_count += 1
                raise InferenceError(f"Prediction timeout: {model}")
            except Exception as e:
                model_info.error_count += 1
                raise InferenceError(f"Prediction failed: {e}")
        
        latency = (time.monotonic() - start_time) * 1000
        
        # Update stats
        model_info.total_predictions += 1
        model_info.last_used_at = datetime.utcnow()
        model_info.avg_latency_ms = (
            (model_info.avg_latency_ms * (model_info.total_predictions - 1) + latency)
            / model_info.total_predictions
        )
        
        # Cache result
        if self._cache and config and config.cache_predictions:
            self._cache.set(model, version, input, output)
        
        result = PredictionResult(
            request_id=str(uuid.uuid4()),
            model_name=model,
            model_version=version,
            output=output,
            latency_ms=latency,
        )
        
        self._record_prediction(result)
        
        return result
    
    async def predict_batch(
        self,
        model: str,
        inputs: List[Any],
        version: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        strategy: BatchStrategy = BatchStrategy.PARALLEL,
        max_batch_size: Optional[int] = None,
    ) -> BatchResult:
        """Make batch predictions."""
        start_time = time.monotonic()
        
        model_info = self._registry.get_model(model, version)
        
        if not model_info:
            raise ModelNotFoundError(f"Model not found: {model}")
        
        version = model_info.version
        config = self._registry.get_config(model, version)
        predictor = self._registry.get_predictor(model, version)
        
        batch_size = max_batch_size or (config.max_batch_size if config else 32)
        
        result = BatchResult(
            model_name=model,
            total_count=len(inputs),
        )
        
        if strategy == BatchStrategy.SEQUENTIAL:
            for i, inp in enumerate(inputs):
                try:
                    pred = await self.predict(model, inp, version, parameters)
                    result.results.append(pred)
                    result.success_count += 1
                except Exception as e:
                    result.errors.append({"index": i, "error": str(e)})
                    result.error_count += 1
        
        elif strategy == BatchStrategy.PARALLEL:
            # Process in batches
            for batch_start in range(0, len(inputs), batch_size):
                batch = inputs[batch_start:batch_start + batch_size]
                
                tasks = [
                    self.predict(model, inp, version, parameters)
                    for inp in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, res in enumerate(batch_results):
                    if isinstance(res, Exception):
                        result.errors.append({
                            "index": batch_start + i,
                            "error": str(res),
                        })
                        result.error_count += 1
                    else:
                        result.results.append(res)
                        result.success_count += 1
        
        elif strategy == BatchStrategy.DYNAMIC:
            # Use native batch if available
            if predictor:
                try:
                    outputs = await predictor.predict_batch(inputs, parameters)
                    
                    for i, output in enumerate(outputs):
                        result.results.append(PredictionResult(
                            request_id=str(uuid.uuid4()),
                            model_name=model,
                            model_version=version,
                            output=output,
                        ))
                        result.success_count += 1
                
                except Exception as e:
                    # Fall back to parallel
                    return await self.predict_batch(
                        model, inputs, version, parameters, BatchStrategy.PARALLEL
                    )
        
        result.latency_ms = (time.monotonic() - start_time) * 1000
        
        return result
    
    async def create_experiment(
        self,
        name: str,
        control_model: str,
        control_version: str,
        treatment_model: str,
        treatment_version: str,
        treatment_percentage: float = 50.0,
    ) -> ModelExperiment:
        """Create A/B experiment."""
        experiment = ModelExperiment(
            name=name,
            control_model=control_model,
            control_version=control_version,
            treatment_model=treatment_model,
            treatment_version=treatment_version,
            treatment_percentage=treatment_percentage,
        )
        
        self._experiments[experiment.id] = experiment
        
        logger.info(f"Experiment created: {name}")
        
        return experiment
    
    async def end_experiment(self, experiment_id: str) -> Optional[ModelExperiment]:
        """End experiment."""
        experiment = self._experiments.get(experiment_id)
        
        if experiment:
            experiment.active = False
            experiment.ended_at = datetime.utcnow()
        
        return experiment
    
    async def get_experiment_results(
        self,
        experiment_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get experiment results."""
        experiment = self._experiments.get(experiment_id)
        
        if not experiment:
            return None
        
        return {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "control": {
                "model": experiment.control_model,
                "version": experiment.control_version,
                "count": experiment.control_count,
            },
            "treatment": {
                "model": experiment.treatment_model,
                "version": experiment.treatment_version,
                "count": experiment.treatment_count,
            },
            "active": experiment.active,
        }
    
    async def get_stats(self) -> InferenceStats:
        """Get statistics."""
        models = self._registry.list_models()
        
        active = [m for m in models if m.status in (ModelStatus.READY, ModelStatus.SERVING)]
        
        total_predictions = sum(m.total_predictions for m in models)
        
        avg_latency = 0.0
        if models:
            latencies = [m.avg_latency_ms for m in models if m.total_predictions > 0]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
        
        cache_hit_rate = self._cache.hit_rate if self._cache else 0.0
        
        active_experiments = len([e for e in self._experiments.values() if e.active])
        
        return InferenceStats(
            total_models=len(models),
            active_models=len(active),
            total_predictions=total_predictions,
            avg_latency_ms=avg_latency,
            cache_hit_rate=cache_hit_rate,
            active_experiments=active_experiments,
        )
    
    def _get_active_experiment(self, model_name: str) -> Optional[ModelExperiment]:
        """Get active experiment for model."""
        for experiment in self._experiments.values():
            if experiment.active and experiment.control_model == model_name:
                return experiment
        return None
    
    def _route_experiment(self, experiment: ModelExperiment) -> str:
        """Route to experiment version."""
        if random.random() * 100 < experiment.treatment_percentage:
            experiment.treatment_count += 1
            return experiment.treatment_version
        else:
            experiment.control_count += 1
            return experiment.control_version
    
    def _record_prediction(self, result: PredictionResult) -> None:
        """Record prediction."""
        self._prediction_history.append(result)
        if len(self._prediction_history) > 10000:
            self._prediction_history = self._prediction_history[-10000:]
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def shutdown(self) -> None:
        """Shutdown service."""
        models = self._registry.list_models()
        
        for model in models:
            await self._registry.unregister(model.name, model.version)
        
        logger.info("ML inference service shutdown complete")


# Factory functions
def create_ml_inference(
    cache_enabled: bool = True,
    cache_size: int = 10000,
) -> MLInferenceService:
    """Create ML inference service."""
    return MLInferenceService(
        cache_enabled=cache_enabled,
        cache_size=cache_size,
    )


def create_predictor(
    predict_fn: Callable,
    preprocess: Optional[Callable] = None,
    postprocess: Optional[Callable] = None,
) -> ModelPredictor:
    """Create callable predictor."""
    return CallablePredictor(predict_fn, preprocess, postprocess)


__all__ = [
    # Exceptions
    "InferenceError",
    "ModelNotFoundError",
    # Enums
    "ModelStatus",
    "ModelType",
    "BatchStrategy",
    # Data classes
    "ModelConfig",
    "ModelInfo",
    "PredictionRequest",
    "PredictionResult",
    "BatchResult",
    "ModelExperiment",
    "InferenceStats",
    # Predictor
    "ModelPredictor",
    "CallablePredictor",
    # Registry
    "ModelRegistry",
    # Cache
    "PredictionCache",
    # Service
    "MLInferenceService",
    # Factory functions
    "create_ml_inference",
    "create_predictor",
]
