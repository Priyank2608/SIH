import io
import hashlib
import uuid
import base64
import re
from datetime import datetime, timezone
from typing import Optional
from xml.sax.saxutils import escape
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image
)
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models.entities import (
    Tender, Bidder, TenderBidder, BidderDocument, OCRResult,
    VerificationResult, ComplianceResult, RiskAssessment,
    HistoricalContract, EvidenceRecord, GeneratedReport, User, Tenant
)
from app.services.audit_service import log_audit_event

def _draw_footer(report_uid: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 22, f"BidShield generated procurement assessment - BS-RPT-{report_uid[:12].upper()}")
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 22, f"Page {doc.page}")
        canvas.restoreState()
    return draw

def _append_signature_block(elements, db: Session, user_id: int, username: str, report_uid: str, signature_data: Optional[str]):
    officer = db.query(User).filter(User.id == user_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == officer.tenant_id).first() if officer else None
    styles = getSampleStyleSheet()
    elements.append(Spacer(1, 18))
    elements.append(Paragraph("Officer Information and Determination", styles["Heading2"]))
    elements.append(Paragraph(
        f"Officer: {officer.full_name if officer else username}<br/>"
        f"Role: {officer.role if officer else 'PROCUREMENT_OFFICER'}<br/>"
        f"Organization: {tenant.name if tenant else 'N/A'}<br/>"
        f"Officer ID: {officer.username if officer else username}<br/>"
        f"Report ID: BS-RPT-{report_uid[:12].upper()}<br/>"
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}<br/>"
        "Determination: As recorded in the system; this report does not infer a decision from risk findings.",
        styles["Normal"],
    ))
    if signature_data:
        match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/]+={0,2})", signature_data)
        if match:
            try:
                raw = base64.b64decode(match.group(1), validate=True)
                image = ImageReader(io.BytesIO(raw))
                width, height = image.getSize()
                scale = min(220 / max(width, 1), 76 / max(height, 1), 1)
                elements.append(Spacer(1, 6))
                elements.append(Image(io.BytesIO(raw), width=width * scale, height=height * scale))
            except Exception:
                pass
    elements.append(Paragraph("Saved officer signature (BidShield account). This is not a legally recognized e-signature.", styles["Italic"]))

def _filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:70] or "report"

