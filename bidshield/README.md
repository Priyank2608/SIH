# BidShield: AI-Powered GeM Bid Compliance Verification Platform

> **Smart India Hackathon 2026** • Problem Statement ID: **SIH26100**  
> **Theme:** Smart Automation • **Category:** Software  
> **Team:** Ascent-X

---

## 1. Overview & Core Product Objective
**BidShield** is an internal procurement-authority-side intelligence platform designed specifically for evaluating and verifying bids submitted on the **Government e-Marketplace (GeM)**.

BidShield assists authorized procurement officers by executing an evidence-linked, tender-aware verification pipeline while ensuring that:
- **THE FINAL PROCUREMENT DECISION ALWAYS REMAINS WITH THE AUTHORIZED PROCUREMENT OFFICER.**
- **AI assists the officer.** AI **NEVER** independently approves, rejects, qualifies, or disqualifies a bidder.
- **Strict Authority-Side Boundary:** No bidder logins, self-service portals, or bidder marketplaces.
- **Explainable Multi-Dimensional Risk:** Clear distinction between "Low Risk" and "Insufficient Evidence". Anomaly detection never equates anomaly with fraud ("Unusual pattern detected").

```
Tender Document (PDF)
  ↓
Requirement Extraction (AI-assisted)
  ↓
Officer Reviews & Approves Requirements
  ↓
Bidder Submissions & Synthetic Documents (PDFs)
  ↓
Multi-Engine OCR (Tesseract / PyMuPDF Layout Extractor)
  ↓
Structured Field Extraction (GSTIN, PAN, Udyam, OEM ID, Turnover, Experience)
  ↓
Registry Verification (Demo GSTN, NSDL, Udyam, OEM Portals)
  ↓
Deterministic Compliance Rule Engine (GST-001, PAN-001, UDYAM-001, OEM-001, etc.)
  ↓
Historical Performance & Documented Delay Cause Tracking
  ↓
8-Dimensional Explainable Risk Engine
  ↓
Cryptographic Evidence Lineage Graph
  ↓
Procurement Officer Review & Formal Determination
  ↓
Immutable Audit Trail & Dual ReportLab PDF Generation
```

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Next.js 15 (App Router), TypeScript, Native Responsive UI |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, ReportLab PDF Engine |
| **Database** | PostgreSQL 16 (Docker) / SQLite (Standalone Demo Mode) |
| **OCR & Document AI** | Tesseract OCR (`pytesseract`), PyMuPDF (`fitz`), PIL Layout Analyzer |
| **Security & Auth** | OAuth2 Bearer JWT, Role-Based Access Control (RBAC), PBKDF2 Password Hashing |
| **Containerization** | Docker, Docker Compose |

---

## 3. Demo Credentials
| Role | Username | Password |
|---|---|---|
| **Procurement Officer** | `officer` | `BidShield@123` |
| **Verification Officer** | `verifier` | `BidShield@123` |
| **Vigilance Auditor** | `auditor` | `BidShield@123` |
| **System Administrator** | `admin` | `BidShield@123` |

---

## 4. Synthetic Demo Dataset
The platform comes pre-seeded with realistic, interconnected procurement data:
- **5 GeM Tenders:**
  1. `GEM/2026/B/0012345`: Supply of Enterprise Desktop Computers (₹4.5 Cr)
  2. `GEM/2026/B/0023456`: Cloud Infrastructure & Cybersecurity SOC Auditing (₹12.0 Cr)
  3. `GEM/2026/B/0034567`: Specialized ICU Ventilators & Medical Equipment (₹8.0 Cr)
  4. `GEM/2026/B/0045678`: 33/11kV Electrical Transformers & Switchgear (₹18.5 Cr)
  5. `GEM/2026/B/0056789`: 2MW Rooftop Solar PV Installation & AMC (₹6.2 Cr)
- **10 Synthetic Bidders:**
  - *Alpha Technologies Pvt Ltd* (Scenario 1: Fully verified prime contractor)
  - *Bharat Systems Pvt Ltd* (Scenario 2: GSTIN mismatch between profile and certificate)
  - *Gamma Infotech Pvt Ltd* (Scenario 5 & 7: Expired Udyam v1, Corrected v2; v1 preserved)
  - *Delta Digital Solutions* (Scenario 4: Degraded scan triggering `MANUAL_REVIEW`)
  - *Epsilon Engineering Pvt Ltd* (Scenario 6: Simulated provider timeout triggering `RETRY_REQUIRED`)
  - *Zeta Innovations Corp* (Scenario 3: Missing mandatory OEM Authorization letter)
  - *Hindustan Cloud & Networks* (100% on-time delivery across high-value contracts)
  - *Apex Medical Systems Ltd* (Documented Force Majeure supply chain delay)
  - *Dynamic Heavy Electricals* (Startup with 0 past contracts: `INSUFFICIENT_EVIDENCE != LOW_RISK`)
  - *Surya Urja Green Technologies* (Make-in-India 58% local content verified)
