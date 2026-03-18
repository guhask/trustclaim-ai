"""
Pre-Authorization Simulator Agent
Simulates how a TPA (Third Party Administrator) would respond to a
cashless pre-authorization request based on extracted claim documents.

In real life, the hospital sends a pre-auth request to the TPA who
responds within 1 hour (planned) or 30 minutes (emergency) per IRDAI mandate.
This agent predicts that response BEFORE filing — giving the patient
advance warning of likely queries, partial approvals, or rejections.
"""

import json
from datetime import datetime
from anthropic import Anthropic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


# Standard TPA query reasons used across Indian health insurers
COMMON_TPA_QUERIES = [
    "Treating doctor's qualification and registration number not mentioned",
    "Exact duration of pre-existing condition not specified in discharge summary",
    "Day-wise treatment chart not attached",
    "Pharmacy bills not supported by doctor prescription",
    "Investigation reports not co-related with diagnosis in discharge summary",
    "Room rent exceeds policy sub-limit — proportionate deduction will apply",
    "Pre-existing condition waiting period not completed",
    "Procedure falls under specific disease waiting period",
    "Pre-authorization not obtained before admission (for planned procedures)",
    "Hospital not in network — cashless not applicable, file reimbursement",
    "ICU charges claimed but ICU stay not documented in nursing notes",
    "Implant/consumable invoice and sticker not attached",
    "Estimated treatment cost breakdown not provided",
    "Patient's age proof not submitted",
]

# TPA response time mandates per IRDAI
TPA_RESPONSE_TIMES = {
    "Emergency":  "30 minutes",
    "Planned":    "1 hour",
    "Discharge":  "3 hours",
}


