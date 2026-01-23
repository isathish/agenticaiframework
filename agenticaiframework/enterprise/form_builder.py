"""
Enterprise Form Builder Module.

Dynamic forms, validation rules, form submissions,
field types, and form management.

Example:
    # Create form builder
    forms = create_form_builder()
    
    # Create form
    form = await forms.create_form(
        name="Contact Us",
        fields=[
            {"name": "name", "type": "text", "required": True},
            {"name": "email", "type": "email", "required": True},
            {"name": "message", "type": "textarea", "required": True},
        ],
    )
    
    # Submit form
    submission = await forms.submit(
        form_id=form.id,
        data={"name": "John", "email": "john@example.com", "message": "Hello!"},
    )
    
    # Get submissions
    submissions = await forms.get_submissions(form.id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class FormError(Exception):
    """Form error."""
    pass


class FormNotFoundError(FormError):
    """Form not found."""
    pass


class ValidationError(FormError):
    """Validation error."""
    
    def __init__(self, errors: Dict[str, List[str]]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")


class FieldType(str, Enum):
    """Field type."""
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    NUMBER = "number"
    DECIMAL = "decimal"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    SELECT = "select"
    MULTISELECT = "multiselect"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TOGGLE = "toggle"
    FILE = "file"
    IMAGE = "image"
    HIDDEN = "hidden"
    PASSWORD = "password"
    RATING = "rating"
    SIGNATURE = "signature"
    RICH_TEXT = "rich_text"


class FormStatus(str, Enum):
    """Form status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SubmissionStatus(str, Enum):
    """Submission status."""
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ValidationRule:
    """Validation rule."""
    type: str = ""  # required, min, max, pattern, etc.
    value: Any = None
    message: str = ""


@dataclass
class FieldOption:
    """Field option for select/radio/checkbox."""
    value: str = ""
    label: str = ""
    disabled: bool = False


@dataclass
class FormField:
    """Form field definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: FieldType = FieldType.TEXT
    label: str = ""
    placeholder: str = ""
    help_text: str = ""
    default_value: Any = None
    required: bool = False
    disabled: bool = False
    hidden: bool = False
    readonly: bool = False
    options: List[FieldOption] = field(default_factory=list)
    validation: List[ValidationRule] = field(default_factory=list)
    conditional: Optional[Dict[str, Any]] = None
    order: int = 0
    width: str = "full"  # full, half, third
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FormSection:
    """Form section/page."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    fields: List[FormField] = field(default_factory=list)
    order: int = 0


@dataclass
class Form:
    """Form definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: FormStatus = FormStatus.DRAFT
    sections: List[FormSection] = field(default_factory=list)
    fields: List[FormField] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    submit_button_text: str = "Submit"
    success_message: str = "Thank you for your submission!"
    redirect_url: str = ""
    notify_emails: List[str] = field(default_factory=list)
    max_submissions: Optional[int] = None
    submission_count: int = 0
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FormSubmission:
    """Form submission."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    form_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    status: SubmissionStatus = SubmissionStatus.PENDING
    ip_address: str = ""
    user_agent: str = ""
    user_id: Optional[str] = None
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FormStats:
    """Form statistics."""
    total_forms: int = 0
    published_forms: int = 0
    total_submissions: int = 0


# Form store
class FormStore(ABC):
    """Form storage."""
    
    @abstractmethod
    async def save(self, form: Form) -> None:
        pass
    
    @abstractmethod
    async def get(self, form_id: str) -> Optional[Form]:
        pass
    
    @abstractmethod
    async def list(self, status: Optional[FormStatus] = None) -> List[Form]:
        pass
    
    @abstractmethod
    async def delete(self, form_id: str) -> bool:
        pass


class InMemoryFormStore(FormStore):
    """In-memory form store."""
    
    def __init__(self):
        self._forms: Dict[str, Form] = {}
    
    async def save(self, form: Form) -> None:
        form.updated_at = datetime.utcnow()
        self._forms[form.id] = form
    
    async def get(self, form_id: str) -> Optional[Form]:
        return self._forms.get(form_id)
    
    async def list(self, status: Optional[FormStatus] = None) -> List[Form]:
        forms = list(self._forms.values())
        
        if status:
            forms = [f for f in forms if f.status == status]
        
        return sorted(forms, key=lambda f: f.created_at, reverse=True)
    
    async def delete(self, form_id: str) -> bool:
        return self._forms.pop(form_id, None) is not None