- **66 Real Synthetic PDF Documents:**
  - Every document is generated via ReportLab with visible banner: `BIDSHIELD • SYNTHETIC DEMO DOCUMENT`.
  - Cryptographically hashed with SHA-256 and stored with full version lineage.

---

## 5. Quick Start (Local Run)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```
Backend API Docs will be available at: `http://localhost:8000/api/v1/docs`

Schema changes are managed with Alembic from `backend/`. Use `alembic upgrade head`
to apply migrations and `alembic downgrade -1` to reverse the latest migration.
The seed script preserves existing data by default; pass `--reset` only when you
intend to rebuild the synthetic demo database.

The optional offline model-training scripts need extra dependencies; install
`backend/requirements-training.txt` when running those scripts. Production
deployments use `backend/requirements.txt` without scikit-learn/joblib.

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` and sign in using `officer / BidShield@123`.

---

## 6. Backend Architecture for Frontend Development

This section gives the frontend team the exact backend model, routes, auth flow, and data contracts needed to build the UI confidently.

### 6.1 Backend Application Structure

```text
backend/
  app/
    main.py                  # FastAPI app entrypoint, CORS, handlers, router registration
    api/
      auth.py                # Login, current user, auth endpoints
      tenders.py             # Tender CRUD + extracted requirements + decisions
      bidders.py             # Bidder 360 profile, performance, risk, evidence, audit
      documents.py           # upload, OCR, verification, document streaming
      verification.py        # verification control center and provider configs
      reports.py             # quick list and detailed reports generation/download
      audit.py               # audit trail endpoints
      dashboard.py           # dashboard metrics
    core/
      config.py              # app settings, URLs, JWT configuration, demo settings
      security.py            # PBKDF2 password hashing, JWT creation, role enforcement
    db/
      session.py             # SQLAlchemy engine, SQLite/Postgres config, session factory
    models/
      entities.py            # Domain models: User, Tender, Bidder, Documents, OCR, risk, evidence
    schemas/
      schemas.py             # API request/response models (Pydantic)
    services/
      audit_service.py       # append-only audit logging
      compliance_service.py  # rule evaluation for tender requirements
      ocr_service.py         # OCR processing pipeline
      performance_service.py # bidder performance scoring
      report_service.py      # report generation logic
      risk_service.py        # risk calculations and categories
      tender_service.py      # requirement extraction and tender logic
      verification_service.py# registry verification integrations
    static/                  # optional assets if present in future
    tests/                   # backend test folder (if expanded)
  scripts/
    seed.py                  # initialize sample data and provider configs
    seed_realistic_pan.py    # realistic PAN data seeding
    train_document_fraud_ml.py
    train_ocr.py
  requirements.txt
  Dockerfile
```

### 6.2 Runtime Stack and API Base URL

- Framework: FastAPI
- ORM: SQLAlchemy 2.x
- Validation: Pydantic
- Auth: JWT Bearer token
- Database: SQLite in demo mode; PostgreSQL in Docker setup
- Base API prefix: `/api/v1`
- Swagger/OpenAPI: `/api/v1/docs`
- Health check: `/health`

Example:
```text
http://localhost:8000/api/v1/docs
```

### 6.3 Authentication Flow

The backend uses signed bearer JWTs (the payload is not encrypted). All procurement, bidder, document, report, dashboard, and audit routes require a valid token. Requirement changes and officer decisions require `PROCUREMENT_OFFICER` or `SUPER_ADMIN`. On successful login, the server returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "officer",
    "full_name": "Procurement Officer",
    "email": "officer@bidshield.local",
    "role": "PROCUREMENT_OFFICER",
    "tenant_id": 1
  }
}
```

Frontend must send the token in the Authorization header:

```http
Authorization: Bearer <token>
```

Protected routes use `Depends(get_current_user)` and role checks via `require_roles(...)`.

Supported roles in the backend include:
- `SUPER_ADMIN`
- `PROCUREMENT_OFFICER`
- `VERIFICATION_OFFICER`
- `AUDITOR`
- `REVIEWER`

