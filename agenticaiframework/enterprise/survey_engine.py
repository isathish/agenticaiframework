"""
Enterprise Survey Engine Module.

Questionnaires, surveys, responses, analytics,
and survey management.

Example:
    # Create survey engine
    surveys = create_survey_engine()
    
    # Create survey
    survey = await surveys.create_survey(
        title="Customer Satisfaction",
        questions=[
            {"text": "How satisfied are you?", "type": "rating", "scale": 5},
            {"text": "Would you recommend us?", "type": "nps"},
            {"text": "Any feedback?", "type": "text"},
        ],
    )
    
    # Collect response
    response = await surveys.submit_response(
        survey_id=survey.id,
        answers={"q1": 5, "q2": 9, "q3": "Great service!"},
    )
    
    # Get analytics
    analytics = await surveys.get_analytics(survey.id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import uuid
from abc import ABC, abstractmethod
from collections import Counter
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
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class SurveyError(Exception):
    """Survey error."""
    pass


class SurveyNotFoundError(SurveyError):
    """Survey not found."""
    pass


class QuestionType(str, Enum):
    """Question type."""
    TEXT = "text"
    TEXTAREA = "textarea"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    RATING = "rating"
    NPS = "nps"
    LIKERT = "likert"
    MATRIX = "matrix"
    RANKING = "ranking"
    DATE = "date"
    NUMBER = "number"
    SLIDER = "slider"


class SurveyStatus(str, Enum):
    """Survey status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ResponseStatus(str, Enum):
    """Response status."""
    PARTIAL = "partial"
    COMPLETE = "complete"
    DISQUALIFIED = "disqualified"


@dataclass
class QuestionOption:
    """Question option/choice."""
    value: str = ""
    label: str = ""
    weight: float = 1.0


@dataclass
class Question:
    """Survey question."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    type: QuestionType = QuestionType.TEXT
    description: str = ""
    required: bool = True
    options: List[QuestionOption] = field(default_factory=list)
    scale: int = 5  # For rating/likert
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    placeholder: str = ""
    validation: Dict[str, Any] = field(default_factory=dict)
    logic: Optional[Dict[str, Any]] = None  # Skip logic
    order: int = 0
    page: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Survey:
    """Survey definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: SurveyStatus = SurveyStatus.DRAFT
    questions: List[Question] = field(default_factory=list)
    welcome_message: str = ""
    thank_you_message: str = "Thank you for completing this survey!"
    redirect_url: str = ""
    anonymous: bool = True
    allow_multiple: bool = False
    randomize_questions: bool = False
    show_progress: bool = True
    max_responses: Optional[int] = None
    response_count: int = 0
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    estimated_time: int = 5  # minutes
    language: str = "en"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Answer:
    """Survey answer."""
    question_id: str = ""
    value: Any = None
    text: str = ""
    selected_options: List[str] = field(default_factory=list)


