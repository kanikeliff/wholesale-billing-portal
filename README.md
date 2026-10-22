# AI-Integrated Wholesale Billing Portal

## Overview

The AI-Integrated Wholesale Billing Portal is a web application designed to process Bill of Lading (BOL) documents, extract structured billing information, support billing review, and integrate with an external decision-support service.

The system follows a human-in-the-loop workflow:

```text
BOL Upload
    ↓
OCR / Field Extraction
    ↓
Normalized Billing Record
    ↓
Validation
    ↓
Team A Recommendation
    ↓
Human Review / Correction
    ↓
Final Billing Decision
```

The portal does not allow external services to silently overwrite billing data. Team B owns the application workflow and correction process, while Team A owns business-data evaluation and recommendation logic.

---

# Architecture

The project is divided into clear layers:

```text
wholesale-billing-portal/
│
├── backend/
│   ├── manage.py
│   │
│   ├── config/
│   │
│   ├── apps/
│   │   ├── billing/
│   │   ├── documents/
│   │   ├── review/
│   │   └── workflow/
│   │
│   ├── core/
│   │   ├── enums/
│   │   ├── exceptions/
│   │   ├── responses/
│   │   ├── events/
│   │   └── utils/
│   │
│   ├── domain/
│   │   ├── entities/
│   │   ├── repositories/
│   │   └── services/
│   │
│   ├── application/
│   │   ├── services/
│   │   ├── validators/
│   │   ├── commands/
│   │   └── facades/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   ├── ocr/
│   │   ├── team_a/
│   │   ├── storage/
│   │   └── mock/
│   │
│   ├── presentation/
│   │   └── api/
│   │
│   └── tests/
│
├── frontend/
├── contracts/
└── docs/
```

The backend currently uses:

- Python
- Django
- Django REST Framework
- PostgreSQL
- Django ORM and migrations
- REST-based Team A integration

---

# Team Responsibilities

## Team B

Team B owns the billing portal and application workflow.

### Backend and Workflow

Responsible for:

- billing-record APIs
- validation
- application state transitions
- Team A orchestration
- retries and external-service failure handling
- correction workflow
- frontend-facing status behavior
- final human-decision workflow
- feedback delivery

### Database and Data Pipeline

Responsible for:

- PostgreSQL schema
- Django models
- migrations
- repositories
- relationships and constraints
- recommendation history
- audit history
- transactional persistence

## Team A

Team A owns business-data evaluation.

Responsible for:

- terminal-log matching
- reference-data lookup
- carrier-code mapping
- E3 Stock ID mapping
- duplicate detection
- product comparison
- volume comparison
- recommendation logic
- recommendation confidence
- rationale
- exception indicators

Team A returns recommendation evidence but does not directly update billing records.

---

# Billing Record Fields

The current MVP uses the following BOL fields.

## BOL-Level Fields

- Contract # / Lifting #
- Origin
- Supplier
- Carrier
- Transaction Date
- Destination
- BOL #

## Line-Item Fields

- Product
- Net Gallons
- Gross Gallons
- E3 Stock ID

A billing record may contain multiple line items.

---

# Backend Setup

## 1. Clone the Repository

```bash
git clone https://github.com/kanikeliff/wholesale-billing-portal.git
cd wholesale-billing-portal
```

---

## 2. Create a Python Virtual Environment

From the repository root:

```bash
python3 -m venv .venv
```

Activate it:

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

---

## 3. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

If `requirements.txt` is not available or has not yet been finalized, install the required packages defined by the backend team before continuing.

---

# PostgreSQL Setup

The development backend uses PostgreSQL.

Example local configuration:

```text
Database: mirabito_dev
Host: localhost
Port: 5432
```

Set the environment variables before running Django.

Example:

```bash
export DB_NAME=mirabito_dev
export DB_USER=<your-postgresql-user>
export DB_HOST=localhost
export DB_PORT=5432
```

Database credentials should never be committed to Git.

If password-based authentication is required in your environment, configure it through an environment variable or local environment configuration.

---

# Django Setup