# Submission store
class SubmissionStore(ABC):
    """Submission storage."""
    
    @abstractmethod
    async def save(self, submission: FormSubmission) -> None:
        pass
    
    @abstractmethod
    async def get(self, submission_id: str) -> Optional[FormSubmission]:
        pass
    
    @abstractmethod
    async def query(
        self,
        form_id: str,
        status: Optional[SubmissionStatus] = None,
    ) -> List[FormSubmission]:
        pass


class InMemorySubmissionStore(SubmissionStore):
    """In-memory submission store."""
    
    def __init__(self):
        self._submissions: Dict[str, FormSubmission] = {}
    
    async def save(self, submission: FormSubmission) -> None:
        self._submissions[submission.id] = submission
    
    async def get(self, submission_id: str) -> Optional[FormSubmission]:
        return self._submissions.get(submission_id)
    
    async def query(
        self,
        form_id: str,
        status: Optional[SubmissionStatus] = None,
    ) -> List[FormSubmission]:
        results = [
            s for s in self._submissions.values()
            if s.form_id == form_id
        ]
        
        if status:
            results = [s for s in results if s.status == status]
        
        return sorted(results, key=lambda s: s.created_at, reverse=True)


# Validator
class FieldValidator:
    """Field validator."""
    
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    URL_PATTERN = re.compile(r'^https?://[^\s/$.?#].[^\s]*$')
    PHONE_PATTERN = re.compile(r'^[\d\s\-\+\(\)]{7,20}$')
    
    @classmethod
    def validate(
        cls,
        field: FormField,
        value: Any,
    ) -> List[str]:
        """Validate field value."""
        errors: List[str] = []
        
        # Required check
        if field.required:
            if value is None or value == "" or (isinstance(value, list) and len(value) == 0):
                errors.append(f"{field.label or field.name} is required")
                return errors
        
        if value is None or value == "":
            return errors
        
        # Type validation
        if field.type == FieldType.EMAIL:
            if not cls.EMAIL_PATTERN.match(str(value)):
                errors.append("Invalid email address")
        
        elif field.type == FieldType.URL:
            if not cls.URL_PATTERN.match(str(value)):
                errors.append("Invalid URL")
        
        elif field.type == FieldType.PHONE:
            if not cls.PHONE_PATTERN.match(str(value)):
                errors.append("Invalid phone number")
        
        elif field.type == FieldType.NUMBER:
            try:
                int(value)
            except (ValueError, TypeError):
                errors.append("Must be a whole number")
        
        elif field.type == FieldType.DECIMAL:
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append("Must be a number")
        
        elif field.type == FieldType.DATE:
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError:
                errors.append("Invalid date format (YYYY-MM-DD)")
        
        # Custom validation rules
        for rule in field.validation:
            error = cls._validate_rule(field, value, rule)
            if error:
                errors.append(error)
        
        return errors
    
    @classmethod
    def _validate_rule(
        cls,
        field: FormField,
        value: Any,
        rule: ValidationRule,
    ) -> Optional[str]:
        """Validate against rule."""
        if rule.type == "min":
            if field.type in (FieldType.NUMBER, FieldType.DECIMAL):
                if float(value) < rule.value:
                    return rule.message or f"Minimum value is {rule.value}"
            else:
                if len(str(value)) < rule.value:
                    return rule.message or f"Minimum length is {rule.value}"
        
        elif rule.type == "max":
            if field.type in (FieldType.NUMBER, FieldType.DECIMAL):
                if float(value) > rule.value:
                    return rule.message or f"Maximum value is {rule.value}"
            else:
                if len(str(value)) > rule.value:
                    return rule.message or f"Maximum length is {rule.value}"
        
        elif rule.type == "pattern":
            if not re.match(rule.value, str(value)):
                return rule.message or "Invalid format"
        
        elif rule.type == "options":
            allowed = rule.value if isinstance(rule.value, list) else [rule.value]
            if value not in allowed:
                return rule.message or "Invalid option"
        
        return None


