import io
import hashlib
import uuid
import base64
import re
from datetime import datetime, timezone
from typing import Optional, List
from app.core.sanitize import escape_text as escape
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image, KeepInFrame
)
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from app.models.entities import (
    Tender, TenderRequirement, Bidder, TenderBidder, BidderDocument, OCRResult,
    VerificationResult, ComplianceResult, RiskAssessment,
    HistoricalContract, EvidenceRecord, GeneratedReport, User, Tenant
)
from app.services.audit_service import log_audit_event

# ─── Shared layout constants ──────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

ACCENT = colors.HexColor('#0f2b48')     # deep procurement navy
RULE_GREY = colors.HexColor('#d0d7de')
ZEBRA = colors.HexColor('#f6f8fa')
MUTED = colors.HexColor('#555555')


def _base_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=17,
                                 leading=21, textColor=ACCENT, spaceAfter=4)
    sub_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontSize=9.5,
                               leading=13, textColor=MUTED, spaceAfter=6)
    meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontSize=8.5,
                                leading=11.5, textColor=colors.HexColor('#333333'))
    sec_style = ParagraphStyle('SecTitle', parent=styles['Heading2'], fontSize=11.5,
                               leading=15, textColor=ACCENT, spaceBefore=12, spaceAfter=4)
    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontSize=8.5, leading=10,
                              fontName='Helvetica-Bold', textColor=colors.white)
    td_style = ParagraphStyle('TD', parent=styles['Normal'], fontSize=8, leading=10,
                              textColor=colors.HexColor('#222222'))
    notice_style = ParagraphStyle('Notice', parent=styles['Normal'], fontSize=7.5,
                                  leading=9.5, textColor=colors.HexColor('#666666'))
    return title_style, sub_style, meta_style, sec_style, th_style, td_style, notice_style


def _meta_table(rows: List[List[str]], th, td) -> Table:
    """Two-column information block kept together as one unit."""
    data = [[Paragraph(f"<b>{escape(k)}</b>", th), Paragraph(escape(v), td)] for k, v in rows]
    t = Table(data, colWidths=[45 * mm, CONTENT_W - 45 * mm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ZEBRA),
        ('GRID', (0, 0), (-1, -1), 0.5, RULE_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _styled_table(header: List[Paragraph], body: List[List[Paragraph]], col_widths, repeat_header: bool = True) -> Table:
    """Standard document table: repeating header row, zebra rows, full grid."""
    data = [header] + body
    t = Table(data, colWidths=col_widths, repeatRows=1 if repeat_header else 0)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('GRID', (0, 0), (-1, -1), 0.5, RULE_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _draw_footer(report_uid: str, report_label: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE_GREY)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(MARGIN, 10 * mm,
                          f"BidShield Procurement Assessment Report · {report_label} · ID BS-RPT-{report_uid[:12].upper()}")
        canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"Page {doc.page}")
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawCentredString(PAGE_W / 2, 6 * mm,
                                 "AI-assisted decision support. Final determinations are made by the authorized Procurement Officer.")
        canvas.restoreState()
    return draw


def _officer_block(db: Session, user_id: int, username: str, report_uid: str,
                   signature_data: Optional[str], th, td) -> List:
    """Officer determination + signature, wrapped so it never splits across pages."""
    officer = db.query(User).filter(User.id == user_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == officer.tenant_id).first() if officer else None
    styles = getSampleStyleSheet()
    body = [
        f"Officer: {officer.full_name if officer else username}",
        f"Role: {officer.role if officer else 'PROCUREMENT_OFFICER'}",
        f"Organization: {tenant.name if tenant else 'N/A'}",
        f"Officer ID: {officer.username if officer else username}",
        f"Report ID: BS-RPT-{report_uid[:12].upper()}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "Determination: As recorded in the system; this report does not infer a decision from risk findings.",
    ]
    group: List = [Paragraph("Officer Information and Determination", styles["Heading2"])]
    rows = [(part.split(':', 1)[0], part.split(':', 1)[1].strip()) for part in body if ':' in part]
    group.append(_meta_table(rows, th, td))
    # Keep a plain-text Report ID line for downstream text verification/QA.
    group.append(Paragraph(f"Report ID: BS-RPT-{report_uid[:12].upper()}", styles["Normal"]))

    if signature_data:
        match = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/]+={0,2})", signature_data)
        if match:
            try:
                raw = base64.b64decode(match.group(1), validate=True)
                image = ImageReader(io.BytesIO(raw))
                width, height = image.getSize()
                scale = min(200 / max(width, 1), 66 / max(height, 1), 1)
                group.append(Spacer(1, 8))
                group.append(Paragraph("<b>Officer Signature</b>", styles["Normal"]))
                group.append(Spacer(1, 2))
                group.append(Image(io.BytesIO(raw), width=width * scale, height=height * scale))
            except Exception:
                pass
    group.append(Paragraph(
        "Saved officer signature (BidShield account). This is not a legally recognized e-signature.",
        styles["Italic"]))
    return [KeepTogether(group)]