class PreAuthSimulatorAgent:

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Pre-Auth Simulator Agent"

    # ── Main simulation ───────────────────────────────────────────────────────
    def simulate(self, policy_data: dict, bill_data: dict,
                 discharge_data: dict, compliance_report: dict,
                 prediction: dict) -> dict:
        """
        Simulate TPA pre-authorization response.
        Returns decision, approved amount, queries, and recommendations.
        """

        # Step 1: Determine likely decision from compliance + prediction
        decision_data = self._determine_decision(
            compliance_report, prediction, bill_data, policy_data
        )

        # Step 2: Calculate approved amount
        amount_data = self._calculate_approved_amount(
            bill_data, policy_data, compliance_report, decision_data
        )

        # Step 3: Generate likely TPA queries
        queries = self._generate_tpa_queries(
            policy_data, bill_data, discharge_data, compliance_report
        )

        # Step 4: LLM detailed TPA simulation
        llm_result = self._llm_simulate(
            policy_data, bill_data, discharge_data,
            compliance_report, prediction, decision_data
        )

        # Step 5: Build recommendations
        recommendations = self._build_recommendations(
            decision_data, queries, llm_result, policy_data
        )

        admission_type = str(
            discharge_data.get("admission_type") or
            bill_data.get("admission_type") or "Planned"
        )

        return {
            "_agent":           self.agent_name,
            "_timestamp":       datetime.now().isoformat(),
            "decision":         decision_data["decision"],
            "decision_color":   decision_data["color"],
            "decision_icon":    decision_data["icon"],
            "confidence":       decision_data["confidence"],
            "decision_reason":  decision_data["reason"],
            "claimed_amount":   amount_data["claimed"],
            "approved_amount":  amount_data["approved"],
            "deduction_amount": amount_data["deduction"],
            "deduction_reasons": amount_data["deduction_reasons"],
            "tpa_name":         policy_data.get("tpa_name", "TPA / Insurer"),
            "response_time":    TPA_RESPONSE_TIMES.get(admission_type, "1 hour"),
            "admission_type":   admission_type,
            "tpa_queries":      queries[:6],
            "llm_summary":      llm_result.get("summary", ""),
            "llm_advice":       llm_result.get("advice", ""),
            "escalation_risk":  llm_result.get("escalation_risk", "LOW"),
            "recommendations":  recommendations,
            "irdai_ref":        "IRDAI/HLT/CIR/2023/205",
        }

    # ── Decision logic ────────────────────────────────────────────────────────
    def _determine_decision(self, compliance_report: dict,
                             prediction: dict, bill_data: dict,
                             policy_data: dict) -> dict:
        prob       = prediction.get("approval_probability", 50)
        violations = compliance_report.get("total_violations", 0)
        warnings   = compliance_report.get("total_warnings", 0)
        status     = str(policy_data.get("policy_status", "")).lower()

        # Critical violations = immediate rejection
        critical = any(
            v.get("severity") == "CRITICAL" or
            v.get("type") in ["POLICY_LAPSED", "POLICY_EXPIRED"]
            for v in compliance_report.get("violations", [])
        )

        if critical or prob < 25:
            return {
                "decision":    "REJECTED",
                "color":       "#E24B4A",
                "icon":        "❌",
                "confidence":  "HIGH",
                "reason":      "Critical compliance violations detected. TPA will reject pre-auth."
            }
        elif violations > 0 or prob < 55:
            return {
                "decision":    "PARTIALLY APPROVED",
                "color":       "#EF9F27",
                "icon":        "⚠️",
                "confidence":  "MEDIUM",
                "reason":      "Compliance issues found. TPA likely to approve with deductions and queries."
            }
        elif warnings > 0 or prob < 75:
            return {
                "decision":    "APPROVED WITH QUERIES",
                "color":       "#185FA5",
                "icon":        "🔵",
                "confidence":  "MEDIUM",
                "reason":      "No violations but warnings present. TPA will approve pending clarifications."
            }
        else:
            return {
                "decision":    "APPROVED",
                "color":       "#0F6E56",
                "icon":        "✅",
                "confidence":  "HIGH",
                "reason":      "All compliance checks passed. TPA likely to approve pre-auth."
            }

    # ── Amount calculation ────────────────────────────────────────────────────
    def _calculate_approved_amount(self, bill_data: dict, policy_data: dict,
                                    compliance_report: dict,
                                    decision_data: dict) -> dict:
        deduction_reasons = []

        try:
            claimed = float(
                str(bill_data.get("total_bill_amount") or 0)
                .replace(",", "").replace("Rs.", "").strip()
            )
        except (ValueError, TypeError):
            claimed = 0

        if claimed == 0:
            return {
                "claimed": 0, "approved": 0,
                "deduction": 0, "deduction_reasons": []
            }

        approved = claimed
        decision = decision_data["decision"]

        # Apply deductions based on decision
        if decision == "REJECTED":
            approved = 0
            deduction_reasons.append("Pre-auth rejected — no amount approved")

        else:
            # Room rent proportionate deduction
            for w in compliance_report.get("warnings", []):
                if w.get("type") == "ROOM_RENT_EXCEEDED":
                    try:
                        charged  = float(w.get("charged_amount") or 0)
                        eligible = float(w.get("eligible_amount") or 0)
                        if charged > eligible > 0:
                            pct      = (charged - eligible) / charged
                            deduct   = claimed * pct
                            approved -= deduct
                            deduction_reasons.append(
                                f"Room rent proportionate deduction: "
                                f"Rs.{deduct:,.0f} ({pct*100:.0f}%)"
                            )
                    except (ValueError, TypeError):
                        pass

            # Standard non-payable deductions (toiletries, attendant charges etc.)
            std_deduct = claimed * 0.03
            approved  -= std_deduct
            deduction_reasons.append(
                f"Standard non-payable items (toiletries, attendant): "
                f"Rs.{std_deduct:,.0f}"
            )

            # Partial approval — additional query-based hold
            if decision == "PARTIALLY APPROVED":
                hold     = claimed * 0.15
                approved -= hold
                deduction_reasons.append(
                    f"Amount held pending query resolution: Rs.{hold:,.0f}"
                )

            # Co-pay if applicable
            copay_str = str(policy_data.get("copay") or "")
            if "%" in copay_str:
                try:
                    pct    = float(copay_str.replace("%","").strip().split()[0]) / 100
                    copay  = approved * pct
                    approved -= copay
                    deduction_reasons.append(
                        f"Co-payment ({int(pct*100)}%): Rs.{copay:,.0f}"
                    )
                except (ValueError, TypeError):
                    pass

        approved = max(0, round(approved))
        deduction = round(claimed - approved)

        return {
            "claimed":           round(claimed),
            "approved":          approved,
            "deduction":         deduction,
            "deduction_reasons": deduction_reasons,
        }

    # ── TPA query generation ──────────────────────────────────────────────────
    def _generate_tpa_queries(self, policy_data: dict, bill_data: dict,
                               discharge_data: dict,
                               compliance_report: dict) -> list:
        queries = []

        # Always check for these
        if not discharge_data.get("treating_doctor"):
            queries.append({
                "query":    "Treating doctor's name, qualification and MCI registration number missing",
                "severity": "HIGH",
                "fix":      "Attach treating doctor's certificate with MCI registration number"
            })

        if not bill_data.get("room_rent_per_day"):
            queries.append({
                "query":    "Room rent per day not clearly mentioned in hospital bill",
                "severity": "MEDIUM",
                "fix":      "Request hospital to reissue bill with per-day room rent clearly stated"
            })

        # Based on violations
        for v in compliance_report.get("violations", []):
            queries.append({
                "query":    v.get("title", "Compliance issue"),
                "severity": "HIGH",
                "fix":      v.get("fix", "Resolve before filing pre-auth")
            })

        # Based on warnings
        for w in compliance_report.get("warnings", []):
            if w.get("type") == "ROOM_RENT_EXCEEDED":
                queries.append({
                    "query":    "Room rent exceeds policy sub-limit — proportionate deduction letter will be issued",
                    "severity": "MEDIUM",
                    "fix":      "Request hospital to shift to eligible room category or accept proportionate deduction"
                })
            else:
                queries.append({
                    "query":    w.get("title", "Warning"),
                    "severity": "LOW",
                    "fix":      w.get("fix", "Clarify with insurer")
                })

        # Standard queries always raised
        queries.append({
            "query":    "Day-wise treatment chart and nursing notes required for admission > 3 days",
            "severity": "LOW",
            "fix":      "Collect from hospital nursing station before discharge"
        })
        queries.append({
            "query":    "All original pharmacy bills must be supported by doctor's prescription",
            "severity": "LOW",
            "fix":      "Ensure all pharmacy bills have corresponding prescriptions attached"
        })

        # Sort by severity
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        queries.sort(key=lambda x: order.get(x["severity"], 3))

        return queries

    # ── LLM simulation ────────────────────────────────────────────────────────
    def _llm_simulate(self, policy_data: dict, bill_data: dict,
                       discharge_data: dict, compliance_report: dict,
                       prediction: dict, decision_data: dict) -> dict:
        prompt = f"""You are an experienced TPA (Third Party Administrator) claims assessor 
at Medi Assist India with 15 years of experience processing Indian health insurance pre-auth requests.

Review this pre-authorization request and give your expert assessment.

CLAIM SUMMARY:
- Insurer: {policy_data.get('insurer_name', 'N/A')}
- Policy: {policy_data.get('policy_number', 'N/A')} | Sum Insured: Rs.{policy_data.get('sum_insured', 'N/A')}
- Patient: {discharge_data.get('patient_name', 'N/A')}, Age: {discharge_data.get('patient_age', 'N/A')}
- Hospital: {discharge_data.get('hospital_name') or bill_data.get('hospital_name', 'N/A')}
- Diagnosis: {discharge_data.get('primary_diagnosis', 'N/A')}
- Admission type: {discharge_data.get('admission_type', 'N/A')}
- Claimed amount: Rs.{bill_data.get('total_bill_amount', 'N/A')}
- Compliance status: {compliance_report.get('compliance_status', 'N/A')}
- Violations: {compliance_report.get('total_violations', 0)}
- Approval probability: {prediction.get('approval_probability', 50)}%
- Simulated TPA decision: {decision_data['decision']}

Return ONLY valid JSON:
{{
  "summary": "2-sentence TPA assessor's summary of this pre-auth request",
  "advice": "Single most important action the patient/hospital should take right now",
  "escalation_risk": "LOW/MEDIUM/HIGH — risk of claim being escalated to senior review",
  "processing_note": "Internal TPA processing note (what the assessor would write)"
}}"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
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
                "summary":         "Pre-auth request received and under assessment.",
                "advice":          "Ensure all original documents are in order before hospital submits pre-auth.",
                "escalation_risk": "MEDIUM",
                "processing_note": "Standard review process initiated."
            }

    # ── Recommendations ───────────────────────────────────────────────────────
    def _build_recommendations(self, decision_data: dict, queries: list,
                                 llm_result: dict, policy_data: dict) -> list:
        recs = []
        decision = decision_data["decision"]

        if decision == "REJECTED":
            recs.append({
                "priority": "CRITICAL",
                "icon":     "🚫",
                "action":   "Do NOT proceed with cashless admission",
                "detail":   "Pre-auth will be rejected. Consider paying out of pocket "
                            "and filing for reimbursement after addressing violations."
            })
        elif decision in ["PARTIALLY APPROVED", "APPROVED WITH QUERIES"]:
            recs.append({
                "priority": "HIGH",
                "icon":     "📞",
                "action":   "Call TPA helpline BEFORE hospital submits pre-auth",
                "detail":   f"Contact {policy_data.get('tpa_name', 'your TPA')} "
                            f"to understand likely deductions. Helpline is available 24x7."
            })

        if llm_result.get("advice"):
            recs.append({
                "priority": "HIGH",
                "icon":     "💡",
                "action":   "Key Action",
                "detail":   llm_result["advice"]
            })

        # High severity query fixes
        for q in queries[:2]:
            if q.get("severity") == "HIGH":
                recs.append({
                    "priority": "HIGH",
                    "icon":     "📋",
                    "action":   f"Resolve before pre-auth: {q['query'][:60]}",
                    "detail":   q["fix"]
                })

        recs.append({
            "priority": "MEDIUM",
            "icon":     "⏱️",
            "action":   "Know your IRDAI rights on response time",
            "detail":   "TPA must respond within 1 hour for planned admission, "
                        "30 minutes for emergency, per IRDAI/HLT/CIR/2023/205. "
                        "If no response, escalate to IRDAI Bima Bharosa portal."
        })

        return recs[:5]
