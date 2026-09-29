import io
import os
import hashlib
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon, Group

def create_national_emblem_drawing(width=60, height=60):
    """Draw a vector representation of an official government seal / crest."""
    d = Drawing(width, height)
    # Outer circle
    d.add(Circle(width/2, height/2, 26, strokeColor=colors.HexColor('#0f2b48'), fillColor=colors.HexColor('#f8fafc'), strokeWidth=1.5))
    d.add(Circle(width/2, height/2, 23, strokeColor=colors.HexColor('#0f2b48'), fillColor=None, strokeWidth=0.5))
    # Ashoka Pillar / Emblem stylized central shape
    d.add(Rect(width/2 - 6, height/2 - 12, 12, 18, fillColor=colors.HexColor('#0f2b48'), strokeColor=None))
    d.add(Circle(width/2, height/2 + 8, 7, fillColor=colors.HexColor('#0f2b48'), strokeColor=None))
    d.add(Circle(width/2 - 7, height/2 + 5, 5, fillColor=colors.HexColor('#0f2b48'), strokeColor=None))
    d.add(Circle(width/2 + 7, height/2 + 5, 5, fillColor=colors.HexColor('#0f2b48'), strokeColor=None))
    # Base wheel
    d.add(Circle(width/2, height/2 - 16, 4, fillColor=None, strokeColor=colors.HexColor('#0f2b48'), strokeWidth=1))
    return d

def create_qr_code_drawing(data_str="SYNTHETIC-DEMO-NOT-VALID", size=55):
    """Draw a realistic looking vector QR Code / 2D Barcode box."""
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, fillColor=colors.white, strokeColor=colors.HexColor('#334155'), strokeWidth=1))
    # 3 Corner squares (QR markers)
    d.add(Rect(3, size - 17, 14, 14, fillColor=colors.HexColor('#0f172a'), strokeColor=None))
    d.add(Rect(5, size - 15, 10, 10, fillColor=colors.white, strokeColor=None))
    d.add(Rect(7, size - 13, 6, 6, fillColor=colors.HexColor('#0f172a'), strokeColor=None))

    d.add(Rect(size - 17, size - 17, 14, 14, fillColor=colors.HexColor('#0f172a'), strokeColor=None))
    d.add(Rect(size - 15, size - 15, 10, 10, fillColor=colors.white, strokeColor=None))
    d.add(Rect(size - 13, size - 13, 6, 6, fillColor=colors.HexColor('#0f172a'), strokeColor=None))

    d.add(Rect(3, 3, 14, 14, fillColor=colors.HexColor('#0f172a'), strokeColor=None))
    d.add(Rect(5, 5, 10, 10, fillColor=colors.white, strokeColor=None))
    d.add(Rect(7, 7, 6, 6, fillColor=colors.HexColor('#0f172a'), strokeColor=None))

    # Grid pixel pattern
    for r in range(4):
        for c in range(5):
            if (r + c) % 2 == 0:
                d.add(Rect(20 + c * 5, 5 + r * 6, 4, 4, fillColor=colors.HexColor('#1e293b'), strokeColor=None))
    return d

def create_official_stamp_drawing(org_name="BIDSHIELD DEMO", text="DEMO ONLY", color_hex="#1d4ed8"):
    """Draw a round rubber stamp / seal."""
    d = Drawing(75, 75)
    c = colors.HexColor(color_hex)
    d.add(Circle(37.5, 37.5, 34, strokeColor=c, fillColor=None, strokeWidth=1.5))
    d.add(Circle(37.5, 37.5, 31, strokeColor=c, fillColor=None, strokeWidth=0.7))
    d.add(String(37.5, 45, text, textAnchor='middle', fontName='Helvetica-Bold', fontSize=8, fillColor=c))
    d.add(String(37.5, 35, "VERIFIED", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=c))
    d.add(String(37.5, 25, org_name[:12], textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=c))
    return d

