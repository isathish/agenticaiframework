---
title: Compliance & Governance
description: Enterprise compliance, audit trails, policy enforcement, and data governance for AI systems
tags:
  - compliance
  - governance
  - audit
  - policy
  - data-masking
---

# 🏛️ Compliance & Governance

<div class="annotate" markdown>

**Enterprise compliance, audit trails, and data governance**

Ensure regulatory compliance with comprehensive audit logging, policy enforcement, and data masking across **400+ modules**

</div>

!!! success "Enterprise Compliance"
    Part of **237 enterprise modules** with **18 compliance & audit features** including PII detection, GDPR tools, and tamper-evident logging. See [Enterprise Documentation](enterprise.md).

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-clipboard-check:{ .lg } **Audit Trails**
    
    Tamper-evident logging
    
    [:octicons-arrow-right-24: Learn More](#audit-trail-manager)

-   :material-shield-lock:{ .lg } **Policy Enforcement**
    
    Rule-based access control
    
    [:octicons-arrow-right-24: Configure](#policy-engine)

-   :material-eye-off:{ .lg } **Data Masking**
    
    PII detection and masking
    
    [:octicons-arrow-right-24: Protect](#data-masking-engine)

-   :material-file-certificate:{ .lg } **Compliance Reports**
    
    Regulatory reporting
    
    [:octicons-arrow-right-24: Generate](#compliance-reporting)

</div>

## 📊 Overview

!!! abstract "Compliance Framework"
    
    The Compliance module provides **10 enterprise governance modules** including tamper-evident audit trails, configurable policy enforcement, and intelligent data masking for PII protection.

### Architecture

```mermaid
graph TB
    subgraph "Application Layer"
        AGENT[Agent Operations]
        API[API Requests]
        DATA[Data Access]
    end
    
    subgraph "Compliance Layer"
        AUDIT[AuditTrailManager<br/>📋 Audit]
        POLICY[PolicyEngine<br/>🛡️ Policy]
        MASK[DataMaskingEngine<br/>🔒 Masking]
    end
    
    subgraph "Storage"
        LOG[Audit Logs]
        RULES[Policy Rules]
        CONFIG[Masking Config]
    end
    
    subgraph "Decorators"
        D1[@audit_action]
        D2[@enforce_policy]
        D3[@mask_output]
    end
    
    AGENT & API & DATA --> D1 & D2 & D3
    D1 --> AUDIT --> LOG
    D2 --> POLICY --> RULES
    D3 --> MASK --> CONFIG
    
    style AUDIT fill:#e3f2fd,stroke:#1976d2
    style POLICY fill:#fff3e0,stroke:#f57c00
    style MASK fill:#fce4ec,stroke:#c2185b
```

---

## 📋 Audit Trail Manager

The `AuditTrailManager` provides tamper-evident logging with hash chain integrity.

### Basic Usage

```python
from agenticaiframework.compliance import (
    AuditTrailManager,
    audit_trail,
    AuditEvent,
    AuditEventType,
    AuditSeverity
)

# Use global instance
audit = AuditTrailManager()

# Log an event
audit.log_event(
    event_type=AuditEventType.DATA_ACCESS,
    severity=AuditSeverity.INFO,
    actor="user@example.com",
    action="read_customer_data",
    resource="customers/12345",
    details={"fields": ["name", "email"]}
)
```

### Event Types

```python
from agenticaiframework.compliance import AuditEventType

# Available event types
AuditEventType.AUTHENTICATION    # Login/logout events
AuditEventType.AUTHORIZATION     # Access control decisions
AuditEventType.DATA_ACCESS       # Data read operations
AuditEventType.DATA_MODIFICATION # Data write operations
AuditEventType.DATA_DELETION     # Data removal
AuditEventType.CONFIGURATION     # Config changes
AuditEventType.SYSTEM            # System events
AuditEventType.SECURITY          # Security events
AuditEventType.COMPLIANCE        # Compliance checks
AuditEventType.AGENT_ACTION      # Agent operations
```

### Severity Levels

```python
from agenticaiframework.compliance import AuditSeverity

AuditSeverity.DEBUG      # Detailed debugging
AuditSeverity.INFO       # Normal operations
AuditSeverity.WARNING    # Potential issues
AuditSeverity.ERROR      # Errors
AuditSeverity.CRITICAL   # Critical events
```

### Using the Decorator

```python
from agenticaiframework.compliance import audit_action

@audit_action(
    event_type=AuditEventType.DATA_ACCESS,
    severity=AuditSeverity.INFO,
    resource_param="customer_id"
)
def get_customer_data(customer_id: str, fields: list):
    """Fetch customer data - automatically audited."""
    return database.get_customer(customer_id, fields)

# Call is automatically logged
data = get_customer_data("12345", ["name", "email"])
```

### Query Audit Logs

```python
import logging

logger = logging.getLogger(__name__)

# Query recent events
events = audit.query_events(
    event_type=AuditEventType.DATA_ACCESS,
    actor="user@example.com",
    start_time="2024-01-01T00:00:00Z",
    end_time="2024-01-31T23:59:59Z",
    limit=100
)

# Verify integrity
integrity_check = audit.verify_integrity()
if not integrity_check.valid:
    logger.info(f"Integrity violation at event {integrity_check.failed_at}")
```

### Hash Chain Integrity

```python
import logging

logger = logging.getLogger(__name__)

# The audit trail uses hash chaining
# Each event includes hash of previous event

event1 = audit.log_event(...)  # hash: abc123
event2 = audit.log_event(...)  # prev_hash: abc123, hash: def456
event3 = audit.log_event(...)  # prev_hash: def456, hash: ghi789

# Verify chain integrity
result = audit.verify_chain()
logger.info(f"Chain valid: {result.valid}")
logger.info(f"Events verified: {result.event_count}")
```

---

## 🛡️ Policy Engine

The `PolicyEngine` enforces configurable access control and operation policies.

### Basic Usage

```python
from agenticaiframework.compliance import (
    PolicyEngine,
    policy_engine,
    Policy,
    PolicyType
)

# Create policy engine
engine = PolicyEngine(audit_trail)

# Define a policy
data_access_policy = Policy(
    name="customer_data_access",
    type=PolicyType.ACCESS_CONTROL,
    description="Controls access to customer data",
    rules=[
        {
            "condition": "role in ['admin', 'support']",
            "action": "allow",
            "resource_pattern": "customers/*"
        },
        {
            "condition": "role == 'analyst'",
            "action": "allow",
            "resource_pattern": "customers/*/analytics"
        },
        {
            "condition": "default",
            "action": "deny"
        }
    ]
)

# Register policy
engine.register_policy(data_access_policy)
```

### Policy Types

```python
from agenticaiframework.compliance import PolicyType

PolicyType.ACCESS_CONTROL    # Resource access
PolicyType.RATE_LIMIT       # Request rate limits
PolicyType.DATA_HANDLING    # Data processing rules
PolicyType.CONTENT          # Content restrictions
PolicyType.OPERATION        # Allowed operations
PolicyType.COMPLIANCE       # Regulatory compliance
```

### Using the Decorator

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.compliance import enforce_policy

@enforce_policy(
    policy_name="customer_data_access",
    resource_param="customer_id"
)
def access_customer_data(customer_id: str, context: dict):
    """Access customer data - policy enforced."""
    return database.get_customer(customer_id)

# Policy check happens before execution
try:
    data = access_customer_data(
        "12345", 
        context={"role": "analyst", "user": "alice@example.com"}
    )
except PolicyViolationError as e:
    logger.info(f"Access denied: {e.policy_name}")
```

### Evaluate Policies

```python
import logging

logger = logging.getLogger(__name__)

# Manual policy evaluation
result = engine.evaluate(
    policy_name="customer_data_access",
    context={
        "role": "analyst",
        "resource": "customers/12345/analytics",
        "action": "read"
    }
)

if result.allowed:
    logger.info("Access granted")
else:
    logger.info(f"Access denied: {result.reason}")
```

### Policy Conditions

```python
# Complex conditions with pattern matching
policy = Policy(
    name="sensitive_operations",
    type=PolicyType.OPERATION,
    rules=[
        {
            # Time-based restrictions
            "condition": "hour >= 9 and hour <= 17",
            "action": "allow",
            "operations": ["bulk_export"]
        },
        {
            # Role + environment
            "condition": "role == 'admin' and environment == 'production'",
            "action": "require_approval",
            "operations": ["delete_data"]
        },
        {
            # IP-based restrictions
            "condition": "ip_address matches '10.0.*.*'",
            "action": "allow",
            "operations": ["internal_api"]
        }
    ]
)
```

---

## 🔒 Data Masking Engine

The `DataMaskingEngine` detects and masks sensitive data including PII.

### Basic Usage

```python
from agenticaiframework.compliance import (
    DataMaskingEngine,
    data_masking,
    MaskingRule,
    MaskingType
)

# Create masking engine
masker = DataMaskingEngine(audit_trail)

# Mask data
masked = masker.mask_text(
    "Contact John Doe at john.doe@email.com or 555-123-4567"
)
# Result: "Contact [NAME] at [EMAIL] or [PHONE]"
```

### Masking Types

```python
from agenticaiframework.compliance import MaskingType

MaskingType.REDACT         # Replace with [TYPE]
MaskingType.PARTIAL        # Show partial (e.g., j***@e***.com)
MaskingType.HASH           # Replace with hash
MaskingType.TOKENIZE       # Replace with token
MaskingType.ENCRYPT        # Encrypt value
MaskingType.GENERALIZE     # Generalize (e.g., 25 → 20-30)
```

### Custom Masking Rules

```python
# Define custom rules
email_rule = MaskingRule(
    name="email",
    pattern=r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    masking_type=MaskingType.PARTIAL,
    partial_show=2  # Show first 2 chars
)

phone_rule = MaskingRule(
    name="phone",
    pattern=r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    masking_type=MaskingType.REDACT,
    replacement="[PHONE]"
)

ssn_rule = MaskingRule(
    name="ssn",
    pattern=r'\b\d{3}-\d{2}-\d{4}\b',
    masking_type=MaskingType.HASH
)

# Register rules
masker.add_rule(email_rule)
masker.add_rule(phone_rule)
masker.add_rule(ssn_rule)
```

### Using the Decorator

```python
from agenticaiframework.compliance import mask_output

@mask_output(
    fields=["email", "phone", "ssn"],
    masking_type=MaskingType.REDACT
)
def get_user_profile(user_id: str) -> dict:
    """Get user profile - sensitive fields automatically masked."""
    return database.get_user(user_id)

# Returned data has masked fields
profile = get_user_profile("user-123")
# {"name": "John", "email": "[EMAIL]", "phone": "[PHONE]"}
```

### Mask Structured Data

```python
# Mask dictionary/JSON data
user_data = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "555-123-4567",
    "ssn": "123-45-6789",
    "address": {
        "street": "123 Main St",
        "city": "New York"
    }
}

masked_data = masker.mask_dict(
    user_data,
    sensitive_fields=["email", "phone", "ssn"]
)
```

### PII Detection

```python
import logging

logger = logging.getLogger(__name__)

# Detect PII without masking
pii_found = masker.detect_pii(text)
for pii in pii_found:
    logger.info(f"Found {pii.type} at position {pii.start}-{pii.end}")
    logger.info(f"Value: {pii.value}")
    logger.info(f"Confidence: {pii.confidence}")
```

---

## 📊 Compliance Reporting

Generate compliance reports for regulatory requirements.

### Generate Report

```python
from agenticaiframework.compliance import audit_trail

# Generate compliance report
report = audit_trail.generate_report(
    report_type="data_access",
    start_date="2024-01-01",
    end_date="2024-01-31",
    format="pdf"
)

# Export report
report.save("/reports/january_2024_access.pdf")
```

### Report Types

```python
# Available report types
report_types = [
    "data_access",      # Data access summary
    "policy_violations", # Policy violation report
    "user_activity",    # User activity report
    "security_events",  # Security event summary
    "pii_exposure",     # PII handling report
    "compliance_summary" # Overall compliance status
]
```

### Scheduled Reports

```python
# Schedule recurring reports
audit_trail.schedule_report(
    report_type="compliance_summary",
    schedule="weekly",
    recipients=["compliance@company.com"],
    format="pdf"
)
```

---

## 🎯 Complete Example

```python
from agenticaiframework import Agent
from agenticaiframework.compliance import (
    audit_trail,
    policy_engine,
    data_masking,
    audit_action,
    enforce_policy,
    mask_output,
    AuditEventType,
    AuditSeverity,
    Policy,
    PolicyType,
    MaskingType
)

# Configure compliance
# 1. Set up audit trail
audit_trail.configure(
    storage="database",
    connection_string="postgresql://...",
    retention_days=365
)

# 2. Define policies
customer_policy = Policy(
    name="customer_data_access",
    type=PolicyType.ACCESS_CONTROL,
    rules=[
        {"condition": "role == 'admin'", "action": "allow"},
        {"condition": "role == 'support'", "action": "allow", "fields": ["name", "email"]},
        {"condition": "default", "action": "deny"}
    ]
)
policy_engine.register_policy(customer_policy)

# 3. Configure data masking
data_masking.configure_pii_detection(
    detect_emails=True,
    detect_phones=True,
    detect_ssn=True,
    detect_credit_cards=True
)

# Compliant service implementation
class CustomerService:
    
    @audit_action(
        event_type=AuditEventType.DATA_ACCESS,
        severity=AuditSeverity.INFO
    )
    @enforce_policy(policy_name="customer_data_access")
    @mask_output(masking_type=MaskingType.PARTIAL)
    def get_customer(self, customer_id: str, context: dict) -> dict:
        """Get customer data with full compliance."""
        return self.database.get_customer(customer_id)
    
    @audit_action(
        event_type=AuditEventType.DATA_MODIFICATION,
        severity=AuditSeverity.WARNING
    )
    @enforce_policy(policy_name="customer_data_access")
    def update_customer(self, customer_id: str, data: dict, context: dict) -> bool:
        """Update customer with audit trail."""
        # Mask sensitive data in logs
        safe_data = data_masking.mask_dict(data)
        audit_trail.log_event(
            event_type=AuditEventType.DATA_MODIFICATION,
            details={"customer_id": customer_id, "changes": safe_data}
        )
        return self.database.update_customer(customer_id, data)

# Usage
service = CustomerService()

# This call is:
# - Audited (who, what, when)
# - Policy checked (access control)
# - Output masked (PII protection)
customer = service.get_customer(
    "12345",
    context={"role": "support", "user": "alice@example.com"}
)
```

---

## 📋 Compliance Standards Support

| Standard | Features |
|----------|----------|
| **GDPR** | Data masking, consent tracking, right to erasure |
| **HIPAA** | PHI protection, access logging, encryption |
| **SOC 2** | Audit trails, access controls, monitoring |
| **PCI DSS** | Card data masking, access logging |
| **SOX** | Financial data controls, audit trails |

---

## 🎯 Best Practices

!!! tip "Compliance Guidelines"
    
    1. **Log everything** - Comprehensive audit trails are essential
    2. **Mask by default** - Apply PII masking to all outputs
    3. **Enforce policies** - Use decorators for consistent enforcement
    4. **Verify integrity** - Regularly check audit trail integrity
    5. **Retain appropriately** - Follow retention policies for your industry

!!! warning "Security Considerations"
    
    - Store audit logs in tamper-evident storage
    - Encrypt sensitive audit data
    - Implement proper access controls for audit logs
    - Regularly backup compliance data
    - Test policy rules before production deployment

---

## 📚 Related Documentation

- [Security](security.md) - Security module
- [Monitoring](monitoring.md) - System monitoring
- [Deployment](deployment.md) - Production deployment
- [Best Practices](best-practices.md) - Enterprise guidelines