def _report_header(tender: Tender, report_title: str, sub_lines: List[str],
                   title_style, sub_style, th, td) -> List:
    elements = [
        Paragraph(f"BIDSHIELD — {report_title}", title_style),
        Paragraph("<br/>".join(escape(l) for l in sub_lines), sub_style),
        Spacer(1, 4),
    ]
    meta_rows = [
        ("Tender Reference", tender.tender_ref),
        ("Tender Title", tender.title),
        ("Department / Organization", tender.department),
        ("Category", tender.category),
        ("Issue Date", tender.issue_date),
        ("Submission Due Date", tender.closing_date),
        ("Generated (UTC)", datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')),
    ]
    elements.append(_meta_table(meta_rows, th, td))
    elements.append(Spacer(1, 8))
    return elements


def _filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:70] or "report"


# ══════════════════════════════════════════════════════════════════════════
# CONSOLIDATED TENDER REPORT
# ══════════════════════════════════════════════════════════════════════════
def generate_quick_bidder_list_pdf(db: Session, tender_id: int, user_id: int = 1,
                                   username: str = "officer",
                                   signature_data: Optional[str] = None) -> GeneratedReport:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise ValueError(f"Tender {tender_id} not found")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=MARGIN, leftMargin=MARGIN,
                            topMargin=16 * mm, bottomMargin=18 * mm)
    title_style, sub_style, meta_style, sec_style, th_style, td_style, notice_style = _base_styles()

    elements: List = _report_header(
        tender, "CONSOLIDATED TENDER EVALUATION REPORT",
        [f"Report: BidShield Procurement Assessment Report (Consolidated)"],
        title_style, sub_style, th_style, td_style)

    # ── Section 1: Approved requirements ─────────────────────────────────
    requirements = db.query(TenderRequirement).filter(
        TenderRequirement.tender_id == tender.id).order_by(TenderRequirement.id.asc()).all()
    approved = [r for r in requirements if r.approval_status in ("APPROVED", "MODIFIED")]

    sec1 = [Paragraph("1. Approved Tender Requirements", sec_style)]
    if approved:
        rows = [[
            Paragraph("Code", th_style), Paragraph("Requirement", th_style),
            Paragraph("Type", th_style), Paragraph("Mandate", th_style),
        ]]
        for r in approved:
            rows.append([
                Paragraph(escape(r.code), td_style),
                Paragraph(escape(r.name), td_style),
                Paragraph(escape(r.requirement_type), td_style),
                Paragraph(escape(r.description[:400]), td_style),
            ])
        sec1.append(_styled_table(rows[0], rows[1:], [22 * mm, 55 * mm, 24 * mm, CONTENT_W - 101 * mm]))
    else:
        sec1.append(Paragraph("No officer-approved requirements were recorded for this tender.",
                              td_style))
    elements.append(KeepTogether(sec1[:2]))
    if len(sec1) > 2:
        elements.extend(sec1[2:])

    # ── Section 2: Bidder submission + compliance + risk summary ────────
    tbs = db.query(TenderBidder).filter(TenderBidder.tender_id == tender_id).all()
    sec2: List = [Paragraph("2. Bidder Submission & Compliance Summary", sec_style)]
    if tbs:
        rows = [[
            Paragraph("Bidder", th_style),
            Paragraph("Compliance", th_style),
            Paragraph("Verified Docs", th_style),
            Paragraph("Risk", th_style),
            Paragraph("Evidence", th_style),
            Paragraph("Officer Determination", th_style),
        ]]
        for tb in tbs:
            b = tb.bidder
            bidder_docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == b.id).all()
            verified_docs = sum(1 for d in bidder_docs if
                db.query(VerificationResult).filter(VerificationResult.document_id == d.id,
                    VerificationResult.status == "VERIFIED").first())
            evidence_count = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == b.id,
                (EvidenceRecord.tender_id == tender_id) | (EvidenceRecord.tender_id.is_(None))).count()
            rows.append([
                Paragraph(f"<b>{escape(b.legal_name)}</b><br/><font color='#666666'>{escape(b.state or '')}</font>", td_style),
                Paragraph(f"{escape(tb.compliance_status or 'PENDING')}<br/>{tb.compliance_score:.1f}%", td_style),
                Paragraph(f"{verified_docs}/{len(bidder_docs)}", td_style),
                Paragraph(escape(tb.risk_level or 'PENDING'), td_style),
                Paragraph(str(evidence_count), td_style),
                Paragraph(escape(tb.final_decision or 'PENDING'), td_style),
            ])
        sec2.append(_styled_table(rows[0], rows[1:],
                                  [52 * mm, 28 * mm, 22 * mm, 26 * mm, 18 * mm, CONTENT_W - 146 * mm]))
    else:
        sec2.append(Paragraph("No bidder submissions have been received for this tender.", td_style))
    elements.append(KeepTogether(sec2[:2]))
    if len(sec2) > 2:
        elements.extend(sec2[2:])

    # ── Section 3: Evidence / document summary ──────────────────────────
    total_docs = db.query(BidderDocument).join(Bidder, Bidder.id == BidderDocument.bidder_id).filter(
        Bidder.tenant_id == tender.tenant_id,
        (BidderDocument.tender_id == tender_id) | (BidderDocument.tender_id.is_(None))).count()
    sec3 = KeepTogether([
        Paragraph("3. Evidence / Document Summary", sec_style),
        Paragraph(
            f"Documents on record for this tender: <b>{total_docs}</b> (all versions). "
            f"Participating bidders: <b>{len(tbs)}</b>. "
            f"Officer-approved requirements: <b>{len(approved)}</b> of {len(requirements)} tracked.",
            td_style),
    ])
    elements.append(sec3)

    # ── Section 4: Declaration ──────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("4. Declaration", sec_style),
        Paragraph(
            "<i>This BidShield Procurement Assessment Report consolidates system-recorded findings for "
            "authorized procurement review. It is not a government-issued certificate. AI-derived findings "
            "(OCR, compliance, risk) are decision support only; the final procurement determination rests "
            "exclusively with the authorized Procurement Officer. Anomaly findings indicate an unusual "
            "pattern, not proven wrongdoing. Synthetic demo data is identified where applicable.</i>",
            notice_style),
    ]))

    # ── Section 5: Officer signature (never split) ──────────────────────
    report_uid = uuid.uuid4().hex
    elements.extend(_officer_block(db, user_id, username, report_uid, signature_data, th_style, td_style))

    footer = _draw_footer(report_uid, "Consolidated Tender Evaluation")
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