def generate_realistic_document(
    doc_type: str,
    bidder_name: str,
    identifier_val: str,
    extra_fields: dict,
    is_degraded: bool = False
) -> bytes:
    """
    Generate synthetic examples styled for demo scenarios. A visible disclaimer
    identifies each page as unofficial and invalid for real procurement use.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=32,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()

    # Base typography styles
    h1_style = ParagraphStyle('H1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=17, textColor=colors.HexColor('#0f2b48'), alignment=1)
    h2_style = ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#1e293b'), alignment=1)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#475569'), alignment=1)
    
    label_style = ParagraphStyle('Lbl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=13, textColor=colors.HexColor('#1e293b'))
    val_style = ParagraphStyle('Val', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#0f172a'))
    val_mono = ParagraphStyle('ValMono', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#1e40af'))
    
    notice_style = ParagraphStyle('Notice', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.HexColor('#991b1b'), alignment=1)
    watermark_style = ParagraphStyle('WM', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#94a3b8'), alignment=1)

    elements = []
    elements.append(Paragraph("BIDSHIELD SYNTHETIC DEMO ONLY — NOT ISSUED BY ANY AUTHORITY — NOT VALID FOR OFFICIAL USE", notice_style))
    elements.append(Spacer(1, 8))

    # 1. PAN CARD FORMAT
    if doc_type == "PAN":
        # Header banner
        header_data = [
            [
                Paragraph("<b>आयकर विभाग</b><br/><b>INCOME TAX DEPARTMENT</b>", ParagraphStyle('Hindi', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#0f2b48'))),
                create_national_emblem_drawing(50, 50),
                Paragraph("<b>भारत सरकार</b><br/><b>GOVT. OF INDIA</b>", ParagraphStyle('Eng', parent=styles['Normal'], fontSize=9, leading=12, alignment=2, textColor=colors.HexColor('#0f2b48')))
            ]
        ]
        ht = Table(header_data, colWidths=[200, 140, 200])
        ht.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (1,0), (1,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(ht)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f2b48'), spaceAfter=10, spaceBefore=4))

        elements.append(Paragraph("स्थायी लेखा संख्या कार्ड / PERMANENT ACCOUNT NUMBER CARD", h2_style))
        elements.append(Spacer(1, 10))

        # Main PAN Card container box
        pan_rows = [
            [Paragraph("स्थायी लेखा संख्या / PAN :", label_style), Paragraph(f"<b>{identifier_val}</b>", val_mono), create_qr_code_drawing(f"PAN:{identifier_val}", 50)],
            [Paragraph("नाम / Name :", label_style), Paragraph(bidder_name, val_style), ""],
            [Paragraph("पिता / संस्था का नाम :", label_style), Paragraph(extra_fields.get("Father / Org Name", "DIRECTOR / INCORPORATED ENTITY"), val_style), ""],
            [Paragraph("निगमन की तिथि / Date of Inc. :", label_style), Paragraph(extra_fields.get("Date of Issue", "2016-04-12"), val_style), ""],
            [Paragraph("स्थिति / Status :", label_style), Paragraph(extra_fields.get("Status", "OPERATIVE / ACTIVE"), val_style), create_official_stamp_drawing("INCOME TAX", "OPERATIVE", "#15803d")]
        ]
        pan_table = Table(pan_rows, colWidths=[160, 270, 110])
        pan_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#0284c7')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9ff')),
            ('GRID', (0,0), (1,-1), 0.5, colors.HexColor('#bae6fd')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('SPAN', (2,0), (2,1)),
            ('SPAN', (2,3), (2,4)),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(pan_table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("Certified digitally verifiable under National E-Governance Services (PAN API NSDL/UTIITSL).", watermark_style))

    # 2. GST REGISTRATION CERTIFICATE (FORM GST REG-06)
    elif doc_type == "GST":
        elements.append(create_national_emblem_drawing(50, 50))
        elements.append(Paragraph("<b>Government of India</b>", h2_style))
        elements.append(Paragraph("<b>Form GST REG-06</b>", h1_style))
        elements.append(Paragraph("[See Rule 10(1)]<br/><b>Registration Certificate</b>", sub_style))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8, spaceBefore=4))

        gst_table_data = [
            [Paragraph("<b>Registration Number (GSTIN) :</b>", label_style), Paragraph(f"<b>{identifier_val}</b>", val_mono)],
            [Paragraph("<b>Legal Name :</b>", label_style), Paragraph(bidder_name, val_style)],
            [Paragraph("<b>Trade Name :</b>", label_style), Paragraph(extra_fields.get("Trade Name", bidder_name), val_style)],
            [Paragraph("<b>Constitution of Business :</b>", label_style), Paragraph(extra_fields.get("Constitution", "Private Limited Company"), val_style)],
            [Paragraph("<b>Address of Principal Place of Business :</b>", label_style), Paragraph(extra_fields.get("Address", "Registered Industrial Facility"), val_style)],
            [Paragraph("<b>Date of Validity :</b>", label_style), Paragraph(f"From <b>{extra_fields.get('Date of Validity', '01/07/2017')}</b> To <b>Perpetual / Active</b>", val_style)],
            [Paragraph("<b>Type of Registration :</b>", label_style), Paragraph("Regular Taxpayer", val_style)],
            [Paragraph("<b>Registration Status :</b>", label_style), Paragraph(f"<b>{extra_fields.get('Registration Status', 'ACTIVE')}</b>", val_style)],
            [Paragraph("<b>Jurisdictional Authority :</b>", label_style), Paragraph("Central Goods and Services Tax Range / State Division", val_style)]
        ]

        if is_degraded:
            elements.append(Paragraph("⚠️ [DOCUMENT SCAN ARTIFACT: LOW RESOLUTION / DEGRADED TELE-FACSIMILE]", notice_style))
            elements.append(Spacer(1, 4))

        gt = Table(gst_table_data, colWidths=[190, 350])
        gt.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0f2b48')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(gt)
        elements.append(Spacer(1, 10))

        # Footer with QR and Signature
        ft_data = [
            [
                create_qr_code_drawing(f"GSTIN:{identifier_val}", 50),
                Paragraph("<b>Digitally Signed By</b><br/>Superintendent / Jurisdictional Officer<br/>Goods and Services Tax Network (GSTN)<br/>Government of India", ParagraphStyle('Sign', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#334155'))),
                create_official_stamp_drawing("GSTN AUTHORITY", "APPROVED", "#047857")
            ]
        ]
        ft = Table(ft_data, colWidths=[70, 360, 110])
        ft.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(ft)

    # 3. UDYAM REGISTRATION CERTIFICATE (MSME)
    elif doc_type == "UDYAM":
        elements.append(create_national_emblem_drawing(45, 45))
        elements.append(Paragraph("<b>भारत सरकार / GOVERNMENT OF INDIA</b>", h2_style))
        elements.append(Paragraph("<b>सूक्ष्म, लघु एवं मध्यम उद्यम मंत्रालय</b><br/><b>MINISTRY OF MICRO, SMALL & MEDIUM ENTERPRISES</b>", h1_style))
        elements.append(Paragraph("<b>UDYAM REGISTRATION CERTIFICATE</b>", ParagraphStyle('UdyamTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#047857'), alignment=1)))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#10b981'), spaceAfter=8, spaceBefore=4))

        udyam_data = [
            [Paragraph("<b>UDYAM REGISTRATION NUMBER :</b>", label_style), Paragraph(f"<b>{identifier_val}</b>", val_mono)],
            [Paragraph("<b>NAME OF ENTERPRISE :</b>", label_style), Paragraph(f"<b>{bidder_name}</b>", val_style)],
            [Paragraph("<b>TYPE OF ENTERPRISE :</b>", label_style), Paragraph(f"<b>{extra_fields.get('Enterprise Type', 'Small')} Enterprise</b>", val_style)],
            [Paragraph("<b>MAJOR ACTIVITY :</b>", label_style), Paragraph(extra_fields.get("Major Activity", "SERVICES & MANUFACTURING"), val_style)],
            [Paragraph("<b>SOCIAL CATEGORY / GENDER :</b>", label_style), Paragraph("GENERAL / MALE & FEMALE PROMOTERS", val_style)],
            [Paragraph("<b>DATE OF INCORPORATION / REG :</b>", label_style), Paragraph(extra_fields.get("Date of Inc", "2016-04-12"), val_style)],
            [Paragraph("<b>NATIONAL INDUSTRY CLASSIFICATION (NIC) :</b>", label_style), Paragraph("62011 - Writing, modifying, testing of computer hardware/software systems", val_style)],
            [Paragraph("<b>EXPIRY / VALIDITY DATE :</b>", label_style), Paragraph(f"<b>{extra_fields.get('Expiry Date', '2029-12-31')}</b> (Status: {extra_fields.get('Status', 'ACTIVE')})", val_style)]
        ]
        ut = Table(udyam_data, colWidths=[200, 340])
        ut.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#047857')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0fdf4')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#bbf7d0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(ut)
        elements.append(Spacer(1, 10))

        ft_data = [
            [
                create_qr_code_drawing(f"UDYAM:{identifier_val}", 48),
                Paragraph("<b>Ministry of MSME, Govt of India</b><br/>Official Portal: https://udyamregistration.gov.in<br/>For any assistance, contact National MSME Helpline.", ParagraphStyle('SignU', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#334155'))),
                create_official_stamp_drawing("MINISTRY MSME", "REGISTERED", "#047857")
            ]
        ]
        ft = Table(ft_data, colWidths=[65, 375, 100])
        ft.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(ft)

    # 4. OEM MANUFACTURER AUTHORIZATION FORM (MAF)
    elif doc_type == "OEM":
        elements.append(Paragraph("<b>GLOBAL TECHNOLOGY & OEM SYSTEMS (INDIA) PVT LTD</b>", ParagraphStyle('OEMHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#1e3a8a'))))
        elements.append(Paragraph("Enterprise Solutions Division • Cyber City, Phase-II, Gurugram / Bengaluru", sub_style))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1e3a8a'), spaceAfter=10, spaceBefore=4))

        elements.append(Paragraph("<b>MANUFACTURER AUTHORIZATION FORM (MAF)</b>", h1_style))
        elements.append(Paragraph("Ref No: <b>" + identifier_val + "</b>", ParagraphStyle('Ref', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#475569'))))
        elements.append(Spacer(1, 10))

        maf_body = f"""
        <b>To,</b><br/>
        The Procurement Authority / Government e-Marketplace (GeM)<br/>
        Ministry of Electronics & Information Technology / Procuring Entity<br/><br/>
        <b>Subject: OEM Authorization for GeM Procurement Tenders</b><br/><br/>
        Dear Sir / Madam,<br/><br/>
        We, <b>Global OEM Technologies India</b>, who are established and reputable manufacturers of enterprise hardware and software systems, having manufacturing and assembly facilities at Pune / Chennai, do hereby authorize <b>{bidder_name}</b> to submit a bid, negotiate and conclude the contract with you against the subject tender.<br/><br/>
        We hereby extend our full guarantee, comprehensive on-site warranty (3 to 5 Years), and 24x7 supply of genuine spare parts and technical support as per the conditions of the contract for the goods and services offered by the above firm.<br/><br/>
        <b>OEM Authorization ID:</b> <font color='#1e40af'><b>{identifier_val}</b></font><br/>
        <b>Product Scope:</b> {extra_fields.get('Product Category', 'Enterprise Equipment & Associated Peripherals')}<br/>
        <b>Validity Period:</b> Valid Until <b>{extra_fields.get('Valid Until', '2028-12-31')}</b>
        """
        elements.append(Paragraph(maf_body, ParagraphStyle('MAFBody', parent=styles['Normal'], fontSize=9.5, leading=14, textColor=colors.HexColor('#1e293b'))))
        elements.append(Spacer(1, 15))

        sign_data = [
            [
                create_qr_code_drawing(f"OEM-AUTH:{identifier_val}", 48),
                Paragraph("<b>Authorized Signatory</b><br/>Vice President - Government & PSU Business<br/>Global OEM Systems (India) Pvt Ltd", ParagraphStyle('SignMAF', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#1e293b'))),
                create_official_stamp_drawing("OEM SYSTEMS", "SEALED", "#1e3a8a")
            ]
        ]
        st = Table(sign_data, colWidths=[65, 375, 100])
        st.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(st)

    # 5. CHARTERED ACCOUNTANT TURNOVER / FINANCIAL CERTIFICATE
    elif doc_type == "TURNOVER":
        elements.append(Paragraph("<b>M/s R. K. SINGHANIA & ASSOCIATES</b><br/><b>CHARTERED ACCOUNTANTS</b>", ParagraphStyle('CAHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#7c2d12'), alignment=1)))
        elements.append(Paragraph("ICAI Firm Registration No: 109844W • Barakhamba Road, Connaught Place, New Delhi", sub_style))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#7c2d12'), spaceAfter=8, spaceBefore=4))

        elements.append(Paragraph("<b>ANNUAL TURNOVER & NET WORTH CERTIFICATE</b>", h1_style))
        elements.append(Paragraph(f"<b>UDIN: {extra_fields.get('UDIN', '26099123AAAA012345')}</b>", ParagraphStyle('UDIN', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor('#b45309'), alignment=1)))
        elements.append(Spacer(1, 8))

        elements.append(Paragraph(
            f"This is to certify that we have audited the books of accounts of <b>{bidder_name}</b> and based on the verified audited financial statements, the financial standing of the enterprise is as follows:",
            ParagraphStyle('CABody', parent=styles['Normal'], fontSize=9.5, leading=13, textColor=colors.HexColor('#1f2937'))
        ))
        elements.append(Spacer(1, 8))

        fin_rows = [
            [Paragraph("<b>Financial Year</b>", label_style), Paragraph("<b>Annual Turnover (INR Crores)</b>", label_style), Paragraph("<b>Net Worth (INR Crores)</b>", label_style), Paragraph("<b>Audit Status</b>", label_style)],
            [Paragraph("FY 2022 - 2023", val_style), Paragraph("INR 12.40 Cr", val_style), Paragraph("INR 6.80 Cr", val_style), Paragraph("Audited & Verified", val_style)],
            [Paragraph("FY 2023 - 2024", val_style), Paragraph("INR 13.80 Cr", val_style), Paragraph("INR 7.90 Cr", val_style), Paragraph("Audited & Verified", val_style)],
            [Paragraph("FY 2024 - 2025", val_style), Paragraph(f"<b>{identifier_val}</b>", val_mono), Paragraph("INR 9.20 Cr", val_style), Paragraph("Audited & Verified", val_style)],
            [Paragraph("<b>Average 3-Yr Turnover :</b>", label_style), Paragraph(f"<b>{identifier_val}</b>", val_mono), Paragraph("<b>Positive & Solvent</b>", label_style), Paragraph("<b>COMPLIANT</b>", val_mono)]
        ]
        ft_table = Table(fin_rows, colWidths=[130, 150, 130, 130])
        ft_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#7c2d12')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#fef3c7')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#fde68a')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(ft_table)
        elements.append(Spacer(1, 10))

        ca_sign = [
            [
                create_qr_code_drawing(f"ICAI-UDIN:{extra_fields.get('UDIN', '26099123AAAA012345')}", 48),
                Paragraph("<b>For R. K. Singhania & Associates</b><br/>Chartered Accountants (FCA)<br/>Membership No: 099123 • FRN: 109844W<br/>Place: New Delhi • Date: 15-May-2025", ParagraphStyle('SignCA', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#1f2937'))),
                create_official_stamp_drawing("CHARTERED ACC", "ICAI UDIN", "#7c2d12")
            ]
        ]
        cat = Table(ca_sign, colWidths=[65, 375, 100])
        cat.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(cat)

    # 6. MAKE IN INDIA (MII) CLASS-I LOCAL CONTENT SELF-DECLARATION
    elif doc_type == "LOCAL_CONTENT":
        elements.append(Paragraph("<b>ON THE LETTERHEAD OF THE BIDDER / STATUTORY AUDITOR</b>", watermark_style))
        elements.append(Paragraph(f"<b>{bidder_name.upper()}</b>", h1_style))
        elements.append(Paragraph("Registered Office & Manufacturing Plant Facility", sub_style))
        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0f2b48'), spaceAfter=8, spaceBefore=4))

        elements.append(Paragraph("<b>PUBLIC PROCUREMENT (PREFERENCE TO MAKE IN INDIA) ORDER 2017</b>", h2_style))
        elements.append(Paragraph("<b>SELF-DECLARATION OF LOCAL CONTENT (CLASS-I LOCAL SUPPLIER)</b>", ParagraphStyle('MII', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#059669'), alignment=1)))
        elements.append(Spacer(1, 10))

        mii_text = f"""
        We hereby declare and certify in compliance with the Public Procurement (Preference to Make in India) Order, 2017 issued by DPIIT, Ministry of Commerce & Industry, Government of India that:<br/><br/>
        1. <b>Legal Name of Bidder:</b> {bidder_name}<br/>
        2. <b>Percentage of Local Content Addition:</b> <font color='#059669'><b>Local Content: {identifier_val}</b></font> (Statutory Requirement: &gt;= 50%)<br/>
        3. <b>Classification:</b> <b>Class-I Local Supplier</b><br/>
        4. <b>Location of Domestic Manufacturing / Value Addition:</b> {extra_fields.get('Facility', extra_fields.get('Location', 'Navi Mumbai / Pune Assembly Hub'))}<br/>
        5. We understand that false declarations will be in breach of the Code of Integrity under Rule 175(1)(i)(h) of the GFR-2017 and may attract debarment / penalty as per statutory norms.
        """
        elements.append(Paragraph(mii_text, ParagraphStyle('MIIText', parent=styles['Normal'], fontSize=9.5, leading=14, textColor=colors.HexColor('#1e293b'))))
        elements.append(Spacer(1, 15))

        sign_data = [
            [
                create_qr_code_drawing(f"MII-DECLARATION:{identifier_val}", 48),
                Paragraph(f"<b>Authorized Signatory / Managing Director</b><br/>{bidder_name}<br/>Official Seal & Signature", ParagraphStyle('SignMII', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#1e293b'))),
                create_official_stamp_drawing("NOTARY PUBLIC", "NOTARIZED", "#059669")
            ]
        ]
        st = Table(sign_data, colWidths=[65, 375, 100])
        st.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(st)

    # 7. PAST PERFORMANCE & EXPERIENCE CERTIFICATE
    elif doc_type == "EXPERIENCE":
        elements.append(create_national_emblem_drawing(45, 45))
        elements.append(Paragraph("<b>GOVERNMENT OF INDIA / STATE PROCURING ENTITY</b>", h2_style))
        elements.append(Paragraph("<b>PUBLIC WORKS & PROCUREMENT DIVISION</b>", h1_style))
        elements.append(Paragraph("<b>CLIENT SATISFACTORY PERFORMANCE & COMPLETION CERTIFICATE</b>", ParagraphStyle('ExpT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor('#0f2b48'), alignment=1)))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8, spaceBefore=4))

        exp_data = [
            [Paragraph("<b>Name of Contractor / Bidder :</b>", label_style), Paragraph(f"<b>{bidder_name}</b>", val_style)],
            [Paragraph("<b>Qualifying Experience Record :</b>", label_style), Paragraph(f"<b>Experience : {identifier_val}</b>", val_mono)],
            [Paragraph("<b>Executed Contract Value :</b>", label_style), Paragraph(f"<b>{extra_fields.get('Contract Value', 'INR 480 Lakhs')}</b>", val_style)],
            [Paragraph("<b>Contract Scope / Description :</b>", label_style), Paragraph("Supply, Testing, Commissioning and SLA Maintenance", val_style)],
            [Paragraph("<b>Completion Status :</b>", label_style), Paragraph("Completed On Schedule • Zero Default", val_style)],
            [Paragraph("<b>Quality & DGQA Rating :</b>", label_style), Paragraph("<b>EXCELLENT (Grade A - 4.9/5.0)</b>", val_style)],
            [Paragraph("<b>Warranty & Defect Liability :</b>", label_style), Paragraph("Satisfactorily Discharged", val_style)]
        ]
        et = Table(exp_data, colWidths=[190, 350])
        et.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0f2b48')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(et)
        elements.append(Spacer(1, 10))

        ft_data = [
            [
                create_qr_code_drawing(f"EXP-CERT:{identifier_val}", 48),
                Paragraph("<b>Executive Engineer / Procuring Officer</b><br/>Central Procurement Organization / Ministry Authority<br/>Govt of India", ParagraphStyle('SignExp', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'))),
                create_official_stamp_drawing("PROCURING ORG", "PASSED", "#0f2b48")
            ]
        ]
        ft = Table(ft_data, colWidths=[65, 375, 100])
        ft.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(ft)

    # 8. DEFAULT / OTHER DOCUMENTS (MCA, EPFO, ESIC, STARTUP)
    else:
        elements.append(create_national_emblem_drawing(45, 45))
        elements.append(Paragraph("<b>GOVERNMENT OF INDIA STATUTORY REGISTRATION</b>", h2_style))
        elements.append(Paragraph(f"<b>{doc_type} STATUTORY COMPLIANCE CERTIFICATE</b>", h1_style))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=8, spaceBefore=4))

        gen_data = [
            [Paragraph("<b>Enterprise Legal Name :</b>", label_style), Paragraph(bidder_name, val_style)],
            [Paragraph(f"<b>Statutory Identifier ({doc_type}) :</b>", label_style), Paragraph(f"<b>{identifier_val}</b>", val_mono)]
        ]
        for k, v in extra_fields.items():
            gen_data.append([
                Paragraph(f"<b>{k} :</b>", label_style),
                Paragraph(str(v), val_style)
            ])
        gt = Table(gen_data, colWidths=[190, 350])
        gt.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#0f2b48')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(gt)
        elements.append(Spacer(1, 10))

        ft_data = [
            [
                create_qr_code_drawing(f"{doc_type}:{identifier_val}", 48),
                Paragraph("<b>Competent Authority / Government of India</b><br/>Digitally verified compliance record.", ParagraphStyle('SignGen', parent=styles['Normal'], fontSize=8.5, leading=12, textColor=colors.HexColor('#334155'))),
                create_official_stamp_drawing("GOI AUTHORITY", "VERIFIED", "#0f2b48")
            ]
        ]
        ft = Table(ft_data, colWidths=[65, 375, 100])
        ft.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(ft)

    doc.build(elements)
    data = buffer.getvalue()
    buffer.close()
    return data
