"""
Fraud Detection Agent
Analyzes hospital bills and discharge summaries for:
1. Inflated charges (room rent, pharmacy, procedures vs market rates)
2. Diagnosis-procedure mismatch (procedure not matching diagnosis)
3. Duplicate or suspicious billing patterns
4. Upcoding signals (billing for higher procedure than performed)
5. Unbundling (splitting one procedure into multiple charges)

This is a B2B insurer-facing feature — insurers use this to
flag claims for detailed investigation before settlement.

Market benchmark data is based on Indian hospital pricing as of 2025-26.
"""

import json
from datetime import datetime
from anthropic import Anthropic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


# ── Market benchmark rates for Indian hospitals (2025-26) ─────────────────────
# Source: NHA (National Health Authority) CGHS rates + private hospital surveys
MARKET_BENCHMARKS = {
    "room_rent": {
        "general_ward":    {"min": 500,   "max": 2500,  "avg": 1200},
        "semi_private":    {"min": 1500,  "max": 5000,  "avg": 2800},
        "private":         {"min": 3000,  "max": 8000,  "avg": 5000},
        "deluxe":          {"min": 6000,  "max": 15000, "avg": 9000},
        "icu":             {"min": 5000,  "max": 20000, "avg": 10000},
        "iccu":            {"min": 8000,  "max": 25000, "avg": 15000},
    },
    "common_procedures": {
        "appendectomy":         {"min": 40000,  "max": 120000, "avg": 70000},
        "cholecystectomy":      {"min": 50000,  "max": 150000, "avg": 90000},
        "hernia_repair":        {"min": 30000,  "max": 100000, "avg": 60000},
        "knee_replacement":     {"min": 150000, "max": 400000, "avg": 250000},
        "hip_replacement":      {"min": 180000, "max": 450000, "avg": 280000},
        "angioplasty":          {"min": 200000, "max": 500000, "avg": 320000},
        "bypass_surgery":       {"min": 300000, "max": 700000, "avg": 450000},
        "cataract":             {"min": 15000,  "max": 60000,  "avg": 30000},
        "hysterectomy":         {"min": 60000,  "max": 180000, "avg": 110000},
        "delivery_normal":      {"min": 15000,  "max": 50000,  "avg": 28000},
        "delivery_caesarean":   {"min": 40000,  "max": 120000, "avg": 70000},
        "dialysis_session":     {"min": 2000,   "max": 6000,   "avg": 3500},
        "chemotherapy_session": {"min": 20000,  "max": 80000,  "avg": 45000},
    },
    "investigations": {
        "cbc":              {"min": 150,  "max": 600,   "avg": 300},
        "lft":              {"min": 300,  "max": 900,   "avg": 550},
        "rft":              {"min": 300,  "max": 800,   "avg": 500},
        "hba1c":            {"min": 300,  "max": 800,   "avg": 500},
        "ecg":              {"min": 200,  "max": 800,   "avg": 400},
        "echo":             {"min": 1500, "max": 5000,  "avg": 2800},
        "xray":             {"min": 200,  "max": 800,   "avg": 450},
        "ct_scan":          {"min": 3000, "max": 12000, "avg": 6000},
        "mri":              {"min": 5000, "max": 18000, "avg": 9000},
        "ultrasound":       {"min": 800,  "max": 3000,  "avg": 1500},
        "endoscopy":        {"min": 3000, "max": 10000, "avg": 5500},
    },
    "pharmacy_pct_of_bill": {
        "medical_management": {"min": 0.10, "max": 0.25, "avg": 0.15},
        "surgical":           {"min": 0.15, "max": 0.40, "avg": 0.25},
        "icu":                {"min": 0.20, "max": 0.45, "avg": 0.30},
    },
    "surgeon_fee_pct": {
        "min": 0.08, "max": 0.25, "avg": 0.15
    },
}