# ══════════════════════════════════════════════════════════════════════════
# INDIVIDUAL BIDDER ASSESSMENT REPORT
# ══════════════════════════════════════════════════════════════════════════
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
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=MARGIN, leftMargin=MARGIN,
                            topMargin=16 * mm, bottomMargin=18 * mm)
    title_style, sub_style, meta_style, sec_style, th_style, td_style, notice_style = _base_styles()

    elements: List = _report_header(
        tender, "INDIVIDUAL BIDDER ASSESSMENT REPORT",
        ["Report: BidShield Procurement Assessment Report (Individual Bidder)"],
        title_style, sub_style, th_style, td_style)

    # ── Section 1: Bidder information ───────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("1. Bidder Information", sec_style),
        _meta_table([
            ("Legal Name", bidder.legal_name),
            ("Trade Name", bidder.trade_name or "N/A"),
            ("PAN", bidder.pan or "N/A"),
            ("GSTIN", bidder.gstin or "N/A"),
            ("Enterprise Type", f"{bidder.enterprise_type or 'Unknown'}{' (Startup)' if bidder.is_startup else ''}"),
            ("State / District", f"{bidder.state or 'N/A'} / {bidder.district or 'N/A'}"),
            ("Contact", f"{bidder.contact_person or 'N/A'} · {bidder.contact_email or 'N/A'}"),
        ], th_style, td_style),
    ]))

    # ── Section 2: Document inventory + OCR summary ─────────────────────
    docs = db.query(BidderDocument).filter(BidderDocument.bidder_id == bidder.id).all()
    sec2: List = [Paragraph("2. Document Inventory & OCR / Extraction Summary", sec_style)]
    if docs:
        rows = [[
            Paragraph("Doc Type", th_style),
            Paragraph("Ver", th_style),
            Paragraph("Filename", th_style),
            Paragraph("SHA-256 (prefix)", th_style),
            Paragraph("OCR Conf", th_style),
            Paragraph("Verification", th_style),
        ]]
        for d in docs:
            ocr = db.query(OCRResult).filter(OCRResult.document_id == d.id).first()
            verif = db.query(VerificationResult).filter(VerificationResult.document_id == d.id).first()
            rows.append([
                Paragraph(escape(d.document_type), td_style),
                Paragraph(f"v{d.version}{'*' if d.is_active else ''}", td_style),
                Paragraph(escape(d.filename[:60]), td_style),
                Paragraph(escape((d.file_hash or '')[:20]) + "…", td_style),
                Paragraph(f"{ocr.confidence:.2f}" if ocr else "N/A", td_style),
                Paragraph(escape(verif.status if verif else "PENDING"), td_style),
            ])
        sec2.append(_styled_table(rows[0], rows[1:],
                                  [24 * mm, 12 * mm, 62 * mm, 36 * mm, 18 * mm, CONTENT_W - 152 * mm]))
        sec2.append(Paragraph("* denotes the active version; superseded versions are retained for audit.",
                              notice_style))
    else:
        sec2.append(Paragraph("No bidder documents have been uploaded.", td_style))
    elements.append(KeepTogether(sec2[:2]))
    if len(sec2) > 2:
        elements.extend(sec2[2:])

    # ── Section 3: Requirement-wise compliance ──────────────────────────
    comp_results = db.query(ComplianceResult).filter(ComplianceResult.tender_bidder_id == tb.id).all()
    sec3: List = [Paragraph("3. Requirement-wise Compliance", sec_style)]
    if comp_results:
        rows = [[
            Paragraph("Rule Code", th_style),
            Paragraph("Requirement", th_style),
            Paragraph("Status", th_style),
            Paragraph("Explanation / Verification Notes", th_style),
        ]]
        for cr in comp_results:
            rows.append([
                Paragraph(escape(cr.rule_code), td_style),
                Paragraph(escape(cr.rule_name), td_style),
                Paragraph(f"<b>{escape(cr.status)}</b>", td_style),
                Paragraph(escape(cr.explanation), td_style),
            ])
        sec3.append(_styled_table(rows[0], rows[1:],
                                  [24 * mm, 45 * mm, 24 * mm, CONTENT_W - 93 * mm]))
    else:
        sec3.append(Paragraph("No compliance evaluation has been run for this bidder yet.", td_style))
    elements.append(KeepTogether(sec3[:2]))
    if len(sec3) > 2:
        elements.extend(sec3[2:])

    # ── Section 4: Risk analysis (dimension + explanation kept together) ─
    ra = db.query(RiskAssessment).filter(RiskAssessment.tender_bidder_id == tb.id).first()
    elements.append(Paragraph("4. Risk Analysis (Explainable, 8 Dimensions)", sec_style))
    if ra and ra.dimensions:
        elements.append(Paragraph(
            f"Overall Risk Score: <b>{ra.overall_score:.1f}/100</b> · Category: <b>{escape(tb.risk_level or 'N/A')}</b> · "
            f"Data Sufficiency: <b>{escape(ra.data_sufficiency)}</b><br/>{escape(ra.explanation)}",
            td_style))
        elements.append(Spacer(1, 5))
        rows = [[
            Paragraph("Risk Dimension", th_style),
            Paragraph("Score (0-100)", th_style),
            Paragraph("Assessment / Contributing Factor", th_style),
        ]]
        for dim, info in ra.dimensions.items():
            rows.append([
                Paragraph(escape(str(dim).replace("_", " ").title()), td_style),
                Paragraph(f"<b>{info.get('score', 0):.1f}</b>", td_style),
                Paragraph(escape(str(info.get('reason', ''))), td_style),
            ])
        elements.append(_styled_table(rows[0], rows[1:],
                                      [45 * mm, 22 * mm, CONTENT_W - 67 * mm]))
    else:
        elements.append(Paragraph(
            "No risk assessment is available yet. Run the analysis pipeline for this bidder.",
            td_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "<i>Anomaly findings indicate an unusual pattern detected; they do not constitute a finding of fraud.</i>",
        notice_style))

    # ── Section 5: Historical performance ───────────────────────────────
    contracts = db.query(HistoricalContract).filter(HistoricalContract.bidder_id == bidder.id).all()
    sec5: List = [Paragraph("5. Historical Procurement Performance", sec_style)]
    if contracts:
        rows = [[
            Paragraph("Contract Ref", th_style),
            Paragraph("Procuring Entity", th_style),
            Paragraph("Value (L)", th_style),
            Paragraph("Delay (d)", th_style),
            Paragraph("Documented Cause", th_style),
            Paragraph("Rating", th_style),
        ]]
        for h in contracts[:8]:
            rows.append([
                Paragraph(escape(h.contract_ref), td_style),
                Paragraph(escape(h.procuring_entity), td_style),
                Paragraph(f"{h.contract_value_lakhs:.1f}", td_style),
                Paragraph(str(h.delay_days), td_style),
                Paragraph(escape(h.documented_delay_cause), td_style),
                Paragraph(f"{h.performance_rating}/5.0", td_style),
            ])
        sec5.append(_styled_table(rows[0], rows[1:],
                                  [30 * mm, 52 * mm, 18 * mm, 16 * mm, 40 * mm, CONTENT_W - 156 * mm]))
    else:
        sec5.append(Paragraph(
            "No historical contract records are on file. Data sufficiency is limited; risk "
            "assessment is marked INSUFFICIENT EVIDENCE rather than LOW RISK.", td_style))
    elements.append(KeepTogether(sec5[:2]))
    if len(sec5) > 2:
        elements.extend(sec5[2:])

    # ── Section 6: Evidence summary ─────────────────────────────────
    evidence_rows = db.query(EvidenceRecord).filter(EvidenceRecord.bidder_id == bidder.id,
        (EvidenceRecord.tender_id == tender_id) | (EvidenceRecord.tender_id.is_(None))).order_by(EvidenceRecord.id.asc()).limit(60).all()
    sec6: List = [Paragraph("6. Evidence Summary", sec_style)]
    if evidence_rows:
        ev_body = []
        for evidence in evidence_rows:
            ev_body.append([
                Paragraph(f"<b>{escape(evidence.claim_type)}</b><br/>{escape(evidence.evidence_text[:400])}", td_style),
                Paragraph(escape(evidence.source_reference), td_style),
                Paragraph(f"{evidence.confidence:.2f}", td_style),
            ])
        sec6.append(_styled_table(
            [Paragraph("Evidence", th_style), Paragraph("Source Reference", th_style), Paragraph("Confidence", th_style)],
            ev_body, [CONTENT_W - 92 * mm, 62 * mm, 30 * mm]))
    else:
        sec6.append(Paragraph("No linked evidence records are available for this bidder.", td_style))
    elements.append(KeepTogether(sec6[:2]))
    if len(sec6) > 2:
        elements.extend(sec6[2:])

    # ── Section 7: Officer determination ────────────────────────────
    det_rows = [
        ("Recorded Officer Determination", tb.final_decision or "PENDING"),
        ("Compliance Status", f"{tb.compliance_status or 'PENDING'} ({tb.compliance_score:.1f}%)"),
        ("Decision Notes", tb.decision_notes or "—"),
    ]
    if tb.decided_at:
        det_rows.append(("Decided At", tb.decided_at.strftime('%Y-%m-%d %H:%M UTC')))
    elements.append(KeepTogether([
        Paragraph("6. Officer Determination", sec_style),
        _meta_table(det_rows, th_style, td_style),
    ]))

    # ── Section 8: Declaration ──────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("7. Declaration", sec_style),
        Paragraph(
            "<i>This BidShield Procurement Assessment Report presents system-recorded findings for the named "
            "bidder in the context of the referenced tender. It is for authorized procurement review and is not "
            "a government-issued certificate or legally recognized e-signature. AI findings are decision support; "
            "the final procurement determination rests exclusively with the authorized Procurement Officer.</i>",
            notice_style),
    ]))

    # ── Section 9: Officer signature (never split) ──────────────────────
    report_uid = uuid.uuid4().hex
    elements.extend(_officer_block(db, user_id, username, report_uid, signature_data, th_style, td_style))

    footer = _draw_footer(report_uid, "Individual Bidder Assessment")
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
