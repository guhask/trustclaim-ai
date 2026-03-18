"""
Document Intelligence Agent
Extracts structured claim data from uploaded PDFs and images.
Handles: Policy documents, Hospital bills, Discharge summaries
"""

import json
import base64
import pdfplumber
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


class DocumentIntelligenceAgent:

    def __init__(self):
        self.client  = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Document Intelligence Agent"

    # ── Public entry point ────────────────────────────────────────────────────
    def extract(self, file_path: str, doc_type: str) -> dict:
        """
        Extract structured data from an uploaded document.
        doc_type: 'policy' | 'bill' | 'discharge' | 'prescription'
        Returns a dict with extracted fields + confidence scores + audit log.
        """
        text = self._extract_text(file_path)

        if doc_type == "policy":
            result = self._extract_policy_data(text)
        elif doc_type == "bill":
            result = self._extract_bill_data(text)
        elif doc_type == "discharge":
            result = self._extract_discharge_data(text)
        else:
            result = self._extract_generic(text)

        result["_agent"]     = self.agent_name
        result["_doc_type"]  = doc_type
        result["_timestamp"] = datetime.now().isoformat()
        result["_raw_text_length"] = len(text)
        return result

    # ── Text extraction ───────────────────────────────────────────────────────
    def _extract_text(self, file_path: str) -> str:
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            return self._extract_pdf(file_path)
        elif path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            return self._extract_image(file_path)
        else:
            with open(file_path, "r", errors="ignore") as f:
                return f.read()

    def _extract_pdf(self, file_path: str) -> str:
        text_parts = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
        except Exception as e:
            return f"[PDF extraction error: {e}]"
        combined = "\n".join(text_parts).strip()
        # Scanned/image PDF — fall back to Claude Vision automatically
        if len(combined) < 50:
            return self._extract_pdf_with_vision(file_path)
        return combined

    def _extract_image(self, file_path: str) -> str:
        """Use Claude Vision for scanned images and image-based PDFs."""
        with open(file_path, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")

        ext = Path(file_path).suffix.lower().lstrip(".")
        media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "png": "image/png", "gif": "image/gif",
                     "webp": "image/webp"}
        media_type = media_map.get(ext, "image/jpeg")

        # Claude Vision — no OpenAI needed
        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       img_data
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL text from this insurance document image. "
                            "Preserve all numbers, dates, names, and amounts exactly as shown. "
                            "Output only the extracted text, nothing else."
                        )
                    }
                ]
            }]
        )
        return response.content[0].text

    def _extract_pdf_with_vision(self, file_path: str) -> str:
        """
        Fallback for scanned / image-based PDFs where pdfplumber returns no text.
        Converts first page to image then uses Claude Vision.
        """
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(file_path, first_page=1, last_page=3, dpi=200)
            all_text = []
            for img in images:
                # Save page as temp PNG
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    img.save(tmp.name, "PNG")
                    page_text = self._extract_image(tmp.name)
                    all_text.append(page_text)
                    os.unlink(tmp.name)
            return "\n".join(all_text)
        except Exception:
            return "[Could not extract text from scanned PDF. Please upload a text-based PDF.]"

    # ── LLM extraction prompts ────────────────────────────────────────────────
    def _extract_policy_data(self, text: str) -> dict:
        prompt = f"""You are an expert Indian health insurance document analyst.
Extract the following fields from this policy document text. 
Return ONLY valid JSON, no explanation.

DOCUMENT TEXT:
{text[:4000]}

Extract these fields (use null if not found):
{{
  "insurer_name": "name of insurance company",
  "policy_number": "policy number / certificate number",
  "policyholder_name": "insured person name",
  "sum_insured": "total sum insured amount in rupees (number only)",
  "policy_start_date": "YYYY-MM-DD format",
  "policy_end_date": "YYYY-MM-DD format",
  "premium_amount": "annual premium in rupees",
  "plan_name": "name of the health plan",
  "members_covered": ["list of covered members with ages"],
  "room_rent_limit": "room rent sub-limit (e.g. 1% of SI or specific amount)",
  "icu_limit": "ICU sub-limit",
  "pre_existing_waiting": "PED waiting period in months",
  "specific_disease_waiting": "specific disease waiting period in months",
  "initial_waiting": "initial waiting period in days",
  "copay_percentage": "co-payment percentage if any",
  "network_hospitals_available": true or false,
  "tpa_name": "TPA or in-house claims",
  "policy_status": "active/lapsed/unknown",
  "exclusions_mentioned": ["list any exclusions explicitly mentioned"],
  "confidence_score": 0-100 based on document clarity
}}"""

        return self._call_llm(prompt)

    def _extract_bill_data(self, text: str) -> dict:
        prompt = f"""You are an expert Indian hospital billing analyst.
Extract the following fields from this hospital bill. 
Return ONLY valid JSON, no explanation.

DOCUMENT TEXT:
{text[:4000]}

Extract these fields (use null if not found):
{{
  "hospital_name": "name of hospital",
  "hospital_address": "hospital address",
  "patient_name": "patient name on bill",
  "admission_date": "YYYY-MM-DD",
  "discharge_date": "YYYY-MM-DD",
  "total_days": "number of days admitted",
  "room_type": "type of room (General/Semi-private/Private/ICU)",
  "room_rent_per_day": "room rent charged per day in rupees",
  "total_room_rent": "total room rent charges",
  "doctor_fees": "total doctor/surgeon/anesthesia fees",
  "pharmacy_charges": "total pharmacy/medicine charges",
  "investigation_charges": "lab tests, radiology, diagnostics total",
  "ot_charges": "operation theatre charges if any",
  "total_bill_amount": "grand total bill amount",
  "amount_paid_by_patient": "amount already paid",
  "balance_due": "balance amount for insurance",
  "diagnosis_on_bill": "diagnosis/procedure mentioned on bill",
  "treating_doctor": "name of treating doctor",
  "bill_number": "bill/invoice number",
  "gst_amount": "GST charged if any",
  "confidence_score": 0-100 based on document clarity
}}"""

        return self._call_llm(prompt)

    def _extract_discharge_data(self, text: str) -> dict:
        prompt = f"""You are an expert Indian medical records analyst specializing in 
insurance claim processing.
Extract the following fields from this hospital discharge summary. 
Return ONLY valid JSON, no explanation.

DOCUMENT TEXT:
{text[:4000]}

Extract these fields (use null if not found):
{{
  "patient_name": "patient full name",
  "patient_age": "age in years",
  "patient_gender": "Male/Female/Other",
  "admission_date": "YYYY-MM-DD",
  "discharge_date": "YYYY-MM-DD",
  "primary_diagnosis": "main diagnosis/condition",
  "secondary_diagnoses": ["any additional diagnoses"],
  "procedure_performed": "main surgical or medical procedure if any",
  "admission_type": "Emergency/Planned",
  "treating_doctor": "name of primary treating doctor",
  "department": "treating department (e.g. Cardiology, Orthopedics)",
  "pre_existing_mentioned": ["any pre-existing conditions mentioned in history"],
  "duration_of_illness_mentioned": "how long patient had this condition (if mentioned)",
  "outcome": "Recovered/Discharged against advice/Referred/Deceased",
  "follow_up_required": true or false,
  "investigation_summary": "brief summary of major investigations",
  "treatment_summary": "brief summary of treatment given",
  "hospital_name": "hospital where admitted",
  "is_accident_related": true or false,
  "confidence_score": 0-100 based on document clarity
}}"""

        return self._call_llm(prompt)

    def _extract_generic(self, text: str) -> dict:
        prompt = f"""Extract all insurance-relevant information from this document.
Return as JSON with field names and values. Include a confidence_score (0-100).

DOCUMENT TEXT:
{text[:3000]}"""
        return self._call_llm(prompt)

    def _call_llm(self, prompt: str) -> dict:
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)
            data["_extraction_success"] = True
            return data

        except json.JSONDecodeError as e:
            return {
                "_extraction_success": False,
                "_error": f"JSON parse error: {e}",
                "_raw_response": raw if 'raw' in dir() else ""
            }
        except Exception as e:
            return {
                "_extraction_success": False,
                "_error": str(e)
            }

    # ── Document validation ───────────────────────────────────────────────────
    def validate_completeness(self, extracted_data: dict, doc_type: str) -> dict:
        """Check if all critical fields were successfully extracted."""
        required_fields = {
            "policy":    ["insurer_name", "policy_number", "sum_insured",
                          "policy_start_date", "policy_end_date"],
            "bill":      ["hospital_name", "admission_date", "discharge_date",
                          "total_bill_amount", "diagnosis_on_bill"],
            "discharge": ["primary_diagnosis", "admission_date", "discharge_date",
                          "treating_doctor", "hospital_name"],
        }

        fields = required_fields.get(doc_type, [])
        missing = [f for f in fields if not extracted_data.get(f)]
        present = [f for f in fields if extracted_data.get(f)]

        completeness = (len(present) / len(fields) * 100) if fields else 100

        return {
            "completeness_score": round(completeness),
            "missing_fields":     missing,
            "present_fields":     present,
            "is_complete":        len(missing) == 0
        }
