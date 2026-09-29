import os
import io
import sys
import hashlib
import argparse
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Add parent directory to sys.path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine, SessionLocal, Base
from app.core.config import settings
from app.core.security import hash_password
from app.models.entities import (
    Tenant, User, Tender, TenderRequirement, Bidder, TenderBidder,
    BidderDocument, HistoricalContract, QualityInspectionRecord,
    ProviderConfig
)
from app.services.tender_service import process_tender_requirements
from app.services.ocr_service import run_ocr_for_document
from app.services.verification_service import run_verification_for_document
from app.services.compliance_service import evaluate_compliance
from app.services.risk_service import calculate_bidder_risk
from app.services.audit_service import log_audit_event

from app.adapters.documents.realistic_generator import generate_realistic_document

DEMO_USERS = (
    ("officer", "officer@bidshield.gov.in", "Rajesh Verma (Procurement Officer)", "PROCUREMENT_OFFICER"),
    ("verifier", "verifier@bidshield.gov.in", "Anita Iyer (Verification Officer)", "VERIFICATION_OFFICER"),
    ("auditor", "auditor@bidshield.gov.in", "Pooja Sharma (Vigilance Auditor)", "AUDITOR"),
    ("admin", "admin@bidshield.gov.in", "Sanjay Kumar (System Administrator)", "SUPER_ADMIN"),
)


def sync_demo_users(db, tenant: Tenant) -> None:
    """Make the documented evaluation accounts available without touching demo data."""
    password = settings.initial_user_password or "BidShield@123"
    for username, email, full_name, role in DEMO_USERS:
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.hashed_password = hash_password(password)
            user.is_active = True
            continue
        db.add(User(
            tenant_id=tenant.id,
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
        ))
    db.commit()

def generate_pdf_document(
    title: str,
    doc_type: str,
    bidder_name: str,
    identifier_label: str,
    identifier_val: str,
    extra_fields: dict,
    is_degraded: bool = False
) -> bytes:
    return generate_realistic_document(
        doc_type=doc_type,
        bidder_name=bidder_name,
        identifier_val=identifier_val,
        extra_fields=extra_fields,
        is_degraded=is_degraded
    )