### 6.4 Core Domain Model

The primary business entities are:

- `Tenant`
  - multi-tenant boundary for procurement authorities
- `User`
  - procurement officers, auditors, admin users
- `Tender`
  - tender metadata, requirements, bidders, status
- `TenderRequirement`
  - requirement definitions with `structured_rule` JSON payload
- `Bidder`
  - bidder details and KYC/compliance profile
- `BidderDocument`
  - uploaded document metadata, file hash, versioned document lineage
- `OCRResult`
  - extracted text, confidence, bounding boxes, fields
- `VerificationResult`
  - provider verification outcome (VERIFIED, FAILED, MISMATCH, MANUAL_REVIEW, etc.)
- `TenderBidder`
  - join model between tender and bidder with compliance decision fields
- `ComplianceResult`
  - requirement-by-requirement compliance scoring
- `RiskAssessment`
  - 8-dimension risk evaluation object
- `HistoricalContract`
  - previous contracts for bidder performance and delay analysis
- `EvidenceRecord`
  - evidence graph records used in audit reports
- `AuditLog`
  - immutable audit history

### 6.5 Main API Modules and Routes

#### Authentication
```text
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

#### Tender management
```text
GET    /api/v1/tenders
POST   /api/v1/tenders
GET    /api/v1/tenders/{id}
POST   /api/v1/tenders/{id}/pdf
POST   /api/v1/tenders/{id}/extract-requirements
POST   /api/v1/tenders/{id}/requirements
PUT    /api/v1/tenders/{id}/requirements/{req_id}
POST   /api/v1/tenders/{id}/requirements/{req_id}/approve
POST   /api/v1/tenders/{id}/requirements/{req_id}/reject
POST   /api/v1/tenders/{id}/bidders/{bidder_id}/analyze
POST   /api/v1/tenders/{id}/bidders/{bidder_id}/decision
GET    /api/v1/tenders/{id}/compliance-matrix
GET    /api/v1/tenders/{id}/evidence
```

#### Bidder intelligence
```text
GET /api/v1/bidders
GET /api/v1/bidders/{id}
GET /api/v1/bidders/{id}/performance
GET /api/v1/bidders/{id}/risk
GET /api/v1/bidders/{id}/evidence
GET /api/v1/bidders/{id}/audit
```

#### Documents and evidence processing
```text
GET  /api/v1/documents
POST /api/v1/documents/upload
GET  /api/v1/documents/{id}
GET  /api/v1/documents/{id}/file
POST /api/v1/documents/{id}/ocr
POST /api/v1/documents/{id}/verify
```

#### Verification control center
```text
GET  /api/v1/verification
POST /api/v1/verification/{document_id}/retry
GET  /api/v1/verification/providers
```

#### Reports and audit
```text
GET  /api/v1/reports
POST /api/v1/reports/quick-list
POST /api/v1/reports/detailed-assessment
GET  /api/v1/reports/{report_uid}/download
GET  /api/v1/audit
GET  /api/v1/audit/integrity
GET  /api/v1/dashboard
```

### 6.6 Response and Data Conventions

The API uses:
- JSON responses for all normal business data
- Pydantic schemas for response models
- HTTP status codes for state changes and errors
- `detail` strings for validation and auth errors

Common patterns:
- `200 OK` for fetches and successful updates
- `201` / successful creation patterns in create endpoints
- `400` for duplicate or invalid input
- `401` for missing/expired JWT
- `403` for role permission failures
- `404` for missing resources
- `500` for server-side processing failures with sanitized error messages

### 6.7 Important Business Workflow for Frontend

The app follows this user journey:

```text
Login
  ↓
Dashboard metrics
  ↓
Tender list / open tenders
  ↓
View tender details and requirement matrix
  ↓
Bidder list with compliance and risk scores
  ↓
Document upload / OCR / verification
  ↓
Requirement check and rule evaluation
  ↓
Risk assessment and evidence review
  ↓
Officer decision (ACCEPTED / REJECTED / MANUAL_REVIEW_REQUESTED)
  ↓
