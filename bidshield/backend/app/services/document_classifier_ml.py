import os
import re
import math
from typing import Dict, Any, List, Optional
import numpy as np

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "models"))
MODEL_PATH = os.path.join(MODEL_DIR, "document_fraud_detector.joblib")

# Statutory regular expressions for Government of India documents
STATUTORY_PATTERNS = {
    "PAN": r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    "GST": r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
    "UDYAM": r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$",
    "MCA": r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$",
    "UDIN": r"^[0-9]{2}[0-9]{6}[A-Z]{4}[0-9]{6}$", # 18-digit ICAI UDIN
    "OEM": r"^OEM-[A-Z0-9\-]+$",
}

DUMMY_KEYWORDS = [
    "DUMMY", "FAKE", "SAMPLE", "PLACEHOLDER", "TEST DOCUMENT",
    "LOREM IPSUM", "NOT A LEGAL", "FICTIONAL", "FOR TESTING ONLY",
    "TEMP DATA", "INVALID CARD"
]

AUTHORITY_KEYWORDS = {
    "PAN": ["INCOME TAX DEPARTMENT", "GOVT OF INDIA", "PERMANENT ACCOUNT NUMBER", "NSDL", "UTIITSL"],
    "GST": ["FORM GST REG-06", "GOODS AND SERVICES TAX", "REGISTRATION CERTIFICATE", "PRINCIPAL PLACE", "REGULAR TAXPAYER"],
    "UDYAM": ["MINISTRY OF MICRO", "UDYAM REGISTRATION", "ENTERPRISE", "MSME", "NIC CODE"],
    "OEM": ["MANUFACTURER AUTHORIZATION", "AUTHORIZED PARTNER", "WARRANTY", "GENUINE SPARE", "MAF"],
    "TURNOVER": ["CHARTERED ACCOUNTANTS", "UDIN", "AUDITED", "ANNUAL TURNOVER", "NET WORTH", "ICAI"],
    "EXPERIENCE": ["SATISFACTORY PERFORMANCE", "COMPLETION CERTIFICATE", "CONTRACT VALUE", "PUBLIC PROCUREMENT"],
    "LOCAL_CONTENT": ["PUBLIC PROCUREMENT", "PREFERENCE TO MAKE IN INDIA", "LOCAL CONTENT", "CLASS-I LOCAL SUPPLIER"],
    "MCA": ["MINISTRY OF CORPORATE AFFAIRS", "REGISTRAR OF COMPANIES", "COMPANIES ACT", "CORPORATE IDENTITY"]
}

def calculate_text_entropy(text: str) -> float:
    """Calculates Shannon entropy to detect repetitive garbage or synthetic text."""
    if not text:
        return 0.0
    prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
    return -sum([p * math.log(p) / math.log(2.0) for p in prob])

def extract_ml_features(text: str, doc_type: str, ocr_confidence: float = 0.9) -> np.ndarray:
    """Extract numeric feature vector for ML classification."""
    clean_text = text.upper()
    
    # 1. Dummy/Fake keyword presence (0 to 1)
    dummy_count = sum(1 for kw in DUMMY_KEYWORDS if kw in clean_text)
    dummy_feature = min(1.0, dummy_count * 0.5)

    # 2. Authority Header Presence (0 to 1)
    auth_list = AUTHORITY_KEYWORDS.get(doc_type.upper(), ["GOVERNMENT OF INDIA", "CERTIFICATE"])
    auth_matches = sum(1 for kw in auth_list if kw in clean_text)
    auth_feature = min(1.0, auth_matches / max(1, len(auth_list)))

    # 3. Structural Identifier Match (0 or 1)
    identifier_valid = 0.0
    pat = STATUTORY_PATTERNS.get(doc_type.upper())
    if pat:
        # Search anywhere in text
        m = re.search(pat.replace("^", "").replace("$", ""), clean_text)
        if m:
            identifier_valid = 1.0
    else:
        identifier_valid = 1.0 if len(clean_text) > 50 else 0.0

    # 4. Text Length Feature (normalized)
    text_len_feature = min(1.0, len(clean_text) / 500.0)

    # 5. Shannon Entropy Feature (normalized to ~1.0)
    entropy = calculate_text_entropy(clean_text)
    entropy_feature = min(1.0, entropy / 5.0)

    # 6. OCR Confidence
    conf_feature = float(ocr_confidence)

    # 7. Deformatting Indicator (e.g. OCR confidence low but authority keywords present)
    deform_feature = 1.0 if (ocr_confidence < 0.65 and auth_matches >= 2) else 0.0

    return np.array([
        dummy_feature,
        auth_feature,
        identifier_valid,
        text_len_feature,
        entropy_feature,
        conf_feature,
        deform_feature
    ])