def generate_quick_bidder_list_pdf(db: Session, tender_id: int, user_id: int = 1, username: str = "officer", signature_data: Optional[str] = None) -> GeneratedReport:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise ValueError(f"Tender {tender_id} not found")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=27,
        leftMargin=27,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f2b48'),
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555'),
        spaceAfter=12
    )
    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.white)
    td_style = ParagraphStyle('TD', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#222222'))
    notice_style = ParagraphStyle('Notice', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#777777'))

    elements = []
    elements.append(Paragraph("BIDSHIELD - CONSOLIDATED TENDER EVALUATION REPORT", title_style))
    elements.append(Paragraph(f"Tender Reference: <b>{tender.tender_ref}</b> | GeM Portal Ref: <b>{tender.gem_ref or 'N/A'}</b>", sub_style))
    elements.append(Paragraph(f"Title: <b>{tender.title}</b><br/>Category: {tender.category} | Department: {tender.department}<br/>Issue Date: {tender.issue_date} | Closing Date: {tender.closing_date}", sub_style))
    elements.append(Spacer(1, 10))

    # Table of bidders
    data = [
        [
            Paragraph("Bidder", th_style),
            Paragraph("Compliance", th_style),
            Paragraph("Verified Docs", th_style),
            Paragraph("Risk", th_style),
            Paragraph("Evidence", th_style),
            Paragraph("Officer Determination", th_style)
        ]
    ]

    tbs = db.query(TenderBidder).filter(TenderBidder.tender_id == tender_id).all()
    for tb in tbs:
        b = tb.bidder
        bidder_docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == b.id).all()
        verified_docs = sum(1 for document in bidder_docs if
            db.query(VerificationResult).filter(VerificationResult.document_id == document.id,
                VerificationResult.status == "VERIFIED").first())
        evidence_count = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == b.id,
            (EvidenceRecord.tender_id == tender_id) | (EvidenceRecord.tender_id.is_(None))).count()
        data.append([
            Paragraph(f"<b>{b.legal_name}</b><br/><font color='#666'>{b.state}</font>", td_style),
            Paragraph(f"{tb.compliance_status}<br/>{tb.compliance_score:.1f}%", td_style),
            Paragraph(f"{verified_docs}/{len(bidder_docs)}", td_style),
            Paragraph(tb.risk_level, td_style),
            Paragraph(str(evidence_count), td_style),
            Paragraph(tb.final_decision, td_style)
        ])

    table = Table(data, colWidths=[140, 90, 65, 75, 55, 115], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<i>Notice: BidShield-generated assessment for procurement review; this is not a government-issued certificate. Risk findings are decision support. Final determinations are made by an authorized procurement officer. Synthetic demo data is identified where applicable.</i>", notice_style))

    report_uid = uuid.uuid4().hex
    _append_signature_block(elements, db, user_id, username, report_uid, signature_data)
    footer = _draw_footer(report_uid)
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f"BidShield_Tender_Evaluation_{_filename_part(tender.tender_ref)}.pdf"

    rep = GeneratedReport(
        report_uid=report_uid,
        tender_id=tender.id,
        bidder_id=None,
        report_type="QUICK_LIST",
        filename=filename,
        file_hash=file_hash,
        file_bytes=pdf_bytes,
        generated_by_id=user_id
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)

    log_audit_event(
        db,
        action="REPORT_GENERATED",
        entity_type="REPORT",
        entity_id=rep.report_uid,
        user_id=user_id,
        username=username,
        details={"report_type": "QUICK_LIST", "tender_id": tender.id, "sha256": file_hash}
    )

    return rep

def generate_detailed_bidder_assessment_pdf(
    db: Session,
    tender_id: int,
    bidder_id: int,
    user_id: int = 1,
    username: str = "officer",
    signature_data: Optional[str] = None,
) -> GeneratedReport:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    tb = db.query(TenderBidder).filter(
        TenderBidder.tender_id == tender_id,
        TenderBidder.bidder_id == bidder_id
    ).first()

    if not tender or not bidder or not tb:
        raise ValueError("Tender, bidder or association not found")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=27,
        leftMargin=27,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0f2b48'), spaceAfter=4)
    sec_style = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#0f2b48'), spaceBefore=10, spaceAfter=4)
    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontSize=8.5, leading=10, fontName='Helvetica-Bold', textColor=colors.white)
    td_style = ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#222222'))
    notice_style = ParagraphStyle('Notice', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#666666'))

    elements = []
    elements.append(Paragraph("BIDSHIELD - INDIVIDUAL BIDDER ASSESSMENT REPORT", title_style))
    elements.append(Paragraph(f"Tender: <b>{tender.tender_ref}</b> - {tender.title}<br/>Category: {tender.category} | Evaluation period: {tender.issue_date} to {tender.closing_date}", styles['Normal']))
    elements.append(Paragraph(f"Bidder: <b>{bidder.legal_name}</b> (PAN: {bidder.pan} | GSTIN: {bidder.gstin} | Type: {bidder.enterprise_type})", styles['Normal']))
    elements.append(Spacer(1, 8))

    # Section 1: Compliance Rule Checklist
    elements.append(Paragraph("1. Deterministic Compliance Verification", sec_style))
    comp_results = db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).all()
    c_data = [[
        Paragraph("Rule Code", th_style),
        Paragraph("Requirement", th_style),
        Paragraph("Status", th_style),
        Paragraph("Explanation / Verification Notes", th_style)
    ]]
    for cr in comp_results:
        c_data.append([
            Paragraph(cr.rule_code, td_style),
            Paragraph(cr.rule_name, td_style),
            Paragraph(f"<b>{cr.status}</b>", td_style),
            Paragraph(cr.explanation, td_style)
        ])
    c_table = Table(c_data, colWidths=[65, 120, 65, 290])
    c_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
    ]))
    elements.append(c_table)
    elements.append(Spacer(1, 8))

    # Section 2: Submitted Documents & OCR Findings
    elements.append(Paragraph("2. Submitted Documents, OCR Extraction & Verification", sec_style))
    docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == bidder.id).all()
    d_data = [[
        Paragraph("Doc Type", th_style),
        Paragraph("Ver", th_style),
        Paragraph("File SHA-256 Hash", th_style),
        Paragraph("OCR Conf", th_style),
        Paragraph("Verification Status / Remarks", th_style)
    ]]
    for d in docs:
        ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
        verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()
        v_status = verif.status if verif else "PENDING"
        ocr_conf = f"{ocr.confidence:.2f}" if ocr else "N/A"
        d_data.append([
            Paragraph(d.document_type, td_style),
            Paragraph(f"v{d.version}", td_style),
            Paragraph(d.file_hash[:20] + "...", td_style),
            Paragraph(ocr_conf, td_style),
            Paragraph(f"{v_status}<br/>{escape(verif.discrepancy_notes or 'No discrepancy recorded.')}" if verif else v_status, td_style)
        ])
    d_table = Table(d_data, colWidths=[90, 35, 175, 70, 170])
    d_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
    ]))
    elements.append(d_table)
    elements.append(Spacer(1, 8))

    # Section 3: Historical Contract Performance & Causes
    elements.append(Paragraph("3. Historical Procurement Contracts & Documented Delays", sec_style))
    contracts = db.query(HistoricalContract).filter(HistoricalContract.bidder_id == bidder.id).all()
    h_data = [[
        Paragraph("Contract Ref", th_style),
        Paragraph("Procuring Entity", th_style),
        Paragraph("Value (L)", th_style),
        Paragraph("Delays", th_style),
        Paragraph("Documented Cause", th_style),
        Paragraph("Rating", th_style)
    ]]
    for h in contracts[:5]:
        h_data.append([
            Paragraph(h.contract_ref, td_style),
            Paragraph(h.procuring_entity, td_style),
            Paragraph(f"₹{h.contract_value_lakhs:.1f}", td_style),
            Paragraph(f"{h.delay_days}d", td_style),
            Paragraph(h.documented_delay_cause, td_style),
            Paragraph(f"{h.performance_rating}/5.0", td_style)
        ])
    h_table = Table(h_data, colWidths=[100, 160, 60, 50, 110, 60])
    h_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
    ]))
    elements.append(h_table)
    elements.append(Spacer(1, 8))

    # Section 4: 8-Dimensional Risk Breakdown
    elements.append(Paragraph("4. Explainable Multi-Dimensional Risk Analysis", sec_style))
    ra = db.query(RiskAssessment).filter(RiskAssessment.tender_bidder_id == tb.id).first()
    if ra and ra.dimensions:
        r_data = [[
            Paragraph("Risk Dimension", th_style),
            Paragraph("Score (0-100)", th_style),
            Paragraph("Assessment / Contributing Factor", th_style)
        ]]
        for dim, info in ra.dimensions.items():
            r_data.append([
                Paragraph(dim.replace("_", " "), td_style),
                Paragraph(f"<b>{info.get('score', 0):.1f}</b>", td_style),
                Paragraph(info.get('reason', ''), td_style)
            ])
        r_table = Table(r_data, colWidths=[130, 80, 320], repeatRows=1)
        r_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])
        ]))
        elements.append(r_table)

    elements.append(Spacer(1, 10))
    if ra:
        elements.append(Paragraph(f"Overall Risk Score: <b>{ra.overall_score:.1f}/100</b> | Risk Category: <b>{tb.risk_level}</b> | Compliance Score: <b>{tb.compliance_score:.1f}%</b> | Recorded Officer Determination: <b>{tb.final_decision}</b>", styles['Normal']))
    else:
        elements.append(Paragraph(f"Overall Risk Score: Not available | Risk Category: <b>{tb.risk_level}</b> | Compliance Score: <b>{tb.compliance_score:.1f}%</b> | Recorded Officer Determination: <b>{tb.final_decision}</b>", styles['Normal']))
    if tb.decision_notes:
        elements.append(Paragraph(f"Officer Review Notes: <i>{tb.decision_notes}</i>", styles['Normal']))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("5. Evidence Summary", sec_style))
    evidence_rows = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == bidder.id,
        (EvidenceRecord.tender_id == tender_id) | (EvidenceRecord.tender_id.is_(None))).order_by(EvidenceRecord.id.asc()).limit(100).all()
    e_data = [[Paragraph("Evidence", th_style), Paragraph("Source Reference", th_style), Paragraph("Confidence", th_style)]]
    for evidence in evidence_rows:
        e_data.append([Paragraph(f"<b>{escape(evidence.claim_type)}</b><br/>{escape(evidence.evidence_text[:700])}", td_style),
                       Paragraph(escape(evidence.source_reference), td_style), Paragraph(f"{evidence.confidence:.2f}", td_style)])
    if len(e_data) == 1:
        e_data.append([Paragraph("No linked evidence records are available.", td_style), Paragraph("N/A", td_style), Paragraph("N/A", td_style)])
    e_table = Table(e_data, colWidths=[300, 170, 70], repeatRows=1)
    e_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2b48')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0d7de')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')])]))
    elements.append(e_table)

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<i>Important Notice: This BidShield-generated assessment is for authorized procurement review and is not a government-issued certificate or legally recognized e-signature. AI findings are decision support; final procurement determinations remain with the authorized Procurement Officer.</i>", notice_style))

    report_uid = uuid.uuid4().hex
    _append_signature_block(elements, db, user_id, username, report_uid, signature_data)
    footer = _draw_footer(report_uid)
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f"BidShield_Bidder_Assessment_{_filename_part(bidder.legal_name)}.pdf"

    rep = GeneratedReport(
        report_uid=report_uid,
        tender_id=tender.id,
        bidder_id=bidder.id,
        report_type="DETAILED_ASSESSMENT",
        filename=filename,
        file_hash=file_hash,
        file_bytes=pdf_bytes,
        generated_by_id=user_id
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)

    log_audit_event(
        db,
        action="REPORT_GENERATED",
        entity_type="REPORT",
        entity_id=rep.report_uid,
        user_id=user_id,
        username=username,
        details={"report_type": "DETAILED_ASSESSMENT", "tender_id": tender.id, "bidder_id": bidder.id, "sha256": file_hash}
    )

    return rep