Report generation + audit trail
```

### 6.8 Common Frontend-Needed Objects

The API returns core objects that the frontend should model:

#### Tender object
```json
{
  "id": 1,
  "tender_ref": "GEM/2026/B/0012345",
  "title": "Supply of Enterprise Desktop Computers",
  "department": "IT Department",
  "category": "IT Hardware",
  "estimated_value_cr": 4.5,
  "status": "ACTIVE",
  "requirements": [],
  "bidders_count": 8
}
```

#### Bidder object
```json
{
  "id": 2,
  "legal_name": "Alpha Technologies Pvt Ltd",
  "trade_name": "Alpha Tech",
  "pan": "ABCDE1234F",
  "gstin": "27ABCDE1234F1Z9",
  "enterprise_type": "Medium",
  "state": "Maharashtra",
  "is_startup": false
}
```

#### Document object
```json
{
  "id": 10,
  "bidder_id": 2,
  "tender_id": 1,
  "document_type": "GST",
  "filename": "gst_certificate.pdf",
  "mime_type": "application/pdf",
  "version": 1,
  "is_active": true,
  "verification_status": "VERIFIED"
}
```

#### Risk assessment object
```json
{
  "id": 5,
  "tender_bidder_id": 12,
  "overall_score": 26.4,
  "overall_category": "LOW",
  "data_sufficiency": "HIGH"
}
```

### 6.9 Useful Frontend Implementation Notes

- Use the login route first and store the JWT in a secure client session.
- Cache tender and bidder detail data per route or page segment.
- Show loading and error states for OCR and verification operations.
- Treat document versioning as important: every upload creates a new version while preserving previous document records.
- For decisions and approvals, prefer optimistic UI updates with server confirmation.
- Use `risk_level`, `compliance_status`, and `final_decision` for bidder cards, detail panels, and decision modals.

### 6.10 Design Guidance for the Frontend

Suggested UI areas based on the backend modules:
- `Login` and `Profile` → `auth.py`
- `Dashboard` → `dashboard.py`
- `Tender List` and `Tender Detail` → `tenders.py`
- `Bidder 360` → `bidders.py`
- `Document Upload / Review` → `documents.py`
- `Verification Center` → `verification.py`
- `Quick List Report` and `Detailed Dossier` → `reports.py`
- `Audit Trail` → `audit.py`

---

## 7. Docker Deployment

To launch the complete containerized stack (PostgreSQL + FastAPI Backend + Next.js Frontend):
Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` and `BIDSHIELD_JWT_SECRET` with strong random values. Docker startup requires both values.
```bash
docker compose up --build
```
- Web Application: `http://localhost:3000`
- REST API Documentation: `http://localhost:8000/api/v1/docs`

---

## 8. Running Tests

Run the full automated test suite (unit, API, end-to-end workflow, tenant isolation, audit integrity, PDF extraction, and migrations):
```bash
cd backend
pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest ../tests -v
```
Tests cover API flows and synthetic scenarios; they do not provide a formal coverage percentage.

---

## 8. Dual ReportLab PDF Reports
BidShield generates two synthetic demo reports:
1. **REPORT 1: Executive Bidder Summary (Quick List)**
   - Matrix of all bidders for a tender showing compliance percentage, verification statuses, overall risk rating, and human review flags.
2. **REPORT 2: Detailed Bidder Assessment Dossier**
   - Multi-page dossier with submitted document hashes, OCR extraction data, verification provider notes, deterministic rule checklists, historical delivery causes, and the available risk breakdown.

---

## 9. Security & Production Hardening
- **Authentication:** Signed JWTs (120 mins); user role and active status are loaded from the database on each request.
- **RBAC:** Business routes require authentication. Requirement changes and formal officer decisions require `PROCUREMENT_OFFICER` or `SUPER_ADMIN`.
- **File Validation:** PDF MIME and signature checks, structural parsing, upload size limit, safe filename handling, and SHA-256 content hashes.
- **Demo boundary:** Verification compares synthetic local data only. It does not call government registries. With demo mode disabled, verification returns `NOT_AVAILABLE` until a live adapter is configured.
- **Officer authority:** Findings can inform review but cannot block or set the officer's final decision.
- **Tenant isolation:** Procurement queries are scoped from the authenticated user's database-backed tenant membership. Cross-tenant resources are returned as not found where appropriate.
- **Audit integrity:** Audit events form a per-tenant tamper-evident SHA-256 hash chain. Run `GET /api/v1/audit/integrity` as an auditor to verify the chain. This detects tampering but does not make database storage absolutely immutable.
- **Tender requirements:** Uploaded tender PDFs are text-extracted or OCR processed. Extracted rules remain pending candidates until an authorized officer approves them; low-confidence or unreadable scans require manual review.
- **Migrations:** Alembic manages schema upgrades. Existing database contents are preserved by the baseline migration and by the default seed behavior.
- **Error Hygiene:** Server errors are logged internally and returned with sanitized messages.