def seed_database(reset: bool = False):
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    elif existing_tenant := db.query(Tenant).first():
        if settings.reset_demo_passwords:
            sync_demo_users(db, existing_tenant)
            print("Existing demo data preserved; documented evaluation accounts synchronized.")
        else:
            print("Database already contains a tenant; preserving existing data. Use --reset to rebuild the synthetic demo database.")
        db.close()
        return

    # 1. Tenant & Users
    print("Creating Tenant and Users...")
    tenant = Tenant(code="GEM-GOI-01", name="Government e-Marketplace (GeM) - Central Procurement Authority")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    sync_demo_users(db, tenant)
    officer = db.query(User).filter(User.username == "officer").one()
    admin = db.query(User).filter(User.username == "admin").one()

    # 2. Five Synthetic GeM Tenders
    print("Creating 5 synthetic GeM tenders...")
    tenders_data = [
        {
            "ref": "GEM/2026/B/0012345",
            "gem": "GEM-REF-99211",
            "title": "Supply and Commissioning of Enterprise Desktop Computers and Peripherals",
            "dept": "Ministry of Electronics and Information Technology",
            "cat": "IT Equipment & Hardware",
            "desc": "Supply, installation and 3-year on-site warranty for 500 Enterprise Workstations. Requires OEM Authorization, GST, PAN, 3 years past experience, and min 50% Make in India local content.",
            "val": 4.5,
            "issue": "2026-09-01",
            "close": "2026-10-15"
        },
        {
            "ref": "GEM/2026/B/0023456",
            "gem": "GEM-REF-99212",
            "title": "Cloud Infrastructure Hosting and Cybersecurity SOC Auditing Services",
            "dept": "National Informatics Centre (NIC)",
            "cat": "Cloud & Cybersecurity Services",
            "desc": "Procurement of managed cloud hosting, ISO 27001 compliance, annual turnover >= 10 Cr, and past experience in high-security government portals.",
            "val": 12.0,
            "issue": "2026-08-15",
            "close": "2026-10-05"
        },
        {
            "ref": "GEM/2026/B/0034567",
            "gem": "GEM-REF-99213",
            "title": "Procurement of Specialized ICU Ventilators and Patient Monitors",
            "dept": "Ministry of Health & Family Welfare",
            "cat": "Medical Devices & Hospital Equipment",
            "desc": "Supply of 120 Advanced ICU Ventilators. Mandatory OEM Authorization, CDSCO regulatory clearance, ISO 13485, and prompt historical delivery track record.",
            "val": 8.0,
            "issue": "2026-09-10",
            "close": "2026-10-25"
        },
        {
            "ref": "GEM/2026/B/0045678",
            "gem": "GEM-REF-99214",
            "title": "Supply of 33/11kV Electrical Transformers and Smart Switchgear Units",
            "dept": "Central Electricity Authority / Power Grid",
            "cat": "Heavy Electrical & Power Equipment",
            "desc": "Design, manufacture, type-testing and delivery of distribution transformers with CPRI test certificates, 5-year warranty, and min 5-year past supply experience.",
            "val": 18.5,
            "issue": "2026-08-20",
            "close": "2026-10-10"
        },
        {
            "ref": "GEM/2026/B/0056789",
            "gem": "GEM-REF-99215",
            "title": "Turnkey Rooftop Solar PV Installation (2MW) with 5-Year Comprehensive AMC",
            "dept": "Ministry of New and Renewable Energy",
            "cat": "Solar & Renewable Energy",
            "desc": "Design, installation, grid interconnection and 5-year comprehensive maintenance. Requires Class-I Local Content (>= 50%), MNRE channel partner registration, and Udyam certification.",
            "val": 6.2,
            "issue": "2026-09-05",
            "close": "2026-10-30"
        }
    ]

    tenders = []
    for td in tenders_data:
        t = Tender(
            tenant_id=tenant.id,
            tender_ref=td["ref"],
            gem_ref=td["gem"],
            title=td["title"],
            department=td["dept"],
            category=td["cat"],
            description=td["desc"],
            estimated_value_cr=td["val"],
            issue_date=td["issue"],
            closing_date=td["close"],
            status="ACTIVE",
            created_by_id=officer.id
        )
        db.add(t)
        tenders.append(t)
    db.commit()

    # Automatically extract and approve requirements for tenders
    for t in tenders:
        reqs = process_tender_requirements(db, t.id, officer.id, officer.username)
        for r in reqs:
            r.approval_status = "APPROVED"
            r.approving_officer_id = officer.id
            r.approved_at = datetime.now(timezone.utc)
            r.officer_notes = "Reviewed and approved by Procurement Officer."
    db.commit()

    # 3. Ten Synthetic Bidders
    print("Creating 10 synthetic bidders with realistic profiles...")
    bidders_data = [
        {
            "name": "Alpha Technologies Pvt Ltd",
            "pan": "AAACA1234A",
            "gstin": "27AAACA1234A1Z5",
            "cin": "U72200MH2016PTC288123",
            "udyam": "UDYAM-MH-02-0012345",
            "type": "Medium",
            "startup": False,
            "addr": "Plot 42, Electronics Zone, MIDC Mahape",
            "state": "Maharashtra",
            "dist": "Navi Mumbai",
            "email": "contact@alphatech-demo.in",
            "phone": "+91 98201 11222",
            "person": "Aarav Sharma"
        },
        {
            "name": "Bharat Systems Pvt Ltd",
            "pan": "AABCB5678B",
            "gstin": "27AABCB1111Z1Z2", # In document we will intentionally have 27AABCB9999Z1Z5 for mismatch!
            "cin": "U72900MH2018PTC304567",
            "udyam": "UDYAM-MH-01-0023456",
            "type": "Small",
            "startup": False,
            "addr": "Tech Park Tower B, Hinjewadi Phase 1",
            "state": "Maharashtra",
            "dist": "Pune",
            "email": "procurement@bharatsystems-demo.in",
            "phone": "+91 98202 22333",
            "person": "Vikram Patel"
        },
        {
            "name": "Gamma Infotech Pvt Ltd",
            "pan": "AACCG9012C",
            "gstin": "06AACCG9012C1Z8",
            "cin": "U72400HR2015PTC055678",
            "udyam": "UDYAM-HR-04-0034567",
            "type": "Small",
            "startup": False,
            "addr": "DLF Cyber City, Tower 8C, Sector 24",
            "state": "Haryana",
            "dist": "Gurugram",
            "email": "sales@gammainfotech-demo.in",
            "phone": "+91 98203 33444",
            "person": "Rohan Gupta"
        },
        {
            "name": "Delta Digital Solutions",
            "pan": "AADDD3456D",
            "gstin": "29AADDD3456D1Z1",
            "cin": "U72200KA2017PTC101234",
            "udyam": "UDYAM-KR-03-0045678",
            "type": "Micro",
            "startup": True,
            "addr": "7th Main, 100ft Road, Indiranagar",
            "state": "Karnataka",
            "dist": "Bengaluru",
            "email": "bids@deltadigital-demo.in",
            "phone": "+91 98204 44555",
            "person": "Kavita Reddy"
        },
        {
            "name": "Epsilon Engineering Pvt Ltd",
            "pan": "AAEEE7890E",
            "gstin": "07AAEEE7890E1Z4",
            "cin": "U29200DL2014PTC267890",
            "udyam": "UDYAM-DL-05-0056789",
            "type": "Medium",
            "startup": False,
            "addr": "Okhla Industrial Area Phase-III",
            "state": "Delhi",
            "dist": "South Delhi",
            "email": "tender@epsiloneng-demo.in",
            "phone": "+91 98205 55666",
            "person": "Manish Tiwari"
        },
        {
            "name": "Zeta Innovations Corp",
            "pan": "AAFZZ1234F",
            "gstin": "33AAFZZ1234F1Z7",
            "cin": "U74900TN2019PTC123456",
            "udyam": "UDYAM-TN-02-0067890",
            "type": "Small",
            "startup": True,
            "addr": "Guindy Industrial Estate, Mount Road",
            "state": "Tamil Nadu",
            "dist": "Chennai",
            "email": "info@zetainnovations-demo.in",
            "phone": "+91 98206 66777",
            "person": "Deepak Natarajan"
        },
        {
            "name": "Hindustan Cloud & Networks",
            "pan": "AAGHH5678G",
            "gstin": "27AAGHH5678G1Z9",
            "cin": "U72300MH2012PTC234567",
            "udyam": "UDYAM-MH-03-0078901",
            "type": "Large",
            "startup": False,
            "addr": "Nesco IT Park, Western Express Highway, Goregaon East",
            "state": "Maharashtra",
            "dist": "Mumbai Suburban",
            "email": "gem@hindustancloud-demo.in",
            "phone": "+91 98207 77888",
            "person": "Ananya Sen"
        },
        {
            "name": "Apex Medical Systems Ltd",
            "pan": "AAHAM9012H",
            "gstin": "07AAHAM9012H1Z3",
            "cin": "L33110DL2010PLC201234",
            "udyam": "UDYAM-DL-01-0089012",
            "type": "Large",
            "startup": False,
            "addr": "Connaught Place, Barakhamba Road",
            "state": "Delhi",
            "dist": "New Delhi",
            "email": "health@apexmedical-demo.in",
            "phone": "+91 98208 88999",
            "person": "Dr. Sameer Chawla"
        },
        {
            "name": "Dynamic Heavy Electricals",
            "pan": "AAIDH3456I",
            "gstin": "09AAIDH3456I1Z6",
            "cin": "U31100UP2022PTC156789",
            "udyam": "UDYAM-UP-08-0090123",
            "type": "Small",
            "startup": True,
            "addr": "UPSIDC Industrial Area, Site IV, Sahibabad",
            "state": "Uttar Pradesh",
            "dist": "Ghaziabad",
            "email": "supply@dynamicheavy-demo.in",
            "phone": "+91 98209 99000",
            "person": "Praveen Yadav"
        },
        {
            "name": "Surya Urja Green Technologies",
            "pan": "AAJSU7890J",
            "gstin": "24AAJSU7890J1Z2",
            "cin": "U40106GJ2020PTC112345",
            "udyam": "UDYAM-GJ-01-0101234",
            "type": "Small",
            "startup": True,
            "addr": "GIDC Electronics Zone, Sector 25",
            "state": "Gujarat",
            "dist": "Gandhinagar",
            "email": "solar@suryaurja-demo.in",
            "phone": "+91 98210 00111",
            "person": "Hardik Shah"
        }
    ]

    bidders = []
    for bd in bidders_data:
        b = Bidder(
            tenant_id=tenant.id,
            legal_name=bd["name"],
            trade_name=bd["name"].replace(" Pvt Ltd", "").replace(" Ltd", "").replace(" Corp", ""),
            pan=bd["pan"],
            gstin=bd["gstin"],
            cin=bd["cin"],
            udyam_number=bd["udyam"],
            enterprise_type=bd["type"],
            is_startup=bd["startup"],
            address=bd["addr"],
            state=bd["state"],
            district=bd["dist"],
            contact_email=bd["email"],
            contact_phone=bd["phone"],
            contact_person=bd["person"],
            incorporation_date="2016-04-12"
        )
        db.add(b)
        bidders.append(b)
    db.commit()

    # 4. Associate Bidders to Tenders (TenderBidder)
    print("Associating bidders with tenders...")
    for t in tenders:
        for b in bidders:
            tb = TenderBidder(
                tender_id=t.id,
                bidder_id=b.id,
                submission_date="2026-09-20",
                compliance_status="PENDING",
                compliance_score=0.0,
                risk_level="LOW",
                final_decision="PENDING"
            )
            db.add(tb)
    db.commit()

    # 5. Historical Contracts & Quality Records
    print("Seeding historical contracts, delivery records and quality metrics...")
    contracts_map = {
        "Alpha Technologies Pvt Ltd": [
            ("GEMC-2024-001", "Ministry of Railways", "Supply of 300 Rugged Laptops", "IT Equipment", 240.0, "2024-03-01", "2024-06-30", "2024-06-25", "COMPLETED", 0, "NONE", 0.0, 4.8),
            ("GEMC-2024-002", "Defence Research Org", "Server Cluster Deployment", "IT Equipment", 480.0, "2024-07-10", "2024-11-30", "2024-11-28", "COMPLETED", 0, "NONE", 0.0, 4.9),
            ("GEMC-2025-001", "State Police Headquarters", "Network Switches & Access Points", "IT Equipment", 180.0, "2025-01-15", "2025-04-15", "2025-04-10", "COMPLETED", 0, "NONE", 0.0, 4.7)
        ],
        "Bharat Systems Pvt Ltd": [
            ("GEMC-2023-010", "Department of Posts", "Workstation Monitors & UPS", "IT Equipment", 120.0, "2023-05-01", "2023-08-31", "2023-09-20", "COMPLETED", 20, "CONTRACTOR", 25000.0, 3.8),
            ("GEMC-2024-015", "Kendriya Vidyalaya Sangathan", "Computer Lab Setup", "IT Equipment", 95.0, "2024-02-01", "2024-05-15", "2024-05-30", "COMPLETED", 15, "CONTRACTOR", 18000.0, 3.9)
        ],
        "Gamma Infotech Pvt Ltd": [
            ("GEMC-2024-022", "Income Tax Department", "Cloud Managed Storage Support", "IT Services", 310.0, "2024-01-10", "2024-12-31", "2024-12-31", "COMPLETED", 0, "NONE", 0.0, 4.6),
            ("GEMC-2025-030", "EPFO Regional Office", "Database Security Audit", "Cloud & Cybersecurity", 150.0, "2025-02-01", "2025-06-30", "2025-06-28", "COMPLETED", 0, "NONE", 0.0, 4.8)
        ],
        "Delta Digital Solutions": [
            ("GEMC-2025-044", "Municipal Corporation", "Biometric Attendance Terminals", "Peripherals", 65.0, "2025-03-01", "2025-05-31", "2025-06-10", "COMPLETED", 10, "APPROVED_EXTENSION", 0.0, 4.1)
        ],
        "Epsilon Engineering Pvt Ltd": [
            ("GEMC-2023-050", "Delhi Metro Rail Corp", "Substation Earthing & Cables", "Heavy Electrical", 520.0, "2023-04-01", "2023-11-30", "2023-11-25", "COMPLETED", 0, "NONE", 0.0, 4.4),
            ("GEMC-2024-055", "National Thermal Power Corp", "Control Panel Relays", "Heavy Electrical", 380.0, "2024-03-15", "2024-09-30", "2024-10-15", "COMPLETED", 15, "PROCURING_ENTITY", 0.0, 4.2)
        ],
        "Zeta Innovations Corp": [
            ("GEMC-2025-060", "State Skill Mission", "Virtual Training Workstations", "IT Equipment", 85.0, "2025-01-15", "2025-04-30", "2025-04-28", "COMPLETED", 0, "NONE", 0.0, 4.3)
        ],
        "Hindustan Cloud & Networks": [
            ("GEMC-2023-070", "Ministry of External Affairs", "Passport Seva Cloud Migration", "Cloud & Cybersecurity", 1450.0, "2023-01-01", "2023-12-31", "2023-12-20", "COMPLETED", 0, "NONE", 0.0, 4.9),
            ("GEMC-2024-075", "UIDAI Aadhaar Data Center", "SOC Monitoring & SIEM Implementation", "Cloud & Cybersecurity", 920.0, "2024-04-01", "2025-03-31", "2025-03-25", "COMPLETED", 0, "NONE", 0.0, 5.0),
            ("GEMC-2025-080", "State Data Center", "Disaster Recovery Automation", "Cloud & Cybersecurity", 680.0, "2025-05-01", "2025-09-15", "2025-09-10", "COMPLETED", 0, "NONE", 0.0, 4.9)
        ],
        "Apex Medical Systems Ltd": [
            ("GEMC-2023-085", "AIIMS New Delhi", "Advanced Pediatric Ventilators", "Medical Devices", 750.0, "2023-03-01", "2023-08-31", "2023-10-15", "COMPLETED", 45, "FORCE_MAJEURE", 0.0, 4.3),
            ("GEMC-2024-090", "Safdarjung Hospital", "Anesthesia Delivery Systems", "Medical Devices", 420.0, "2024-02-15", "2024-07-31", "2024-07-28", "COMPLETED", 0, "NONE", 0.0, 4.7)
        ],
        "Dynamic Heavy Electricals": [
            # Startup with 0 public contracts to test INSUFFICIENT_EVIDENCE
        ],
        "Surya Urja Green Technologies": [
            ("GEMC-2024-095", "Gujarat Energy Development Agency", "500kW Rooftop Solar Installation", "Solar & Renewable", 210.0, "2024-04-01", "2024-08-31", "2024-08-25", "COMPLETED", 0, "NONE", 0.0, 4.7),
            ("GEMC-2025-098", "Airport Authority of India", "Solar Carport Power Plant", "Solar & Renewable", 340.0, "2025-01-10", "2025-05-31", "2025-05-28", "COMPLETED", 0, "NONE", 0.0, 4.8)
        ]
    }

    for b in bidders:
        c_list = contracts_map.get(b.legal_name, [])
        for c in c_list:
            hc = HistoricalContract(
                bidder_id=b.id,
                contract_ref=c[0],
                procuring_entity=c[1],
                title=c[2],
                category=c[3],
                contract_value_lakhs=c[4],
                issue_date=c[5],
                scheduled_completion=c[6],
                actual_completion=c[7],
                status=c[8],
                delay_days=c[9],
                documented_delay_cause=c[10],
                liquidated_damages_inr=c[11],
                performance_rating=c[12],
                similarity_score=0.88
            )
            db.add(hc)
            db.commit()
            db.refresh(hc)

            # Quality records
            qr = QualityInspectionRecord(
                contract_id=hc.id,
                inspection_date=c[7] or c[6],
                inspection_agency="Directorate General of Quality Assurance (DGQA)",
                result="PASS" if c[9] == 0 else "CONDITIONAL",
                defect_count=0 if c[9] == 0 else 2,
                rework_required=False,
                warranty_claims=0,
                remarks="All factory type tests and on-site commissioning parameters complied."
            )
            db.add(qr)
    db.commit()

    # 6. Generate 60+ Synthetic Documents across 10 Bidders
    print("Generating 60+ synthetic PDF documents with real bytes and cryptographic hashes...")

    # Document generation specs per bidder
    docs_to_create = []

    # 1. Alpha Tech (All genuine & verified)
    docs_to_create.extend([
        (bidders[0], "PAN", "PAN Card Verification Certificate", "PAN", "AAACA1234A", {"Date of Issue": "2016-05-10", "Status": "OPERATIVE"}),
        (bidders[0], "GST", "Goods and Services Tax Registration Certificate", "GSTIN", "27AAACA1234A1Z5", {"Registration Status": "ACTIVE", "Address": bidders[0].address}),
        (bidders[0], "UDYAM", "Udyam MSME Registration Certificate", "UDYAM", "UDYAM-MH-02-0012345", {"Enterprise Type": "Medium", "Expiry Date": "2029-12-31"}),
        (bidders[0], "OEM", "Manufacturer Authorization Form (MAF)", "OEM AUTH ID", "OEM-DELL-2026-9921", {"Product Category": "Desktop Computers", "Valid Until": "2027-12-31"}),
        (bidders[0], "EXPERIENCE", "Past Procurement Experience Certificate", "Experience", "4 Years", {"Contract Value": "INR 480 Lakhs", "Status": "Completed Successfully"}),
        (bidders[0], "TURNOVER", "Chartered Accountant Audited Turnover Certificate", "Turnover", "INR 14.5 Crore", {"UDIN": "26099123AAAA01", "Financial Year": "2024-2025"}),
        (bidders[0], "LOCAL_CONTENT", "Make in India Class-I Local Content Declaration", "Local Content", "62%", {"Statutory Threshold": ">= 50%", "Location": "Navi Mumbai Facility"})
    ])

    # 2. Bharat Systems (Scenario 2: GSTIN mismatch in document vs profile)
    docs_to_create.extend([
        (bidders[1], "PAN", "PAN Card Verification Certificate", "PAN", "AABCB5678B", {"Status": "OPERATIVE"}),
        (bidders[1], "GST", "GST Registration Certificate", "GSTIN", "27AABCB9999Z1Z5", {"Registration Status": "ACTIVE", "Notice": "Discrepancy with portal profile"}),
        (bidders[1], "UDYAM", "Udyam Registration Certificate", "UDYAM", "UDYAM-MH-01-0023456", {"Enterprise Type": "Small", "Expiry Date": "2028-12-31"}),
        (bidders[1], "OEM", "Manufacturer Authorization Form", "OEM AUTH ID", "OEM-HP-2026-4412", {"Valid Until": "2027-06-30"}),
        (bidders[1], "EXPERIENCE", "Past Performance Experience Certificate", "Experience", "3 Years", {"Contract Value": "INR 120 Lakhs"}),
        (bidders[1], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 6.2 Crore", {"UDIN": "26088234BBBB02"})
    ])

    # 3. Gamma Infotech (Scenario 5 & 7: Expired Udyam v1, Corrected v2!)
    docs_to_create.extend([
        (bidders[2], "PAN", "PAN Card Verification Certificate", "PAN", "AACCG9012C", {"Status": "OPERATIVE"}),
        (bidders[2], "GST", "GST Registration Certificate", "GSTIN", "06AACCG9012C1Z8", {"Registration Status": "ACTIVE"}),
        # Version 1: Expired Udyam
        (bidders[2], "UDYAM", "Udyam Registration Certificate (v1)", "UDYAM", "UDYAM-HR-04-0034567", {"Enterprise Type": "Small", "Expiry Date": "2026-05-15", "Status": "EXPIRED"}),
        # Version 2: Corrected & Renewed Udyam
        (bidders[2], "UDYAM", "Udyam Registration Certificate (v2 Renewed)", "UDYAM", "UDYAM-HR-04-0034567", {"Enterprise Type": "Small", "Expiry Date": "2028-12-31", "Status": "ACTIVE"}),
        (bidders[2], "OEM", "OEM Cloud Reseller Authorization", "OEM AUTH ID", "OEM-AWS-2026-8812", {"Valid Until": "2027-12-31"}),
        (bidders[2], "EXPERIENCE", "Cybersecurity Project Experience", "Experience", "5 Years", {"Contract Value": "INR 310 Lakhs"}),
        (bidders[2], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 18.0 Crore", {"UDIN": "26077345CCCC03"}),
        (bidders[2], "LOCAL_CONTENT", "Make in India Declaration", "Local Content", "55%", {"Status": "Compliant"})
    ])

    # 4. Delta Digital (Scenario 4: Degraded scan triggering MANUAL_REVIEW)
    docs_to_create.extend([
        (bidders[3], "PAN", "PAN Card Verification Certificate", "PAN", "AADDD3456D", {"Status": "OPERATIVE"}),
        (bidders[3], "GST", "GST Registration Certificate (Low Quality Scan)", "GSTIN", "29AADDD3456D1Z1", {"Scan Note": "DEGRADED LOW QUALITY SCAN", "Registration Status": "ACTIVE"}, True),
        (bidders[3], "UDYAM", "Udyam MSME Certificate", "UDYAM", "UDYAM-KR-03-0045678", {"Enterprise Type": "Micro", "Expiry Date": "2029-10-10"}),
        (bidders[3], "OEM", "OEM Authorization Form", "OEM AUTH ID", "OEM-LENOVO-2026-119", {"Valid Until": "2027-08-31"}),
        (bidders[3], "EXPERIENCE", "Experience Certificate", "Experience", "2 Years", {"Contract Value": "INR 65 Lakhs"}),
        (bidders[3], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 3.5 Crore", {"UDIN": "26066456DDDD04"})
    ])

    # 5. Epsilon Engineering (Scenario 6: Simulated provider timeout -> RETRY_REQUIRED)
    docs_to_create.extend([
        (bidders[4], "PAN", "PAN Card Verification Certificate", "PAN", "AAEEE7890E", {"Status": "OPERATIVE"}),
        (bidders[4], "GST", "GST Registration Certificate (Gateway Retry Test)", "GSTIN", "07AAEEE7890E1Z4", {"Provider Action": "RETRY_REQUIRED_SIMULATED", "Registration Status": "ACTIVE"}),
        (bidders[4], "UDYAM", "Udyam Certificate", "UDYAM", "UDYAM-DL-05-0056789", {"Enterprise Type": "Medium", "Expiry Date": "2028-09-30"}),
        (bidders[4], "EXPERIENCE", "Transformer Supply Experience", "Experience", "6 Years", {"Contract Value": "INR 520 Lakhs"}),
        (bidders[4], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 22.0 Crore", {"UDIN": "26055567EEEE05"}),
        (bidders[4], "LOCAL_CONTENT", "Make in India Declaration", "Local Content", "70%", {"Status": "Compliant"})
    ])

    # 6. Zeta Innovations (Scenario 3: Missing OEM letter!)
    docs_to_create.extend([
        (bidders[5], "PAN", "PAN Card Verification Certificate", "PAN", "AAFZZ1234F", {"Status": "OPERATIVE"}),
        (bidders[5], "GST", "GST Registration Certificate", "GSTIN", "33AAFZZ1234F1Z7", {"Registration Status": "ACTIVE"}),
        (bidders[5], "UDYAM", "Udyam MSME Certificate", "UDYAM", "UDYAM-TN-02-0067890", {"Enterprise Type": "Small", "Expiry Date": "2029-04-15"}),
        (bidders[5], "EXPERIENCE", "Past Procurement Experience", "Experience", "2 Years", {"Contract Value": "INR 85 Lakhs"}),
        (bidders[5], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 4.2 Crore", {"UDIN": "26044678FFFF06"})
        # OEM document intentionally omitted!
    ])

    # 7. Hindustan Cloud & Networks (Multi-doc prime cloud player)
    docs_to_create.extend([
        (bidders[6], "PAN", "PAN Card Verification Certificate", "PAN", "AAGHH5678G", {"Status": "OPERATIVE"}),
        (bidders[6], "GST", "GST Registration Certificate", "GSTIN", "27AAGHH5678G1Z9", {"Registration Status": "ACTIVE"}),
        (bidders[6], "UDYAM", "Udyam Registration Certificate", "UDYAM", "UDYAM-MH-03-0078901", {"Enterprise Type": "Large", "Expiry Date": "2030-12-31"}),
        (bidders[6], "MCA", "MCA Certificate of Incorporation", "CIN", "U72300MH2012PTC234567", {"RoC": "Mumbai", "Paid Up Capital": "INR 5.0 Cr"}),
        (bidders[6], "EPFO", "EPFO Establishment Compliance Certificate", "UAN", "101299887766", {"Active Employees": "450"}),
        (bidders[6], "ESIC", "ESIC Employer Registration Certificate", "ESIC", "310009988112233", {"Status": "Regular"}),
        (bidders[6], "EXPERIENCE", "National Cloud Implementation Experience", "Experience", "10 Years", {"Contract Value": "INR 1450 Lakhs"}),
        (bidders[6], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 48.0 Crore", {"UDIN": "26033789GGGG07"})
    ])

    # 8. Apex Medical Systems Ltd
    docs_to_create.extend([
        (bidders[7], "PAN", "PAN Card Verification Certificate", "PAN", "AAHAM9012H", {"Status": "OPERATIVE"}),
        (bidders[7], "GST", "GST Registration Certificate", "GSTIN", "07AAHAM9012H1Z3", {"Registration Status": "ACTIVE"}),
        (bidders[7], "UDYAM", "Udyam Registration Certificate", "UDYAM", "UDYAM-DL-01-0089012", {"Enterprise Type": "Large", "Expiry Date": "2030-05-30"}),
        (bidders[7], "OEM", "Medical Device OEM Authorization Form", "OEM AUTH ID", "OEM-MED-2026-5541", {"Valid Until": "2028-12-31"}),
        (bidders[7], "EXPERIENCE", "Hospital ICU Ventilator Installation Experience", "Experience", "8 Years", {"Contract Value": "INR 750 Lakhs"}),
        (bidders[7], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 35.0 Crore", {"UDIN": "26022890HHHH08"}),
        (bidders[7], "LOCAL_CONTENT", "Make in India Declaration (Medical Devices)", "Local Content", "52%", {"Threshold": "Class-I Local Supplier"})
    ])

    # 9. Dynamic Heavy Electricals (Startup with local content and exemption)
    docs_to_create.extend([
        (bidders[8], "PAN", "PAN Card Verification Certificate", "PAN", "AAIDH3456I", {"Status": "OPERATIVE"}),
        (bidders[8], "GST", "GST Registration Certificate", "GSTIN", "09AAIDH3456I1Z6", {"Registration Status": "ACTIVE"}),
        (bidders[8], "UDYAM", "Udyam MSME Certificate", "UDYAM", "UDYAM-UP-08-0090123", {"Enterprise Type": "Small", "Expiry Date": "2031-01-10"}),
        (bidders[8], "STARTUP", "DPIIT Startup Recognition Certificate", "STARTUP ID", "DPIIT-UP-2022-7712", {"Valid Till": "2032-01-10"}),
        (bidders[8], "LOCAL_CONTENT", "Make in India Local Content Declaration", "Local Content", "65%", {"Facility": "Sahibabad Unit"}),
        (bidders[8], "TURNOVER", "Audited CA Statement (Startup Stage)", "Turnover", "INR 1.8 Crore", {"UDIN": "26011901IIII09"})
    ])

    # 10. Surya Urja Green Technologies
    docs_to_create.extend([
        (bidders[9], "PAN", "PAN Card Verification Certificate", "PAN", "AAJSU7890J", {"Status": "OPERATIVE"}),
        (bidders[9], "GST", "GST Registration Certificate", "GSTIN", "24AAJSU7890J1Z2", {"Registration Status": "ACTIVE"}),
        (bidders[9], "UDYAM", "Udyam Registration Certificate", "UDYAM", "UDYAM-GJ-01-0101234", {"Enterprise Type": "Small", "Expiry Date": "2029-08-20"}),
        (bidders[9], "OEM", "Tier-1 Solar Cell & Inverter OEM Authorization", "OEM AUTH ID", "OEM-SOLAR-2026-3391", {"Valid Until": "2028-06-30"}),
        (bidders[9], "EXPERIENCE", "Grid Solar Installation Experience", "Experience", "4 Years", {"Contract Value": "INR 340 Lakhs"}),
        (bidders[9], "TURNOVER", "CA Turnover Certificate", "Turnover", "INR 9.5 Crore", {"UDIN": "26000012JJJJ10"}),
        (bidders[9], "LOCAL_CONTENT", "Make in India Solar PV Declaration", "Local Content", "58%", {"MNRE Status": "Class-I Compliant"})
    ])

    # Process and save all synthetic documents
    doc_counter = 0
    created_docs = []

    # Map previous version for Gamma Infotech's Udyam v2
    gamma_udyam_v1_id = None

    for item in docs_to_create:
        bidder = item[0]
        doc_type = item[1]
        title = item[2]
        id_lbl = item[3]
        id_val = item[4]
        extras = item[5]
        is_deg = item[6] if len(item) > 6 else False

        pdf_bytes = generate_pdf_document(
            title=title,
            doc_type=doc_type,
            bidder_name=bidder.legal_name,
            identifier_label=id_lbl,
            identifier_val=id_val,
            extra_fields=extras,
            is_degraded=is_deg
        )

        f_hash = hashlib.sha256(pdf_bytes).hexdigest()
        version = 1
        is_active = True
        prev_id = None

        if bidder.legal_name == "Gamma Infotech Pvt Ltd" and doc_type == "UDYAM":
            if "v2" in title:
                version = 2
                is_active = True
                prev_id = gamma_udyam_v1_id
            else:
                version = 1
                is_active = False # Superseded by v2, but strictly kept in DB!

        filename = f"{doc_type.lower()}_{bidder.legal_name.lower().replace(' ', '_')[:12]}_v{version}.pdf"

        b_doc = BidderDocument(
            bidder_id=bidder.id,
            tender_id=tenders[0].id, # Link primarily to primary tender
            document_type=doc_type,
            filename=filename,
            mime_type="application/pdf",
            file_hash=f_hash,
            file_size_bytes=len(pdf_bytes),
            version=version,
            is_active=is_active,
            previous_version_id=prev_id,
            is_synthetic=True,
            content_bytes=pdf_bytes
        )
        db.add(b_doc)
        db.commit()
        db.refresh(b_doc)

        if bidder.legal_name == "Gamma Infotech Pvt Ltd" and doc_type == "UDYAM" and "v1" in title:
            gamma_udyam_v1_id = b_doc.id

        created_docs.append(b_doc)
        doc_counter += 1

    print(f"Created {doc_counter} synthetic documents successfully.")

    # 7. Run OCR, Verification, Compliance, and Risk for All 10 Bidders
    print("Running OCR, Verification, Deterministic Compliance, and Risk pipeline for all 10 bidders...")
    for d in created_docs:
        try:
            run_ocr_for_document(db, d.id, officer.id, officer.username)
            run_verification_for_document(db, d.id, officer.id, officer.username)
        except Exception as e:
            print(f"Error processing doc {d.id}: {e}")

    for t in tenders:
        for b in bidders:
            try:
                evaluate_compliance(db, t.id, b.id)
                calculate_bidder_risk(db, t.id, b.id)
            except Exception as e:
                print(f"Error evaluating compliance for {b.legal_name} in tender {t.tender_ref}: {e}")

    # Seed Provider Configs
    print("Registering Provider Configurations...")
    default_providers = [
        ("DEMO_GSTN", "Synthetic local GST comparison (no live API)", "GST", "NONE", "https://not-configured.invalid/gst"),
        ("DEMO_NSDL", "Synthetic local PAN comparison (no live API)", "PAN", "NONE", "https://not-configured.invalid/pan"),
        ("DEMO_MSME", "Synthetic local Udyam comparison (no live API)", "UDYAM", "NONE", "https://not-configured.invalid/udyam"),
        ("DEMO_OEM", "Synthetic local OEM comparison (no live API)", "OEM", "NONE", "https://not-configured.invalid/oem"),
        ("DEMO_ICAI", "Synthetic local turnover comparison (no live API)", "TURNOVER", "NONE", "https://not-configured.invalid/turnover"),
        ("DEMO_PROC", "Synthetic local experience comparison (no live API)", "EXPERIENCE", "NONE", "https://not-configured.invalid/experience"),
    ]
    for code, name, doc_type, auth_type, ep in default_providers:
        p = ProviderConfig(
            provider_code=code,
            provider_name=name,
            document_type=doc_type,
            auth_type=auth_type,
            api_endpoint=ep,
            is_active=True,
            timeout_seconds=10
        )
        db.add(p)
    db.commit()

    # Log seed completion
    log_audit_event(
        db,
        action="DATABASE_SEEDED",
        entity_type="SYSTEM",
        entity_id="ALL",
        user_id=admin.id,
        username="admin",
        details={
            "tenders_count": len(tenders),
            "bidders_count": len(bidders),
            "documents_count": doc_counter
        }
    )

    print("=== SEED COMPLETE ===")
    print(f"Total Tenders: {len(tenders)}")
    print(f"Total Bidders: {len(bidders)}")
    print(f"Total Documents: {doc_counter}")
    print("Seeded accounts: officer, verifier, auditor, admin")
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the clearly synthetic BidShield demo dataset")
    parser.add_argument("--reset", action="store_true", help="Delete existing database contents and rebuild the demo dataset")
    seed_database(reset=parser.parse_args().reset)