From the `backend/` directory:

```bash
python manage.py check
```

Apply migrations:

```bash
python manage.py migrate
```

Run the development server:

```bash
python manage.py runserver
```

By default, Django runs at:

```text
http://127.0.0.1:8000/
```

---

# Health Check

The backend exposes:

```http
GET /api/v1/health/
```

Example:

```bash
curl http://127.0.0.1:8000/api/v1/health/
```

Use this endpoint first when verifying that the backend is running correctly.

---

# Current Billing APIs

## Get Billing Record

```http
GET /api/v1/billing-records/<record_id>/
```

Example:

```bash
curl http://127.0.0.1:8000/api/v1/billing-records/rec_001/
```

---

## Validate Billing Record

```http
POST /api/v1/billing-records/<record_id>/validate/
```

Validation checks include:

- required billing fields
- field quality
- malformed values
- transaction dates
- line-item structure
- numeric gallon values
- negative gallon values
- OCR review flags

Possible validation outcomes include:

```text
NEEDS_REVIEW
RECOMMENDATION_PENDING
EXCEPTION
```

---

## Request Recommendation

```http
POST /api/v1/billing-records/<record_id>/evaluate/
```

This endpoint coordinates Team A recommendation evaluation.

Possible responses:

```text
200
Recommendation completed successfully.

202
Team A is temporarily unavailable.
The billing record remains RECOMMENDATION_PENDING.

404
Billing record does not exist.

409
The requested workflow transition is not valid.

502
A non-retryable Team A integration failure occurred.
```

The frontend should interact with Team B APIs rather than calling Team A directly.

---

# Billing Record Workflow

Current workflow states:

```text
UPLOADED
    ↓
OCR_PROCESSING
    ↓
OCR_COMPLETE
    ↓
NEEDS_REVIEW
    ↓
RECOMMENDATION_PENDING
    ↓
RECOMMENDATION_READY
    ↓
APPROVED / REJECTED / EXCEPTION
```

Not every record must pass through every state.

For example:

```text
OCR_COMPLETE
    ↓
RECOMMENDATION_PENDING
```

is valid if no manual OCR review is required.

Re-evaluation is also supported:

```text
RECOMMENDATION_READY
    ↓
RECOMMENDATION_PENDING
    ↓
RECOMMENDATION_READY
```

This is used when billing data changes and Team A must evaluate the updated record again.

---

# Team A Integration

Team A is accessed only through the backend.

Conceptually:

```text
Frontend
    ↓
Team B API
    ↓
RecommendationService
    ↓
Team A Adapter
    ↓
Team A HTTP Client
    ↓
Team A API
```

Team A authentication uses:

```text
X-API-Key
```

The API key must:

- come from environment configuration
- never be hardcoded
- never be exposed to the frontend
- never be committed to Git

---

# Team A Retry Behavior

The Team A client supports retries for temporary failures.

Retryable failures include:

```text
timeout
network failure
HTTP 5xx
HTTP 503
```

Non-retryable failures include:

```text
HTTP 400
HTTP 401
HTTP 422
```

Current retry strategy:

```text
initial request
    ↓
retry after 2 seconds
    ↓
retry after 4 seconds
    ↓
retry after 8 seconds
```

If all attempts fail with a retryable error:

```text
BillingRecord.status = RECOMMENDATION_PENDING
```

The billing record must not be lost or rolled back because Team A is temporarily unavailable.

---

# Persistence Rules

Recommendation responses must be stored as history rather than overwriting previous recommendations.

Expected repository behavior:

```text
Recommendation revision 1
Recommendation revision 2
Recommendation revision 3
...
```

Only one revision should be marked current.

Expected constraints:

```text
UNIQUE(billing_record, revision_number)
```

and only one current recommendation per billing record.

A successful evaluation should eventually persist:

```text
previous recommendation
    ↓
is_current = false

new recommendation
    ↓
inserted as new revision
    ↓
is_current = true

billing record
    ↓
RECOMMENDATION_READY
```

The recommendation revision and `RECOMMENDATION_READY` status update should be atomic.