@dataclass
class SurveyResponse:
    """Survey response."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    survey_id: str = ""
    respondent_id: Optional[str] = None
    answers: Dict[str, Any] = field(default_factory=dict)
    status: ResponseStatus = ResponseStatus.COMPLETE
    ip_address: str = ""
    user_agent: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: int = 0
    page_reached: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuestionAnalytics:
    """Question analytics."""
    question_id: str = ""
    question_text: str = ""
    question_type: QuestionType = QuestionType.TEXT
    response_count: int = 0
    skip_count: int = 0
    average: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    distribution: Dict[str, int] = field(default_factory=dict)
    nps_score: Optional[float] = None
    text_responses: List[str] = field(default_factory=list)


@dataclass
class SurveyAnalytics:
    """Survey analytics."""
    survey_id: str = ""
    total_responses: int = 0
    complete_responses: int = 0
    partial_responses: int = 0
    completion_rate: float = 0.0
    average_duration: float = 0.0
    questions: List[QuestionAnalytics] = field(default_factory=list)
    response_trend: Dict[str, int] = field(default_factory=dict)
    top_drop_off_questions: List[str] = field(default_factory=list)


@dataclass
class SurveyStats:
    """Survey statistics."""
    total_surveys: int = 0
    active_surveys: int = 0
    total_responses: int = 0


# Survey store
class SurveyStore(ABC):
    """Survey storage."""
    
    @abstractmethod
    async def save(self, survey: Survey) -> None:
        pass
    
    @abstractmethod
    async def get(self, survey_id: str) -> Optional[Survey]:
        pass
    
    @abstractmethod
    async def list(self, status: Optional[SurveyStatus] = None) -> List[Survey]:
        pass
    
    @abstractmethod
    async def delete(self, survey_id: str) -> bool:
        pass


class InMemorySurveyStore(SurveyStore):
    """In-memory survey store."""
    
    def __init__(self):
        self._surveys: Dict[str, Survey] = {}
    
    async def save(self, survey: Survey) -> None:
        survey.updated_at = datetime.utcnow()
        self._surveys[survey.id] = survey
    
    async def get(self, survey_id: str) -> Optional[Survey]:
        return self._surveys.get(survey_id)
    
    async def list(self, status: Optional[SurveyStatus] = None) -> List[Survey]:
        surveys = list(self._surveys.values())
        
        if status:
            surveys = [s for s in surveys if s.status == status]
        
        return sorted(surveys, key=lambda s: s.created_at, reverse=True)
    
    async def delete(self, survey_id: str) -> bool:
        return self._surveys.pop(survey_id, None) is not None


# Response store
class ResponseStore(ABC):
    """Response storage."""
    
    @abstractmethod
    async def save(self, response: SurveyResponse) -> None:
        pass
    
    @abstractmethod
    async def get(self, response_id: str) -> Optional[SurveyResponse]:
        pass
    
    @abstractmethod
    async def query(
        self,
        survey_id: str,
        status: Optional[ResponseStatus] = None,
    ) -> List[SurveyResponse]:
        pass


class InMemoryResponseStore(ResponseStore):
    """In-memory response store."""
    
    def __init__(self):
        self._responses: Dict[str, SurveyResponse] = {}
    
    async def save(self, response: SurveyResponse) -> None:
        self._responses[response.id] = response
    
    async def get(self, response_id: str) -> Optional[SurveyResponse]:
        return self._responses.get(response_id)
    
    async def query(
        self,
        survey_id: str,
        status: Optional[ResponseStatus] = None,
    ) -> List[SurveyResponse]:
        results = [
            r for r in self._responses.values()
            if r.survey_id == survey_id
        ]
        
        if status:
            results = [r for r in results if r.status == status]
        
        return sorted(results, key=lambda r: r.started_at, reverse=True)


# Survey engine
class SurveyEngine:
    """Survey engine."""
    
    # Default Likert scale
    LIKERT_OPTIONS = [
        QuestionOption(value="1", label="Strongly Disagree", weight=1),
        QuestionOption(value="2", label="Disagree", weight=2),
        QuestionOption(value="3", label="Neutral", weight=3),
        QuestionOption(value="4", label="Agree", weight=4),
        QuestionOption(value="5", label="Strongly Agree", weight=5),
    ]
    
    def __init__(
        self,
        survey_store: Optional[SurveyStore] = None,
        response_store: Optional[ResponseStore] = None,
    ):
        self._surveys = survey_store or InMemorySurveyStore()
        self._responses = response_store or InMemoryResponseStore()
        self._stats = SurveyStats()
    
    async def create_survey(
        self,
        title: str,
        questions: List[Dict[str, Any]] = None,
        description: str = "",
        created_by: str = "",
        **kwargs,
    ) -> Survey:
        """Create survey."""
        survey = Survey(
            title=title,
            description=description,
            created_by=created_by,
            **kwargs,
        )
        
        # Add questions
        if questions:
            for i, q_def in enumerate(questions):
                survey.questions.append(self._create_question(q_def, i))
        
        await self._surveys.save(survey)
        self._stats.total_surveys += 1
        
        logger.info(f"Survey created: {title}")
        
        return survey
    
    def _create_question(
        self,
        q_def: Dict[str, Any],
        order: int = 0,
    ) -> Question:
        """Create question from definition."""
        q_type = QuestionType(q_def.get("type", "text"))
        
        question = Question(
            text=q_def.get("text", ""),
            type=q_type,
            description=q_def.get("description", ""),
            required=q_def.get("required", True),
            scale=q_def.get("scale", 5),
            order=order,
        )
        
        # Add options
        if "options" in q_def:
            for opt in q_def["options"]:
                if isinstance(opt, dict):
                    question.options.append(QuestionOption(**opt))
                else:
                    question.options.append(QuestionOption(value=str(opt), label=str(opt)))
        
        # Add default options for certain types
        if q_type == QuestionType.NPS:
            question.scale = 10
            question.options = [
                QuestionOption(value=str(i), label=str(i))
                for i in range(11)
            ]
        elif q_type == QuestionType.LIKERT and not question.options:
            question.options = list(self.LIKERT_OPTIONS)
        elif q_type == QuestionType.RATING:
            question.options = [
                QuestionOption(value=str(i), label=str(i))
                for i in range(1, question.scale + 1)
            ]
        
        return question
    
    async def get_survey(self, survey_id: str) -> Optional[Survey]:
        """Get survey."""
        return await self._surveys.get(survey_id)
    
    async def update_survey(
        self,
        survey_id: str,
        **updates,
    ) -> Optional[Survey]:
        """Update survey."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return None
        
        for key, value in updates.items():
            if hasattr(survey, key):
                setattr(survey, key, value)
        
        await self._surveys.save(survey)
        
        return survey
    
    async def add_question(
        self,
        survey_id: str,
        question_def: Dict[str, Any],
    ) -> Optional[Survey]:
        """Add question to survey."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return None
        
        order = len(survey.questions)
        survey.questions.append(self._create_question(question_def, order))
        
        await self._surveys.save(survey)
        
        return survey
    
    async def activate(self, survey_id: str) -> Optional[Survey]:
        """Activate survey."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return None
        
        survey.status = SurveyStatus.ACTIVE
        
        await self._surveys.save(survey)
        self._stats.active_surveys += 1
        
        logger.info(f"Survey activated: {survey.title}")
        
        return survey
    
    async def pause(self, survey_id: str) -> Optional[Survey]:
        """Pause survey."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return None
        
        survey.status = SurveyStatus.PAUSED
        
        await self._surveys.save(survey)
        
        return survey
    
    async def complete(self, survey_id: str) -> Optional[Survey]:
        """Mark survey as completed."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return None
        
        survey.status = SurveyStatus.COMPLETED
        
        await self._surveys.save(survey)
        self._stats.active_surveys -= 1
        
        return survey
    
    async def list_surveys(
        self,
        status: Optional[SurveyStatus] = None,
    ) -> List[Survey]:
        """List surveys."""
        return await self._surveys.list(status)
    
    # Responses
    async def submit_response(
        self,
        survey_id: str,
        answers: Dict[str, Any],
        respondent_id: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> SurveyResponse:
        """Submit survey response."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            raise SurveyNotFoundError(f"Survey not found: {survey_id}")
        
        if survey.status != SurveyStatus.ACTIVE:
            raise SurveyError("Survey is not active")
        
        # Check limits
        if survey.max_responses and survey.response_count >= survey.max_responses:
            raise SurveyError("Survey has reached maximum responses")
        
        # Check dates
        now = datetime.utcnow()
        if survey.starts_at and now < survey.starts_at:
            raise SurveyError("Survey has not started yet")
        if survey.ends_at and now > survey.ends_at:
            raise SurveyError("Survey has ended")
        
        # Validate answers
        errors = self._validate_answers(survey, answers)
        if errors:
            raise SurveyError(f"Validation errors: {errors}")
        
        # Create response
        start_time = datetime.utcnow()
        response = SurveyResponse(
            survey_id=survey_id,
            respondent_id=respondent_id,
            answers=answers,
            status=ResponseStatus.COMPLETE,
            ip_address=ip_address,
            user_agent=user_agent,
            started_at=start_time,
            completed_at=datetime.utcnow(),
        )
        response.duration_seconds = int(
            (response.completed_at - response.started_at).total_seconds()
        )
        
        await self._responses.save(response)
        
        # Update count
        survey.response_count += 1
        await self._surveys.save(survey)
        
        self._stats.total_responses += 1
        
        logger.info(f"Response submitted for: {survey.title}")
        
        return response
    
    def _validate_answers(
        self,
        survey: Survey,
        answers: Dict[str, Any],
    ) -> List[str]:
        """Validate response answers."""
        errors: List[str] = []
        
        for question in survey.questions:
            value = answers.get(question.id)
            
            if question.required and (value is None or value == ""):
                errors.append(f"Question '{question.text}' is required")
        
        return errors
    
    async def get_response(
        self,
        response_id: str,
    ) -> Optional[SurveyResponse]:
        """Get response."""
        return await self._responses.get(response_id)
    
    async def get_responses(
        self,
        survey_id: str,
        status: Optional[ResponseStatus] = None,
    ) -> List[SurveyResponse]:
        """Get responses."""
        return await self._responses.query(survey_id, status)
    
    # Analytics
    async def get_analytics(
        self,
        survey_id: str,
    ) -> SurveyAnalytics:
        """Get survey analytics."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            raise SurveyNotFoundError(f"Survey not found: {survey_id}")
        
        responses = await self.get_responses(survey_id)
        
        complete = [r for r in responses if r.status == ResponseStatus.COMPLETE]
        partial = [r for r in responses if r.status == ResponseStatus.PARTIAL]
        
        analytics = SurveyAnalytics(
            survey_id=survey_id,
            total_responses=len(responses),
            complete_responses=len(complete),
            partial_responses=len(partial),
            completion_rate=len(complete) / len(responses) if responses else 0.0,
            average_duration=statistics.mean([r.duration_seconds for r in complete]) if complete else 0.0,
        )
        
        # Question analytics
        for question in survey.questions:
            q_analytics = self._analyze_question(question, complete)
            analytics.questions.append(q_analytics)
        
        # Response trend (by date)
        for response in responses:
            date_key = response.started_at.strftime("%Y-%m-%d")
            analytics.response_trend[date_key] = analytics.response_trend.get(date_key, 0) + 1
        
        return analytics
    
    def _analyze_question(
        self,
        question: Question,
        responses: List[SurveyResponse],
    ) -> QuestionAnalytics:
        """Analyze question responses."""
        analytics = QuestionAnalytics(
            question_id=question.id,
            question_text=question.text,
            question_type=question.type,
        )
        
        values = []
        for response in responses:
            value = response.answers.get(question.id)
            if value is not None:
                values.append(value)
        
        analytics.response_count = len(values)
        analytics.skip_count = len(responses) - len(values)
        
        if not values:
            return analytics
        
        # Numeric analysis for rating/NPS/slider
        if question.type in (QuestionType.RATING, QuestionType.NPS, QuestionType.SLIDER, QuestionType.NUMBER):
            numeric_values = [float(v) for v in values if v is not None]
            if numeric_values:
                analytics.average = statistics.mean(numeric_values)
                analytics.median = statistics.median(numeric_values)
                if len(numeric_values) > 1:
                    analytics.std_dev = statistics.stdev(numeric_values)
                analytics.min_value = min(numeric_values)
                analytics.max_value = max(numeric_values)
                
                # NPS calculation
                if question.type == QuestionType.NPS:
                    promoters = len([v for v in numeric_values if v >= 9])
                    detractors = len([v for v in numeric_values if v <= 6])
                    total = len(numeric_values)
                    analytics.nps_score = ((promoters - detractors) / total) * 100 if total > 0 else 0
        
        # Distribution for choice questions
        if question.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE, QuestionType.RATING, QuestionType.NPS, QuestionType.LIKERT):
            counter = Counter()
            for value in values:
                if isinstance(value, list):
                    for v in value:
                        counter[str(v)] += 1
                else:
                    counter[str(value)] += 1
            analytics.distribution = dict(counter)
        
        # Text responses
        if question.type in (QuestionType.TEXT, QuestionType.TEXTAREA):
            analytics.text_responses = [str(v) for v in values if v]
        
        return analytics
    
    async def export_responses(
        self,
        survey_id: str,
        format: str = "json",
    ) -> str:
        """Export responses."""
        survey = await self._surveys.get(survey_id)
        if not survey:
            return ""
        
        responses = await self.get_responses(survey_id)
        
        if format == "json":
            data = []
            for r in responses:
                row = {
                    "response_id": r.id,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "duration_seconds": r.duration_seconds,
                }
                row.update(r.answers)
                data.append(row)
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            if not responses:
                return ""
            
            # Headers: question texts
            headers = ["response_id", "completed_at", "duration_seconds"]
            question_ids = [q.id for q in survey.questions]
            headers.extend([q.text for q in survey.questions])
            
            lines = [",".join(f'"{h}"' for h in headers)]
            
            for r in responses:
                row = [
                    r.id,
                    r.completed_at.isoformat() if r.completed_at else "",
                    str(r.duration_seconds),
                ]
                for q_id in question_ids:
                    value = r.answers.get(q_id, "")
                    row.append(f'"{value}"')
                lines.append(",".join(row))
            
            return "\n".join(lines)
        
        return ""
    
    def get_stats(self) -> SurveyStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_survey_engine() -> SurveyEngine:
    """Create survey engine."""
    return SurveyEngine()


def create_survey(
    title: str,
    **kwargs,
) -> Survey:
    """Create survey."""
    return Survey(title=title, **kwargs)


def create_question(
    text: str,
    type: QuestionType = QuestionType.TEXT,
    **kwargs,
) -> Question:
    """Create question."""
    return Question(text=text, type=type, **kwargs)


__all__ = [
    # Exceptions
    "SurveyError",
    "SurveyNotFoundError",
    # Enums
    "QuestionType",
    "SurveyStatus",
    "ResponseStatus",
    # Data classes
    "QuestionOption",
    "Question",
    "Survey",
    "Answer",
    "SurveyResponse",
    "QuestionAnalytics",
    "SurveyAnalytics",
    "SurveyStats",
    # Stores
    "SurveyStore",
    "InMemorySurveyStore",
    "ResponseStore",
    "InMemoryResponseStore",
    # Engine
    "SurveyEngine",
    # Factory functions
    "create_survey_engine",
    "create_survey",
    "create_question",
]