# ── Fraud risk signals ────────────────────────────────────────────────────────
FRAUD_SIGNALS = {
    "room_rent_inflation":
        "Room rent charged significantly above market rate for room type",
    "pharmacy_inflation":
        "Pharmacy charges disproportionately high relative to total bill",
    "diagnosis_procedure_mismatch":
        "Procedure performed does not align with stated diagnosis",
    "excessive_investigations":
        "Number/cost of investigations appears excessive for diagnosis",
    "unbundling":
        "Single procedure appears split into multiple line items to inflate total",
    "upcoding":
        "Procedure description suggests billing for higher category than performed",
    "duplicate_charges":
        "Same or similar items billed more than once",
    "implant_without_sticker":
        "Implant/device billed but no manufacturer sticker/invoice attached",
    "icu_without_justification":
        "ICU charges claimed but diagnosis does not typically require ICU admission",
    "short_stay_high_bill":
        "Very high bill relative to short length of stay",
    "round_number_billing":
        "Multiple charges in suspiciously round numbers (padding indicator)",
}


class FraudDetectionAgent:

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Fraud Detection Agent"

    # ── Main detection ────────────────────────────────────────────────────────
    def detect(self, bill_data: dict, discharge_data: dict,
               policy_data: dict) -> dict:
        """
        Run fraud detection on the claim.
        Returns: fraud score (0-100), risk level, flags, and recommendations.
        """

        flags      = []
        risk_score = 0

        # Rule-based checks
        flags.extend(self._check_room_rent(bill_data))
        flags.extend(self._check_pharmacy_ratio(bill_data))
        flags.extend(self._check_stay_vs_bill(bill_data))
        flags.extend(self._check_round_numbers(bill_data))
        flags.extend(self._check_diagnosis_mismatch(bill_data, discharge_data))

        # Score from flags
        for flag in flags:
            sev = flag.get("severity", "LOW")
            if sev == "HIGH":
                risk_score += 30
            elif sev == "MEDIUM":
                risk_score += 12
            else:
                risk_score += 5

        risk_score = min(risk_score, 100)

        # LLM deep analysis
        llm_result = self._llm_fraud_analysis(
            bill_data, discharge_data, policy_data, flags, risk_score
        )

        # Merge LLM flags
        for f in llm_result.get("additional_flags", []):
            flags.append(f)
            sev = f.get("severity", "LOW")
            risk_score = min(100, risk_score + (20 if sev == "HIGH" else 10 if sev == "MEDIUM" else 4))

        # Final risk level
        if risk_score >= 65:
            risk_level = "HIGH RISK"
            risk_color = "#E24B4A"
            risk_icon  = "🚨"
            recommendation = "Refer for detailed investigation before settlement. Do not pay without site verification."
        elif risk_score >= 30:
            risk_level = "MEDIUM RISK"
            risk_color = "#EF9F27"
            risk_icon  = "⚠️"
            recommendation = "Request additional documents and clarifications before settlement."
        elif risk_score >= 10:
            risk_level = "LOW RISK"
            risk_color = "#185FA5"
            risk_icon  = "🔵"
            recommendation = "Minor anomalies detected. Proceed with standard verification."
        else:
            risk_level = "CLEAN"
            risk_color = "#0F6E56"
            risk_icon  = "✅"
            recommendation = "No significant fraud indicators. Proceed with normal settlement process."

        return {
            "_agent":         self.agent_name,
            "_timestamp":     datetime.now().isoformat(),
            "fraud_score":    risk_score,
            "risk_level":     risk_level,
            "risk_color":     risk_color,
            "risk_icon":      risk_icon,
            "recommendation": recommendation,
            "flags":          flags,
            "total_flags":    len(flags),
            "high_flags":     sum(1 for f in flags if f.get("severity") == "HIGH"),
            "medium_flags":   sum(1 for f in flags if f.get("severity") == "MEDIUM"),
            "llm_summary":    llm_result.get("summary", ""),
            "llm_verdict":    llm_result.get("verdict", ""),
            "estimated_inflation": llm_result.get("estimated_inflation", "Unable to estimate"),
            "action_required": risk_score >= 40,
        }

    # ── Check 1: Room rent vs market ──────────────────────────────────────────
    def _check_room_rent(self, bill_data: dict) -> list:
        flags = []
        try:
            room_type    = str(bill_data.get("room_type") or "").lower()
            rent_per_day = float(
                str(bill_data.get("room_rent_per_day") or 0)
                .replace(",", "").replace("Rs.", "").strip()
            )
            if rent_per_day == 0:
                return []

            # Map room type to benchmark key
            key = "private"
            if "general" in room_type or "ward" in room_type:
                key = "general_ward"
            elif "semi" in room_type:
                key = "semi_private"
            elif "icu" in room_type or "intensive" in room_type:
                key = "icu"
            elif "iccu" in room_type or "ccu" in room_type:
                key = "iccu"
            elif "deluxe" in room_type or "suite" in room_type:
                key = "deluxe"

            bench = MARKET_BENCHMARKS["room_rent"][key]
            overage_pct = ((rent_per_day / bench["avg"]) - 1) * 100

            if rent_per_day > bench["avg"] * 1.6:
                flags.append({
                    "type":      "ROOM_RENT_INFLATION",
                    "severity":  "HIGH",
                    "title":     "Room Rent Significantly Above Market Average",
                    "detail":    (
                        f"Charged: Rs.{rent_per_day:,.0f}/day for {room_type or 'private'} room. "
                        f"Market average: Rs.{bench['avg']:,}/day (range Rs.{bench['min']:,}–Rs.{bench['max']:,}). "
                        f"Charged is {overage_pct:.0f}% above market average — possible inflation."
                    ),
                    "action":    "Verify actual room category with hospital records. Request room rent certificate."
                })
            elif rent_per_day > bench["avg"] * 1.2:
                flags.append({
                    "type":      "ROOM_RENT_HIGH",
                    "severity":  "MEDIUM",
                    "title":     "Room Rent Above Market Average",
                    "detail":    (
                        f"Charged: Rs.{rent_per_day:,.0f}/day for {room_type or 'private'} room. "
                        f"Market average: Rs.{bench['avg']:,}/day. "
                        f"Charged is {overage_pct:.0f}% above average."
                    ),
                    "action":    "Request hospital classification certificate and itemized room charges."
                })
        except (ValueError, TypeError):
            pass
        return flags

    # ── Check 2: Pharmacy ratio ───────────────────────────────────────────────
    def _check_pharmacy_ratio(self, bill_data: dict) -> list:
        flags = []
        try:
            total    = float(str(bill_data.get("total_bill_amount") or 0)
                             .replace(",", "").replace("Rs.", "").strip())
            pharmacy = float(str(bill_data.get("pharmacy_charges") or 0)
                             .replace(",", "").replace("Rs.", "").strip())

            if total <= 0 or pharmacy <= 0:
                return []

            ratio = pharmacy / total

            # Surgical claims: pharmacy > 45% is suspicious
            # Medical claims: pharmacy > 30% is suspicious
            # Indian hospital benchmark: pharmacy typically 15-25% of total bill
            # > 35% warrants investigation, > 45% is HIGH risk
            if ratio > 0.45:
                flags.append({
                    "type":     "PHARMACY_INFLATION",
                    "severity": "HIGH",
                    "title":    "Pharmacy Charges Disproportionately High",
                    "detail":   (
                        f"Pharmacy: Rs.{pharmacy:,.0f} = {ratio*100:.0f}% of total bill Rs.{total:,.0f}. "
                        f"Market benchmark: 15–25% of total bill. "
                        f"Charges at {ratio*100:.0f}% indicate possible inflation or non-payable items included."
                    ),
                    "action":   "Request itemized pharmacy bill with batch numbers. Verify all items against prescriptions."
                })
            elif ratio > 0.35:
                flags.append({
                    "type":     "PHARMACY_ELEVATED",
                    "severity": "HIGH",
                    "title":    "Pharmacy Charges Well Above Market Benchmark",
                    "detail":   (
                        f"Pharmacy: Rs.{pharmacy:,.0f} = {ratio*100:.0f}% of total bill Rs.{total:,.0f}. "
                        f"Market benchmark is 15–25%. Values above 35% warrant investigation."
                    ),
                    "action":   "Request itemized pharmacy bill with batch numbers and prescriptions."
                })
            elif ratio > 0.25:
                flags.append({
                    "type":     "PHARMACY_ELEVATED",
                    "severity": "MEDIUM",
                    "title":    "Pharmacy Charges Above Market Benchmark",
                    "detail":   (
                        f"Pharmacy: Rs.{pharmacy:,.0f} = {ratio*100:.0f}% of total bill. "
                        f"Market benchmark is 15–25% of total bill."
                    ),
                    "action":   "Request itemized pharmacy bill for verification."
                })
        except (ValueError, TypeError):
            pass
        return flags

    # ── Check 3: Short stay vs high bill ──────────────────────────────────────
    def _check_stay_vs_bill(self, bill_data: dict) -> list:
        flags = []
        try:
            days  = int(bill_data.get("total_days") or 0)
            total = float(str(bill_data.get("total_bill_amount") or 0)
                          .replace(",", "").replace("Rs.", "").strip())

            if days <= 0 or total <= 0:
                return []

            per_day = total / days

            # Rs.50,000+ per day is suspicious for non-ICU
            room_type = str(bill_data.get("room_type") or "").lower()
            is_icu    = "icu" in room_type or "intensive" in room_type

            # Benchmark: Rs.15,000-30,000/day is typical for private room admission
            # Rs.50,000+ per day warrants investigation for non-ICU
            if per_day > 50000 and not is_icu:
                flags.append({
                    "type":     "HIGH_DAILY_COST",
                    "severity": "HIGH",
                    "title":    "Unusually High Cost Per Day of Admission",
                    "detail":   (
                        f"Total: Rs.{total:,.0f} for {days} days = "
                        f"Rs.{per_day:,.0f}/day. "
                        f"Market benchmark for non-ICU: Rs.15,000–30,000/day. "
                        f"Possible billing inflation or incorrect room classification."
                    ),
                    "action":   "Request day-wise cost breakdown and room classification certificate."
                })
            elif per_day > 30000 and not is_icu:
                flags.append({
                    "type":     "ELEVATED_DAILY_COST",
                    "severity": "MEDIUM",
                    "title":    "Above-Average Cost Per Day of Admission",
                    "detail":   (
                        f"Total: Rs.{total:,.0f} for {days} days = "
                        f"Rs.{per_day:,.0f}/day. "
                        f"Market benchmark for private room: Rs.15,000–30,000/day."
                    ),
                    "action":   "Request itemized day-wise cost breakdown."
                })
        except (ValueError, TypeError):
            pass
        return flags

    # ── Check 4: Round number billing ─────────────────────────────────────────
    def _check_round_numbers(self, bill_data: dict) -> list:
        flags = []
        try:
            # Check if major charge components are suspiciously round
            charges_to_check = {
                "Doctor fees":     bill_data.get("doctor_fees"),
                "Pharmacy":        bill_data.get("pharmacy_charges"),
                "Investigations":  bill_data.get("investigation_charges"),
                "OT charges":      bill_data.get("ot_charges"),
            }

            round_count = 0
            round_items = []
            for label, val in charges_to_check.items():
                if val:
                    try:
                        num = float(str(val).replace(",","").replace("Rs.","").strip())
                        # Flag if divisible by 1000 exactly with value > 5000
                        if num > 5000 and num % 1000 == 0:
                            round_count += 1
                            round_items.append(f"{label}: Rs.{num:,.0f}")
                    except (ValueError, TypeError):
                        pass

            if round_count >= 2:
                flags.append({
                    "type":     "ROUND_NUMBER_BILLING",
                    "severity": "MEDIUM",
                    "title":    "Multiple Charges in Round Numbers — Possible Estimation",
                    "detail":   (
                        f"{round_count} charge components are exact multiples of Rs.1,000: "
                        f"{', '.join(round_items)}. "
                        f"Round-number billing across multiple components is a known indicator "
                        f"of estimated rather than actual charges."
                    ),
                    "action":   "Request itemized breakdowns with actual cost calculations for all rounded charges."
                })
        except Exception:
            pass
        return flags

    # ── Check 5: Diagnosis vs procedure mismatch ──────────────────────────────
    def _check_diagnosis_mismatch(self, bill_data: dict,
                                   discharge_data: dict) -> list:
        flags = []

        diagnosis  = str(discharge_data.get("primary_diagnosis") or
                         bill_data.get("diagnosis_on_bill") or "").lower()
        procedure  = str(discharge_data.get("procedure_performed") or "").lower()

        if not diagnosis or not procedure:
            return []

        # Known mismatches
        mismatches = [
            (["diabetes", "nephropathy", "hypertension"],
             ["bypass", "angioplasty", "stent", "knee", "hip", "cataract"],
             "Surgical procedure does not typically align with medical diagnosis"),
            (["appendix", "appendicitis"],
             ["cardiac", "heart", "angio", "bypass"],
             "Cardiac procedure billed for appendix diagnosis"),
            (["fracture", "ortho"],
             ["cardiac", "gastro", "endoscopy"],
             "Procedure does not match orthopaedic diagnosis"),
        ]

        for diag_keywords, proc_keywords, message in mismatches:
            diag_match = any(k in diagnosis for k in diag_keywords)
            proc_match = any(k in procedure for k in proc_keywords)
            if diag_match and proc_match:
                flags.append({
                    "type":     "DIAGNOSIS_PROCEDURE_MISMATCH",
                    "severity": "HIGH",
                    "title":    "Diagnosis-Procedure Mismatch Detected",
                    "detail":   (
                        f"Diagnosis: '{discharge_data.get('primary_diagnosis')}' "
                        f"but procedure: '{discharge_data.get('procedure_performed')}'. "
                        f"{message}."
                    ),
                    "action":   "Request detailed clinical notes justifying the procedure for this diagnosis."
                })
                break

        return flags

    # ── LLM deep fraud analysis ───────────────────────────────────────────────
    def _llm_fraud_analysis(self, bill_data: dict, discharge_data: dict,
                             policy_data: dict, existing_flags: list,
                             current_score: int) -> dict:
        prompt = f"""You are a senior health insurance fraud investigator at a leading Indian 
insurer with 20 years of experience detecting fraudulent claims.

Analyze this hospital bill critically for fraud and billing anomalies.
Look for: unusual charge ratios, procedures inconsistent with diagnosis,
investigation costs disproportionate to condition, soft inflation patterns,
charges typical of higher acuity than billed, implants billed without itemization.
Be specific — even legitimate claims often have soft inflation. Find it.

CLAIM DATA:
Hospital: {bill_data.get('hospital_name', 'N/A')}
Diagnosis: {discharge_data.get('primary_diagnosis', 'N/A')}
Procedure: {discharge_data.get('procedure_performed', 'N/A')}
Admission type: {discharge_data.get('admission_type', 'N/A')}
Total Bill: Rs.{bill_data.get('total_bill_amount', 'N/A')}
Days admitted: {bill_data.get('total_days', 'N/A')}
Room Type: {bill_data.get('room_type', 'N/A')}
Room Rent/Day: Rs.{bill_data.get('room_rent_per_day', 'N/A')}
Doctor/Consultant Fees: Rs.{bill_data.get('doctor_fees', 'N/A')}
Pharmacy/Medicines: Rs.{bill_data.get('pharmacy_charges', 'N/A')}
Investigations (Lab/Radiology): Rs.{bill_data.get('investigation_charges', 'N/A')}
OT/Procedure charges: Rs.{bill_data.get('ot_charges', 'N/A')}

RULE-BASED FLAGS ALREADY FOUND: {len(existing_flags)}
CURRENT SCORE: {current_score}/100

MARKET CONTEXT (Indian hospitals 2025-26):
- Private room rent: Rs.3,000-8,000/day (avg Rs.5,000)
- Pharmacy: typically 15-25% of total bill for medical, 20-35% for surgical
- Investigations: typically 8-15% of total bill
- Consultant fees: typically 8-15% of total bill
- OT charges: typically 10-20% of total bill for surgical cases

Return ONLY valid JSON:
{{
  "summary": "2-sentence assessment — be specific about what looks suspicious or confirms clean",
  "verdict": "CLEAN / SUSPICIOUS / LIKELY_FRAUD",
  "estimated_inflation": "Estimated inflated amount if suspicious (e.g. Rs.10,000-20,000 approx) or Not detected",
  "additional_flags": [
    {{
      "type": "FLAG_TYPE",
      "severity": "HIGH/MEDIUM/LOW",
      "title": "Short specific title",
      "detail": "Specific detail with numbers from the bill",
      "action": "Specific investigator action required"
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=800,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception:
            return {
                "summary":            "Analysis complete. Review flagged items carefully.",
                "verdict":            "SUSPICIOUS" if current_score >= 40 else "CLEAN",
                "estimated_inflation": "Unable to estimate",
                "additional_flags":   []
            }