---

# Important Transaction Rule

Do not call external services while holding a database transaction open.

Incorrect:

```text
BEGIN TRANSACTION

call Team A
wait
retry
wait

save recommendation

COMMIT
```

Correct:

```text
Transaction 1:
    update record → RECOMMENDATION_PENDING
COMMIT

Call Team A outside the transaction

Transaction 2:
    save recommendation revision
    update record → RECOMMENDATION_READY
COMMIT
```

External network calls must remain outside database transactions.

---

# Recommendation Repository Contract

The database implementation should provide behavior equivalent to:

```python
get_current(record_id)

list_history(record_id)

store_revision(
    record_id,
    recommendation_data,
)

store_revision_and_mark_ready(
    record_id,
    recommendation_data,
)
```

The billing-record repository should provide:

```python
get_by_id(record_id)

update_status(
    record_id,
    status,
)
```

Application services decide what should happen.

Repositories persist those decisions.

---

# Human Corrections

The portal follows a human-in-the-loop model.

A biller may correct extracted information.

Example:

```text
OCR extracted:
Gross Gallons = 7000

Biller correction:
Gross Gallons = 6995
```

The system should preserve both pieces of information:

```text
OCR evidence:
7000

Current accepted billing value:
6995

Audit history:
7000 → 6995
```

OCR evidence should not be silently overwritten.

Likewise, Team A mappings are recommendation evidence and should not silently overwrite accepted billing values.

---

# Running Tests

From the `backend/` directory:

```bash
python manage.py test
```

To run the current backend integration test suite:

```bash
python manage.py test \
tests.test_recommendation_service \
tests.test_team_a_adapter \
tests.test_team_a_client \
tests.test_billing_validation_service \
tests.test_api_endpoints \
-v 2
```

At the time this README was prepared, the backend suite contained:

```text
36 passing tests
```

These tests cover:

- billing validation
- malformed billing fields
- missing fields
- OCR quality flags
- Team A request mapping
- Team A response validation
- Team A HTTP behavior
- retry handling
- timeout behavior
- workflow transitions
- recommendation evaluation
- re-evaluation
- API error behavior

---

# Git Workflow

Avoid committing directly to shared stable branches when developing new functionality.

Example backend branches:

```text
backend/validation-workflow
backend/recommendation-workflow
database/postgresql-integration
```

Before starting work:

```bash
git fetch origin
```

Check your current branch:

```bash
git branch --show-current
```

Check for uncommitted changes:

```bash
git status
```

After completing a tested change:

```bash
git add <files>
git commit -m "Describe the change"
git push origin <branch-name>
```

Do not commit:

```text
__pycache__/
*.pyc
.env
database passwords
API keys
local secrets
```

---

# Backend Development Rule

Before committing backend changes, run:

```bash
python manage.py check
```

and:

```bash
python manage.py test
```

A feature should not be merged when its related tests are failing.

---

# Development Status

Currently implemented:

```text
Billing record retrieval          ✅
Billing validation                ✅
Workflow state validation         ✅
Team A request mapping            ✅
Team A response validation        ✅
Team A HTTP client                ✅
Timeout handling                  ✅
Retry behavior                    ✅
Recommendation orchestration      ✅
Re-evaluation workflow            ✅
Recommendation API endpoint       ✅
API error handling                ✅
Backend automated tests           ✅
```

In progress:

```text
PostgreSQL persistence            🚧
Recommendation history            🚧
Repository integration            🚧
Human correction persistence      🚧
Audit history                     🚧
Final feedback persistence        🚧
```

Future integration will replace mock data providers with real Django/PostgreSQL repositories without changing the high-level application workflow.

---

# Key Design Principle

The most important architecture rule in this project is:

```text
Team B owns application workflow and corrections.

Team A owns business-data evaluation and recommendations.

Neither silently overwrites the other component's data.
```

The backend acts as the central orchestrator connecting:

```text
Frontend
OCR
Database
Team A
Human Review
```

while keeping billing records durable even when external services fail.
