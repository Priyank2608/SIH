import io
import re
import pymupdf as fitz
from PIL import Image
import pytesseract
from app.core.config import settings

class OCRAdapter:
    name: str = "BaseOCR"
    
    def extract(self, content_bytes: bytes, document_type: str, mime_type: str = "application/pdf") -> dict:
        raise NotImplementedError

class TesseractOCRAdapter(OCRAdapter):
    name: str = "TesseractOCR"

    def extract(self, content_bytes: bytes, document_type: str, mime_type: str = "application/pdf") -> dict:
        if not content_bytes:
            return {
                "text": "",
                "fields": {},
                "bounding_boxes": [],
                "confidence": 0.0,
                "engine": self.name,
                "model_version": settings.ocr_model_version,
                "page_count": 0
            }

        extracted_text = ""
        confidence = 0.0
        confidence_values = []
        bounding_boxes = []
        page_count = 1
        engine_used = self.name

        is_pdf = mime_type == "application/pdf" or content_bytes.startswith(b"%PDF")
        if is_pdf:
            try:
                with fitz.open(stream=content_bytes, filetype="pdf") as pdf:
                    page_count = len(pdf)
                    native_pages = [page.get_text("text") for page in pdf]
                    extracted_text = "\n".join(native_pages).strip()
                    if extracted_text:
                        confidence = 0.94 if len(extracted_text) > 30 else 0.45
                        for pno, page in enumerate(pdf):
                            for block in page.get_text("blocks"):
                                if len(block) >= 5 and block[4].strip():
                                    bounding_boxes.append({"page": pno + 1,
                                        "box": [round(block[0], 1), round(block[1], 1), round(block[2], 1), round(block[3], 1)],
                                        "text": block[4].strip()[:100]})
                    else:
                        # Scanned PDFs need page rendering before OCR. Never decode PDF
                        # bytes as text: that can turn binary data into false OCR output.
                        page_texts = []
                        for pno, page in enumerate(pdf):
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            page_text, page_conf, boxes = self._ocr_image(image, pno + 1)
                            page_texts.append(page_text)
                            if page_conf is not None:
                                confidence_values.append(page_conf)
                            bounding_boxes.extend(boxes)
                        extracted_text = "\n".join(page_texts)
                        confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0
            except Exception:
                extracted_text, confidence = "", 0.0

        elif mime_type.startswith("image/"):
            try:
                image = Image.open(io.BytesIO(content_bytes)).convert("RGB")
                extracted_text, page_confidence, bounding_boxes = self._ocr_image(image, 1)
                confidence = page_confidence or 0.0
            except Exception:
                extracted_text, confidence = "", 0.0

        fields = self._extract_fields(extracted_text, document_type)

        # Detect degraded scan or manual review condition
        if "DEGRADED" in extracted_text.upper() or "LOW QUALITY SCAN" in extracted_text.upper():
            confidence = 0.42
        # Avoid presenting regex matches from uncertain OCR as extracted facts.
        if confidence < 0.60:
            fields = {}

        return {
            "text": extracted_text,
            "fields": fields,
            "bounding_boxes": bounding_boxes[:60], # Top 60 bounding boxes for UI rendering
            "confidence": round(confidence, 2),
            "engine": engine_used,
            "model_version": settings.ocr_model_version,
            "page_count": page_count
        }

    def _ocr_image(self, image: Image.Image, page_number: int):
        text = pytesseract.image_to_string(image, lang=settings.ocr_language, config="--psm 6")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=settings.ocr_language)
        values = [float(value) for value in data.get("conf", []) if str(value).strip() not in ("", "-1")]
        confidence = round(sum(values) / len(values) / 100.0, 2) if values else None
        boxes = []
        for i, word in enumerate(data.get("text", [])[:80]):
            word = word.strip()
            if word:
                boxes.append({"page": page_number,
                    "box": [data["left"][i], data["top"][i], data["left"][i] + data["width"][i], data["top"][i] + data["height"][i]],
                    "text": word})
        return text, confidence, boxes

    def _extract_fields(self, text: str, doc_type: str) -> dict:
        patterns = {
            "GST": r"([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            "PAN": r"([A-Z]{5}[0-9]{4}[A-Z]{1})",
            "UDYAM": r"(UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7})",
            "EPFO": r"(\d{12})",
            "ESIC": r"([A-Z0-9\-]{10,20})",
            "MCA": r"([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})",
            "OEM": r"(OEM-[A-Z0-9\-]+)",
            "STARTUP": r"(DPIIT-[A-Z0-9\-]+|[A-Z0-9\-]{8,20})",
            "NSIC": r"(NSIC-[A-Z0-9\-]+|[A-Z0-9\-]{8,20})",
            "LOCAL_CONTENT": r"(\d+%)",
        }
        out = {}
        key = doc_type.upper()
        p = patterns.get(key)
        if p:
            m = re.search(p, text.upper())
            if m:
                out["identifier"] = m.group(1)

        # Fallback keyword checks if identifier not matched yet
        if not out.get("identifier"):
            m_alt = re.search(r"(?:ID|NUMBER|NO|REF|REGISTRATION|CODE)\s*[:\-]?\s*([A-Z0-9\-]{4,25})", text.upper())
            if m_alt:
                out["identifier"] = m_alt.group(1)

        # Generic metadata extraction
        name = re.search(r"LEGAL\s*NAME\s*[:\-]?\s*([^\n\r]+)", text, re.I)
        if name:
            out["legal_name"] = name.group(1).strip()
            
        trade = re.search(r"TRADE\s*NAME\s*[:\-]?\s*([^\n\r]+)", text, re.I)
        if trade:
            out["trade_name"] = trade.group(1).strip()

        address = re.search(r"ADDRESS\s*[:\-]?\s*([^\n\r]+)", text, re.I)
        if address:
            out["address"] = address.group(1).strip()

        expiry = re.search(r"(?:EXPIRY|VALIDITY|VALID\s*UNTIL|EXPIRES)[^0-9]*(\d{4}-\d{2}-\d{2})", text, re.I)
        if expiry:
            out["expiry_date"] = expiry.group(1)

        status_m = re.search(r"(?:REGISTRATION\s*STATUS|STATUS)\s*[:\-]?\s*([A-Z_]+)", text, re.I)
        if status_m:
            out["status"] = status_m.group(1).strip()

        turnover_m = re.search(r"TURNOVER\s*[:\-]?\s*(?:INR\s*)?([0-9\.]+)\s*(?:CR|CRORE)", text, re.I)
        if turnover_m:
            out["turnover_cr"] = float(turnover_m.group(1))

        exp_m = re.search(r"EXPERIENCE\s*[:\-]?\s*(\d+)\s*YEAR", text, re.I)
        if exp_m:
            out["experience_years"] = int(exp_m.group(1))

        contract_val_m = re.search(r"CONTRACT\s*VALUE\s*[:\-]?\s*(?:INR\s*)?([0-9\.]+)\s*(?:LAKH|CR)", text, re.I)
        if contract_val_m:
            out["contract_value"] = contract_val_m.group(1)

        return out