class DocumentFraudMLClassifier:
    """Local heuristic screening only; no fraud or authenticity determinations."""

    def __init__(self):
        # Do not deserialize the repository's joblib artifact at runtime.
        pass

    def evaluate_document(
        self,
        extracted_text: str,
        doc_type: str,
        ocr_confidence: float = 0.94,
        declared_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        text_clean = (extracted_text or "").upper()
        reasons = []

        # 1. Flag placeholder markers for officer review; they do not prove fraud.
        dummy_matches = [kw for kw in DUMMY_KEYWORDS if kw in text_clean]
        if dummy_matches:
            return {
                "classification": "UNUSUAL_PATTERN",
                "deformatting_index": 0.0,
                "diagnostic_reasons": [
                    f"Document contains placeholder marker(s): {', '.join(dummy_matches[:3])}.",
                    "This local screen is not an authenticity or fraud determination; officer review is required."
                ],
                "screening_version": "local-heuristics-v1"
            }

        # 2. Check statutory syntax match
        pat = STATUTORY_PATTERNS.get(doc_type.upper())
        identifier_found = None
        if pat:
            m = re.search(pat.replace("^", "").replace("$", ""), text_clean)
            if m:
                identifier_found = m.group(0)
            else:
                reasons.append(f"Statutory format for {doc_type} not detected matching standard Indian syntax.")

        # If declared identifier is provided, verify match
        if declared_identifier and identifier_found:
            if declared_identifier.strip().upper() != identifier_found.strip().upper():
                return {
                    "classification": "UNUSUAL_PATTERN",
                    "deformatting_index": 0.1,
                    "diagnostic_reasons": [
                        f"Extracted identifier ({identifier_found}) differs from the bidder profile ({declared_identifier}).",
                        "This discrepancy requires officer review and is not a fraud determination."
                    ],
                    "screening_version": "local-heuristics-v1"
                }

        # 3. Check Authority Header & Keywords
        auth_list = AUTHORITY_KEYWORDS.get(doc_type.upper(), ["GOVERNMENT OF INDIA"])
        auth_matches = [kw for kw in auth_list if kw in text_clean]
        auth_ratio = len(auth_matches) / max(1, len(auth_list))

        # 4. Deformatting vs True Document Evaluation
        if ocr_confidence < 0.65:
            if auth_ratio >= 0.40 and (identifier_found or len(text_clean) > 80):
                return {
                    "classification": "MANUAL_REVIEW",
                    "deformatting_index": round(1.0 - ocr_confidence, 2),
                    "diagnostic_reasons": [
                        f"Document content complies with {doc_type} statutory structure ({len(auth_matches)} authority keywords verified).",
                        f"Visual deformatting detected (OCR Confidence {ocr_confidence*100:.0f}% due to scan compression or skew). Recommended for secondary officer confirmation."
                    ],
                    "screening_version": "local-heuristics-v1"
                }
            else:
                return {
                    "classification": "MANUAL_REVIEW",
                    "deformatting_index": 0.85,
                    "diagnostic_reasons": [
                        "Low scan resolution combined with missing statutory authority markers.",
                        "Document requires re-upload of high-resolution scan."
                    ],
                    "screening_version": "local-heuristics-v1"
                }

        # 5. Heuristic screening only; this does not verify authenticity.
        features = extract_ml_features(extracted_text, doc_type, ocr_confidence)
        
        screen_score = float(np.clip(
            (features[1] * 0.35) + # Authority headers
            (features[2] * 0.35) + # Identifier syntax
            (features[3] * 0.10) + # Length
            (features[4] * 0.10) + # Entropy
            (features[5] * 0.10) - # Confidence
            (features[0] * 0.80),  # Dummy penalty
            0.0, 1.0
        ))

        screen_score = round(screen_score, 2)

        if screen_score >= 0.70:
            classification = "NO_PATTERN_DETECTED"
            reasons.append("Expected text patterns were present. This is not an authenticity verification.")
        elif screen_score >= 0.40:
            classification = "MANUAL_SCRUTINY_RECOMMENDED"
            reasons.append("Some expected text patterns were not found; officer review is recommended.")
        else:
            classification = "UNUSUAL_PATTERN"
            reasons.append(f"Expected text patterns for {doc_type} were not found. This is not a fraud determination.")

        return {
            "classification": classification,
            "screening_score": screen_score,
            "deformatting_index": 0.05,
            "diagnostic_reasons": reasons,
            "screening_version": "local-heuristics-v1"
        }

# Global singleton
ml_fraud_classifier = DocumentFraudMLClassifier()