# Form builder
class FormBuilder:
    """Form builder."""
    
    def __init__(
        self,
        form_store: Optional[FormStore] = None,
        submission_store: Optional[SubmissionStore] = None,
    ):
        self._forms = form_store or InMemoryFormStore()
        self._submissions = submission_store or InMemorySubmissionStore()
        self._stats = FormStats()
    
    async def create_form(
        self,
        name: str,
        fields: List[Dict[str, Any]] = None,
        description: str = "",
        created_by: str = "",
        **kwargs,
    ) -> Form:
        """Create form."""
        form = Form(
            name=name,
            description=description,
            created_by=created_by,
            **kwargs,
        )
        
        # Add fields
        if fields:
            for i, field_def in enumerate(fields):
                form.fields.append(self._create_field(field_def, i))
        
        await self._forms.save(form)
        self._stats.total_forms += 1
        
        logger.info(f"Form created: {name}")
        
        return form
    
    def _create_field(
        self,
        field_def: Dict[str, Any],
        order: int = 0,
    ) -> FormField:
        """Create field from definition."""
        field = FormField(
            name=field_def.get("name", ""),
            type=FieldType(field_def.get("type", "text")),
            label=field_def.get("label", field_def.get("name", "")),
            placeholder=field_def.get("placeholder", ""),
            help_text=field_def.get("help_text", ""),
            default_value=field_def.get("default"),
            required=field_def.get("required", False),
            order=order,
        )
        
        # Add options
        if "options" in field_def:
            for opt in field_def["options"]:
                if isinstance(opt, dict):
                    field.options.append(FieldOption(**opt))
                else:
                    field.options.append(FieldOption(value=str(opt), label=str(opt)))
        
        # Add validation
        if "validation" in field_def:
            for rule in field_def["validation"]:
                field.validation.append(ValidationRule(**rule))
        
        return field
    
    async def get_form(self, form_id: str) -> Optional[Form]:
        """Get form."""
        return await self._forms.get(form_id)
    
    async def update_form(
        self,
        form_id: str,
        **updates,
    ) -> Optional[Form]:
        """Update form."""
        form = await self._forms.get(form_id)
        if not form:
            return None
        
        for key, value in updates.items():
            if hasattr(form, key):
                setattr(form, key, value)
        
        await self._forms.save(form)
        
        return form
    
    async def add_field(
        self,
        form_id: str,
        field_def: Dict[str, Any],
    ) -> Optional[Form]:
        """Add field to form."""
        form = await self._forms.get(form_id)
        if not form:
            return None
        
        order = len(form.fields)
        form.fields.append(self._create_field(field_def, order))
        
        await self._forms.save(form)
        
        return form
    
    async def remove_field(
        self,
        form_id: str,
        field_name: str,
    ) -> Optional[Form]:
        """Remove field from form."""
        form = await self._forms.get(form_id)
        if not form:
            return None
        
        form.fields = [f for f in form.fields if f.name != field_name]
        
        await self._forms.save(form)
        
        return form
    
    async def publish(self, form_id: str) -> Optional[Form]:
        """Publish form."""
        form = await self._forms.get(form_id)
        if not form:
            return None
        
        form.status = FormStatus.PUBLISHED
        
        await self._forms.save(form)
        self._stats.published_forms += 1
        
        logger.info(f"Form published: {form.name}")
        
        return form
    
    async def close(self, form_id: str) -> Optional[Form]:
        """Close form."""
        form = await self._forms.get(form_id)
        if not form:
            return None
        
        form.status = FormStatus.CLOSED
        
        await self._forms.save(form)
        
        return form
    
    async def list_forms(
        self,
        status: Optional[FormStatus] = None,
    ) -> List[Form]:
        """List forms."""
        return await self._forms.list(status)
    
    # Submissions
    async def submit(
        self,
        form_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> FormSubmission:
        """Submit form."""
        form = await self._forms.get(form_id)
        if not form:
            raise FormNotFoundError(f"Form not found: {form_id}")
        
        if form.status != FormStatus.PUBLISHED:
            raise FormError("Form is not accepting submissions")
        
        # Check limits
        if form.max_submissions and form.submission_count >= form.max_submissions:
            raise FormError("Form has reached maximum submissions")
        
        # Check dates
        now = datetime.utcnow()
        if form.opens_at and now < form.opens_at:
            raise FormError("Form is not open yet")
        if form.closes_at and now > form.closes_at:
            raise FormError("Form is closed")
        
        # Validate
        errors = await self.validate(form_id, data)
        if errors:
            raise ValidationError(errors)
        
        # Create submission
        submission = FormSubmission(
            form_id=form_id,
            data=data,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        await self._submissions.save(submission)
        
        # Update count
        form.submission_count += 1
        await self._forms.save(form)
        
        self._stats.total_submissions += 1
        
        logger.info(f"Form submitted: {form.name}")
        
        return submission
    
    async def validate(
        self,
        form_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """Validate form data."""
        form = await self._forms.get(form_id)
        if not form:
            return {"_form": ["Form not found"]}
        
        errors: Dict[str, List[str]] = {}
        
        for field in form.fields:
            value = data.get(field.name)
            field_errors = FieldValidator.validate(field, value)
            
            if field_errors:
                errors[field.name] = field_errors
        
        return errors
    
    async def get_submission(
        self,
        submission_id: str,
    ) -> Optional[FormSubmission]:
        """Get submission."""
        return await self._submissions.get(submission_id)
    
    async def get_submissions(
        self,
        form_id: str,
        status: Optional[SubmissionStatus] = None,
    ) -> List[FormSubmission]:
        """Get submissions."""
        return await self._submissions.query(form_id, status)
    
    async def update_submission_status(
        self,
        submission_id: str,
        status: SubmissionStatus,
        notes: str = "",
    ) -> Optional[FormSubmission]:
        """Update submission status."""
        submission = await self._submissions.get(submission_id)
        if not submission:
            return None
        
        submission.status = status
        if notes:
            submission.notes = notes
        
        await self._submissions.save(submission)
        
        return submission
    
    async def export_submissions(
        self,
        form_id: str,
        format: str = "json",
    ) -> str:
        """Export submissions."""
        submissions = await self.get_submissions(form_id)
        
        if format == "json":
            return json.dumps(
                [{"data": s.data, "created_at": s.created_at.isoformat()} for s in submissions],
                indent=2,
            )
        elif format == "csv":
            if not submissions:
                return ""
            
            # Get all field names
            fields = set()
            for s in submissions:
                fields.update(s.data.keys())
            fields = sorted(fields)
            
            lines = [",".join(fields)]
            for s in submissions:
                row = [str(s.data.get(f, "")) for f in fields]
                lines.append(",".join(row))
            
            return "\n".join(lines)
        
        return ""
    
    def get_stats(self) -> FormStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_form_builder() -> FormBuilder:
    """Create form builder."""
    return FormBuilder()


def create_form(
    name: str,
    **kwargs,
) -> Form:
    """Create form."""
    return Form(name=name, **kwargs)


def create_field(
    name: str,
    type: FieldType = FieldType.TEXT,
    **kwargs,
) -> FormField:
    """Create field."""
    return FormField(name=name, type=type, **kwargs)


__all__ = [
    # Exceptions
    "FormError",
    "FormNotFoundError",
    "ValidationError",
    # Enums
    "FieldType",
    "FormStatus",
    "SubmissionStatus",
    # Data classes
    "ValidationRule",
    "FieldOption",
    "FormField",
    "FormSection",
    "Form",
    "FormSubmission",
    "FormStats",
    # Stores
    "FormStore",
    "InMemoryFormStore",
    "SubmissionStore",
    "InMemorySubmissionStore",
    # Validator
    "FieldValidator",
    # Builder
    "FormBuilder",
    # Factory functions
    "create_form_builder",
    "create_form",
    "create_field",
]
