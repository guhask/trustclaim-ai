"""
Claim Prediction Agent
Uses compliance flags + document completeness + pattern analysis to:
1. Output an approval probability score (0-100%)
2. List top rejection risks ranked by severity
3. Generate specific, actionable fix instructions
"""

import json
from datetime import datetime
from anthropic import Anthropic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, RISK_WEIGHTS


class ClaimPredictionAgent:

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Claim Prediction Agent"

    # ── Main prediction ───────────────────────────────────────────────────────
    def predict(self, policy_data: dict, bill_data: dict,
                discharge_data: dict, compliance_report: dict) -> dict:
        """
        Generate claim approval prediction.
        Returns: probability score, risk list, fix guide, confidence level.
        """

        # Step 1: Rule-based risk scoring
        rule_score = self._rule_based_score(compliance_report)

        # Step 2: Document completeness factor
        doc_score  = self._document_score(policy_data, bill_data, discharge_data)

        # Step 3: LLM-based holistic prediction
        llm_result = self._llm_prediction(
            policy_data, bill_data, discharge_data, compliance_report, rule_score
        )

        # Step 4: Blend scores
        final_score = self._blend_scores(rule_score, doc_score,
                                          llm_result.get("llm_probability", 70))

        # Step 5: Build risk list
        risks = self._build_risk_list(compliance_report, llm_result)

        # Step 6: Generate fix guide
        fix_guide = self._generate_fix_guide(risks, policy_data, discharge_data)

        return {
            "_agent":     self.agent_name,
            "_timestamp": datetime.now().isoformat(),
            "approval_probability":  final_score,
            "probability_label":     self._probability_label(final_score),
            "probability_color":     self._probability_color(final_score),
            "rule_based_score":      rule_score,
            "document_score":        doc_score,
            "llm_probability":       llm_result.get("llm_probability", 70),
            "confidence_level":      llm_result.get("confidence", "MEDIUM"),
            "top_risks":             risks[:5],    # Top 5 ranked risks
            "fix_guide":             fix_guide,
            "estimated_payable":     self._estimate_payable(bill_data, compliance_report),
            "recommendation":        llm_result.get("recommendation", ""),
            "key_insight":           llm_result.get("key_insight", ""),
        }

    # ── Rule-based scoring ────────────────────────────────────────────────────
    def _rule_based_score(self, compliance_report: dict) -> int:
        """
        Start at 100. Deduct points for each violation/warning.
        """
        score = 100
        violations = compliance_report.get("violations", [])
        warnings   = compliance_report.get("warnings", [])

        for v in violations:
            v_type = v.get("type", "")
            deduct = RISK_WEIGHTS.get(v_type.lower().replace("_violation", "").
                                      replace("_breach", ""), 25)
            if v.get("severity") == "CRITICAL":
                deduct = min(deduct * 1.5, 50)
            score -= deduct

        for w in warnings:
            score -= 8  # Warnings are less severe

        return max(0, min(100, round(score)))

    # ── Document score ────────────────────────────────────────────────────────
    def _document_score(self, policy_data: dict,
                         bill_data: dict, discharge_data: dict) -> int:
        scores = []
        for doc in [policy_data, bill_data, discharge_data]:
            scores.append(int(doc.get("confidence_score") or
                              doc.get("_confidence", 70)))
        return round(sum(scores) / len(scores)) if scores else 70

    # ── LLM prediction ────────────────────────────────────────────────────────
    def _llm_prediction(self, policy_data: dict, bill_data: dict,
                         discharge_data: dict, compliance_report: dict,
                         rule_score: int) -> dict:
        prompt = f"""You are India's most experienced health insurance claim assessor with 
25 years of hands-on experience processing thousands of claims for Star Health, HDFC ERGO, 
and Niva Bupa.

Based on the claim data and compliance report below, provide your expert assessment.

COMPLIANCE VIOLATIONS FOUND: {compliance_report.get('total_violations', 0)}
COMPLIANCE WARNINGS FOUND: {compliance_report.get('total_warnings', 0)}
RULE-BASED SCORE: {rule_score}/100

POLICY: Sum insured ₹{policy_data.get('sum_insured', 'unknown')}, 
Insurer: {policy_data.get('insurer_name', 'unknown')},
Policy age: from {policy_data.get('policy_start_date', 'unknown')}

CLAIM: Diagnosis: {discharge_data.get('primary_diagnosis', 'unknown')},
Hospital: {discharge_data.get('hospital_name') or bill_data.get('hospital_name', 'unknown')},
Total bill: ₹{bill_data.get('total_bill_amount', 'unknown')},
Admission: {discharge_data.get('admission_type', 'unknown')}

TOP VIOLATIONS:
{json.dumps(compliance_report.get('violations', [])[:3], indent=2)[:800]}

Return ONLY valid JSON:
{{
  "llm_probability": 0-100 integer (your expert estimate of approval chance),
  "confidence": "HIGH/MEDIUM/LOW",
  "recommendation": "One clear sentence on what to do next",
  "key_insight": "The single most important thing about this claim",
  "additional_risks": [
    {{
      "risk": "Risk description",
      "severity": "HIGH/MEDIUM/LOW",
      "fix": "Specific fix"
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
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
                "llm_probability": rule_score,
                "confidence": "MEDIUM",
                "recommendation": "Review all compliance violations before filing.",
                "key_insight": "Multiple compliance checks need attention.",
                "additional_risks": []
            }

    # ── Score blending ────────────────────────────────────────────────────────
    def _blend_scores(self, rule: int, doc: int, llm: int) -> int:
        """Weighted blend: rule-based 50%, LLM 35%, document quality 15%."""
        blended = (rule * 0.50) + (llm * 0.35) + (doc * 0.15)
        return round(max(0, min(100, blended)))

    # ── Risk list builder ─────────────────────────────────────────────────────
    def _build_risk_list(self, compliance_report: dict, llm_result: dict) -> list:
        risks = []

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        for v in compliance_report.get("violations", []):
            risks.append({
                "title":    v.get("title", "Compliance Violation"),
                "severity": v.get("severity", "HIGH"),
                "description": v.get("description", ""),
                "irdai_ref":   v.get("irdai_ref", ""),
                "fix":      v.get("fix", ""),
                "type":     "VIOLATION"
            })

        for w in compliance_report.get("warnings", []):
            risks.append({
                "title":    w.get("title", "Warning"),
                "severity": w.get("severity", "MEDIUM"),
                "description": w.get("description", ""),
                "irdai_ref":   w.get("irdai_ref", ""),
                "fix":      w.get("fix", ""),
                "type":     "WARNING"
            })

        for r in llm_result.get("additional_risks", []):
            risks.append({
                "title":    r.get("risk", "Additional Risk"),
                "severity": r.get("severity", "MEDIUM"),
                "description": r.get("risk", ""),
                "irdai_ref":   "AI Analysis",
                "fix":      r.get("fix", ""),
                "type":     "AI_INSIGHT"
            })

        # Sort by severity
        risks.sort(key=lambda x: severity_order.get(x["severity"], 4))
        return risks

    # ── Fix guide ─────────────────────────────────────────────────────────────
    def _generate_fix_guide(self, risks: list, policy_data: dict,
                             discharge_data: dict) -> list:
        """Generate prioritized, actionable fix instructions."""
        fix_steps = []
        seen = set()

        for i, risk in enumerate(risks[:5], 1):
            fix = risk.get("fix", "")
            if fix and fix not in seen:
                seen.add(fix)
                fix_steps.append({
                    "step":     i,
                    "priority": risk["severity"],
                    "action":   risk["title"],
                    "detail":   fix,
                    "irdai_ref": risk.get("irdai_ref", ""),
                })

        # Add universal best practices
        if not any("document" in f.get("action", "").lower() for f in fix_steps):
            fix_steps.append({
                "step":     len(fix_steps) + 1,
                "priority": "LOW",
                "action":   "Organize all original documents",
                "detail":   "Ensure all originals are preserved: discharge summary, itemized bills, "
                            "investigation reports, prescriptions. Photocopies are not accepted.",
                "irdai_ref": "IRDAI/HLT/CIR/2021/189"
            })

        return fix_steps

    # ── Payable estimate ──────────────────────────────────────────────────────
    def _estimate_payable(self, bill_data: dict, compliance_report: dict) -> dict:
        try:
            total = float(str(bill_data.get("total_bill_amount") or 0).replace(",", ""))
            if total == 0:
                return {"estimated": 0, "note": "Bill amount not available"}

            # Apply room rent proportionate deduction if flagged
            deduction_pct = 0
            for w in compliance_report.get("warnings", []):
                if w.get("type") == "ROOM_RENT_EXCEEDED":
                    charged = float(w.get("charged_amount") or 0)
                    eligible = float(w.get("eligible_amount") or 0)
                    if charged > 0:
                        deduction_pct = max(0, (charged - eligible) / charged * 100)

            # Apply violation deductions
            violation_deduction = len(compliance_report.get("violations", [])) * 5

            effective_deduction = deduction_pct + violation_deduction
            payable = total * (1 - effective_deduction / 100)

            return {
                "total_bill":         total,
                "estimated_payable":  round(payable),
                "deduction_pct":      round(effective_deduction, 1),
                "note": (f"Estimated after {effective_deduction:.1f}% adjustments. "
                         f"Actual amount subject to insurer assessment.")
            }
        except Exception:
            return {"estimated": 0, "note": "Could not estimate payable amount"}

    # ── Label helpers ─────────────────────────────────────────────────────────
    def _probability_label(self, score: int) -> str:
        if score >= 80:  return "High Approval Chance"
        if score >= 60:  return "Moderate Approval Chance"
        if score >= 40:  return "Low Approval Chance"
        return "Very High Rejection Risk"

    def _probability_color(self, score: int) -> str:
        if score >= 80:  return "green"
        if score >= 60:  return "orange"
        if score >= 40:  return "red"
        return "darkred"
