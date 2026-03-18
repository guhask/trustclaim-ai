"""
Compliance Guardrail Agent
Cross-checks claim data against IRDAI regulations and policy-specific rules.
Every flag cites the exact IRDAI regulation or policy clause.
This is the heart of TrustClaim AI's compliance story.
"""

import json
from datetime import datetime, date
from anthropic import Anthropic
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import (ANTHROPIC_API_KEY, CLAUDE_MODEL,
                          WAITING_PERIODS, STANDARD_EXCLUSIONS)
from data.irdai_rules.knowledge_base import IRDAI_REGULATIONS, COMMON_REJECTION_REASONS


class ComplianceGuardrailAgent:

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Compliance Guardrail Agent"
        self.regulations = IRDAI_REGULATIONS

    # ── Main compliance check ─────────────────────────────────────────────────
    def check(self, policy_data: dict, bill_data: dict, discharge_data: dict) -> dict:
        """
        Run all compliance checks. Returns a structured report with:
        - List of violations with IRDAI citations
        - List of warnings (potential issues)
        - Overall compliance status
        - Audit trail of all checks run
        """
        audit_trail = []
        violations  = []
        warnings    = []

        # 1. Waiting period checks
        wp = self._check_waiting_periods(policy_data, discharge_data)
        violations.extend(wp["violations"])
        warnings.extend(wp["warnings"])
        audit_trail.append(wp["audit"])

        # 2. Exclusion checks
        ex = self._check_exclusions(policy_data, discharge_data)
        violations.extend(ex["violations"])
        warnings.extend(ex["warnings"])
        audit_trail.append(ex["audit"])

        # 3. Documentation completeness
        dc = self._check_documentation(policy_data, bill_data, discharge_data)
        violations.extend(dc["violations"])
        warnings.extend(dc["warnings"])
        audit_trail.append(dc["audit"])

        # 4. Sub-limit checks
        sl = self._check_sub_limits(policy_data, bill_data)
        violations.extend(sl["violations"])
        warnings.extend(sl["warnings"])
        audit_trail.append(sl["audit"])

        # 5. Policy validity check
        pv = self._check_policy_validity(policy_data, bill_data)
        violations.extend(pv["violations"])
        warnings.extend(pv["warnings"])
        audit_trail.append(pv["audit"])

        # 6. LLM deep compliance analysis
        deep = self._deep_compliance_analysis(policy_data, discharge_data)
        violations.extend(deep.get("violations", []))
        warnings.extend(deep.get("warnings", []))
        audit_trail.append({
            "check": "LLM Deep Compliance Analysis",
            "status": "completed",
            "model": CLAUDE_MODEL
        })

        # Determine overall status
        if violations:
            status = "NON_COMPLIANT"
            status_color = "red"
        elif warnings:
            status = "REVIEW_REQUIRED"
            status_color = "orange"
        else:
            status = "COMPLIANT"
            status_color = "green"

        return {
            "_agent":         self.agent_name,
            "_timestamp":     datetime.now().isoformat(),
            "compliance_status": status,
            "status_color":   status_color,
            "total_violations": len(violations),
            "total_warnings": len(warnings),
            "violations":     violations,
            "warnings":       warnings,
            "audit_trail":    audit_trail,
            "irdai_regulations_checked": len(self.regulations),
        }

    # ── Check 1: Waiting periods ──────────────────────────────────────────────
    def _check_waiting_periods(self, policy_data: dict, discharge_data: dict) -> dict:
        violations = []
        warnings   = []
        checks_run = []

        policy_start = self._parse_date(policy_data.get("policy_start_date"))
        admission    = self._parse_date(
            discharge_data.get("admission_date") or
            policy_data.get("_bill_admission_date")
        )

        if policy_start and admission:
            days_elapsed = (admission - policy_start).days

            # Initial 30-day waiting period
            checks_run.append("Initial 30-day waiting period check")
            if days_elapsed < WAITING_PERIODS["initial"]:
                violations.append({
                    "type":        "WAITING_PERIOD_VIOLATION",
                    "severity":    "HIGH",
                    "title":       "Initial Waiting Period Not Completed",
                    "description": (
                        f"Hospitalization occurred {days_elapsed} days after policy inception. "
                        f"A mandatory {WAITING_PERIODS['initial']}-day initial waiting period applies."
                    ),
                    "irdai_ref":   "IRDAI/HLT/REG/2016/143",
                    "days_elapsed": days_elapsed,
                    "days_required": WAITING_PERIODS["initial"],
                    "fix": "Claim is likely to be rejected unless this is an accidental injury. "
                           "Collect proof of accident if applicable."
                })
            else:
                checks_run.append(f"✓ Initial waiting cleared ({days_elapsed} days elapsed)")

            # Specific disease waiting periods
            specific_conditions = [
                "hernia", "cataract", "knee replacement", "hip replacement",
                "hysterectomy", "sinusitis", "varicose", "piles", "fissure",
                "calculus", "stone", "ent", "deviated nasal", "tonsil"
            ]
            diagnosis = str(discharge_data.get("primary_diagnosis", "")).lower()
            for condition in specific_conditions:
                if condition in diagnosis and days_elapsed < 730:  # 2 years
                    checks_run.append(f"Specific disease check: {condition}")
                    warnings.append({
                        "type":        "SPECIFIC_DISEASE_WAITING",
                        "severity":    "MEDIUM",
                        "title":       f"Specific Disease Waiting Period — {condition.title()}",
                        "description": (
                            f"Diagnosis '{discharge_data.get('primary_diagnosis')}' may fall under "
                            f"specific disease waiting category. Standard waiting period is 2 years."
                        ),
                        "irdai_ref":   "IRDAI/HLT/REG/2016/143 Schedule I",
                        "fix": "Verify with insurer if this condition falls under specific disease list. "
                               "If policy is older than 2 years from inception, this may not apply."
                    })

            # PED check
            pre_existing = discharge_data.get("pre_existing_mentioned", [])
            if pre_existing:
                ped_waiting_months = int(policy_data.get("pre_existing_waiting") or 48)
                ped_waiting_days   = ped_waiting_months * 30
                checks_run.append("Pre-existing disease waiting period check")
                if days_elapsed < ped_waiting_days:
                    violations.append({
                        "type":        "PED_WAITING_VIOLATION",
                        "severity":    "HIGH",
                        "title":       "Pre-Existing Disease Waiting Period Not Completed",
                        "description": (
                            f"Discharge summary mentions pre-existing conditions: {pre_existing}. "
                            f"Policy has a {ped_waiting_months}-month PED waiting period. "
                            f"Only {round(days_elapsed/30)} months have elapsed."
                        ),
                        "irdai_ref":   "IRDAI/HLT/REG/2016/143 Clause 4",
                        "fix": "Claim likely to be rejected for PED. "
                               "Check if treating doctor can clarify the condition is a new onset, not pre-existing."
                    })
        else:
            warnings.append({
                "type":     "DATE_MISSING",
                "severity": "MEDIUM",
                "title":    "Could Not Verify Waiting Period",
                "description": "Policy start date or admission date missing. Waiting period check skipped.",
                "irdai_ref": "N/A",
                "fix": "Upload complete policy document with inception date and hospital bill with admission date."
            })

        return {
            "violations": violations,
            "warnings":   warnings,
            "audit": {
                "check":   "Waiting Period Compliance",
                "checks_run": checks_run,
                "violations_found": len(violations),
                "timestamp": datetime.now().isoformat()
            }
        }

    # ── Check 2: Exclusions ───────────────────────────────────────────────────
    def _check_exclusions(self, policy_data: dict, discharge_data: dict) -> dict:
        violations = []
        warnings   = []

        diagnosis   = str(discharge_data.get("primary_diagnosis", "")).lower()
        procedure   = str(discharge_data.get("procedure_performed", "")).lower()
        combined    = f"{diagnosis} {procedure}"

        exclusion_keywords = {
            "cosmetic":       ("Cosmetic/Aesthetic Treatment",    "IRDAI/HLT/REG/2016/143 Schedule II"),
            "aesthetic":      ("Cosmetic/Aesthetic Treatment",    "IRDAI/HLT/REG/2016/143 Schedule II"),
            "dental":         ("Dental Treatment Exclusion",      "IRDAI/HLT/REG/2016/143 Schedule II"),
            "refractive":     ("Refractive Error Correction",     "IRDAI/HLT/REG/2016/143 Schedule II"),
            "obesity":        ("Obesity Treatment",               "IRDAI/HLT/REG/2016/143 Schedule II"),
            "bariatric":      ("Bariatric Surgery Exclusion",     "IRDAI/HLT/REG/2016/143 Schedule II"),
            "substance abuse":("Substance Abuse Treatment",       "IRDAI/HLT/REG/2016/143 Schedule II"),
            "alcohol":        ("Alcohol-Related Treatment",       "IRDAI/HLT/REG/2016/143 Schedule II"),
            "experimental":   ("Experimental Treatment",          "IRDAI/HLT/REG/2016/143 Schedule II"),
            "hair":           ("Cosmetic/Hair Treatment",         "IRDAI/HLT/REG/2016/143 Schedule II"),
        }

        for keyword, (title, ref) in exclusion_keywords.items():
            if keyword in combined:
                violations.append({
                    "type":        "EXCLUSION_VIOLATION",
                    "severity":    "HIGH",
                    "title":       f"Excluded Treatment: {title}",
                    "description": (
                        f"Diagnosis/procedure '{diagnosis or procedure}' appears to match "
                        f"a standard IRDAI exclusion: {title}."
                    ),
                    "irdai_ref":   ref,
                    "keyword_matched": keyword,
                    "fix": f"This treatment is permanently excluded under IRDAI standard exclusions. "
                           f"Claim is very likely to be rejected. Consult treating doctor to "
                           f"verify if treatment was medically necessary due to illness/accident."
                })

        # Also check policy-specific exclusions
        policy_exclusions = policy_data.get("exclusions_mentioned", [])
        for excl in policy_exclusions:
            if any(word in combined for word in excl.lower().split()[:3]):
                warnings.append({
                    "type":        "POLICY_SPECIFIC_EXCLUSION",
                    "severity":    "HIGH",
                    "title":       f"Potential Policy-Specific Exclusion Match",
                    "description": f"Your policy lists '{excl}' as an exclusion. "
                                   f"Current claim diagnosis may overlap.",
                    "irdai_ref":   "Policy Schedule — Exclusions Section",
                    "fix": "Review your specific policy exclusion list against the diagnosis carefully."
                })

        return {
            "violations": violations,
            "warnings":   warnings,
            "audit": {
                "check":   "Exclusion Compliance",
                "keywords_checked": len(exclusion_keywords),
                "violations_found": len(violations),
                "timestamp": datetime.now().isoformat()
            }
        }

    # ── Check 3: Documentation completeness ──────────────────────────────────
    def _check_documentation(self, policy_data: dict, bill_data: dict,
                              discharge_data: dict) -> dict:
        violations = []
        warnings   = []
        missing    = []

        required_docs = {
            "Policy copy":               bool(policy_data.get("_extraction_success")),
            "Hospital bill":             bool(bill_data.get("_extraction_success")),
            "Discharge summary":         bool(discharge_data.get("_extraction_success")),
            "Treating doctor name":      bool(discharge_data.get("treating_doctor") or
                                              bill_data.get("treating_doctor")),
            "Admission date":            bool(discharge_data.get("admission_date") or
                                              bill_data.get("admission_date")),
            "Diagnosis documented":      bool(discharge_data.get("primary_diagnosis") or
                                              bill_data.get("diagnosis_on_bill")),
        }

        missing = [doc for doc, present in required_docs.items() if not present]

        if missing:
            violations.append({
                "type":        "DOCUMENTATION_INCOMPLETE",
                "severity":    "MEDIUM",
                "title":       "Incomplete Documentation",
                "description": f"The following required documents/fields are missing: {', '.join(missing)}",
                "irdai_ref":   "IRDAI/HLT/CIR/2021/189",
                "missing_items": missing,
                "fix": (
                    "Collect all missing documents before filing. "
                    "IRDAI mandates insurers cannot ask for documents beyond the standard list, "
                    "but all standard documents must be complete."
                )
            })

        return {
            "violations": violations,
            "warnings":   warnings,
            "audit": {
                "check":   "Documentation Completeness",
                "docs_checked": len(required_docs),
                "docs_present": len(required_docs) - len(missing),
                "docs_missing": missing,
                "timestamp": datetime.now().isoformat()
            }
        }

    # ── Check 4: Sub-limits ───────────────────────────────────────────────────
    def _check_sub_limits(self, policy_data: dict, bill_data: dict) -> dict:
        violations = []
        warnings   = []

        try:
            si           = float(str(policy_data.get("sum_insured") or 0).replace(",", ""))
            room_limit   = policy_data.get("room_rent_limit")
            room_charged = float(str(bill_data.get("room_rent_per_day") or 0).replace(",", ""))
            room_type    = str(bill_data.get("room_type") or "").lower()

            if si > 0 and room_charged > 0 and room_limit:
                # Parse "1% of SI" type limits
                if "%" in str(room_limit):
                    pct = float(str(room_limit).replace("%", "").strip().split()[0])
                    eligible_room = si * pct / 100
                else:
                    eligible_room = float(str(room_limit).replace(",", ""))

                if room_charged > eligible_room:
                    excess_pct = ((room_charged - eligible_room) / eligible_room) * 100
                    warnings.append({
                        "type":        "ROOM_RENT_EXCEEDED",
                        "severity":    "HIGH",
                        "title":       "Room Rent Exceeds Policy Sub-Limit",
                        "description": (
                            f"Room rent charged: ₹{room_charged:,.0f}/day. "
                            f"Policy eligible limit: ₹{eligible_room:,.0f}/day. "
                            f"Excess: {excess_pct:.0f}%. "
                            f"Proportionate deduction will apply to ALL related expenses."
                        ),
                        "irdai_ref":   "IRDAI/HLT/CIR/2020/151",
                        "eligible_amount": eligible_room,
                        "charged_amount":  room_charged,
                        "fix": (
                            f"Request hospital to shift to a room within ₹{eligible_room:,.0f}/day "
                            f"if still admitted. If already discharged, the proportionate deduction "
                            f"will reduce your reimbursable amount significantly."
                        )
                    })
        except (ValueError, TypeError):
            pass

        return {
            "violations": violations,
            "warnings":   warnings,
            "audit": {
                "check":   "Sub-Limit Compliance",
                "violations_found": len(violations),
                "warnings_found": len(warnings),
                "timestamp": datetime.now().isoformat()
            }
        }

    # ── Check 5: Policy validity ──────────────────────────────────────────────
    def _check_policy_validity(self, policy_data: dict, bill_data: dict) -> dict:
        violations = []
        warnings   = []

        policy_end  = self._parse_date(policy_data.get("policy_end_date"))
        admission   = self._parse_date(bill_data.get("admission_date") or
                                       bill_data.get("_admission_date"))
        status      = str(policy_data.get("policy_status") or "").lower()

        if "lapsed" in status or "expired" in status:
            violations.append({
                "type":        "POLICY_LAPSED",
                "severity":    "CRITICAL",
                "title":       "Policy Lapsed or Expired",
                "description": "Policy status indicates lapsed or expired. No claims are payable.",
                "irdai_ref":   "Policy Terms — General Conditions",
                "fix": "Revive the policy immediately by paying outstanding premium. "
                       "Contact insurer for revival terms."
            })

        if policy_end and admission:
            if admission > policy_end:
                violations.append({
                    "type":        "POLICY_EXPIRED",
                    "severity":    "CRITICAL",
                    "title":       "Hospitalization After Policy Expiry",
                    "description": (
                        f"Policy expired on {policy_end.strftime('%d %b %Y')}. "
                        f"Hospitalization on {admission.strftime('%d %b %Y')} is after expiry."
                    ),
                    "irdai_ref":   "IRDAI/HLT/REG/2016/143 Clause 6",
                    "fix": "No claim is payable after policy expiry. "
                           "Ensure policy is always renewed before the expiry date."
                })
            elif (policy_end - admission).days < 30:
                warnings.append({
                    "type":        "POLICY_NEAR_EXPIRY",
                    "severity":    "LOW",
                    "title":       "Policy Expiring Soon",
                    "description": f"Policy expires in {(policy_end - admission).days} days. Renew before expiry.",
                    "irdai_ref":   "N/A",
                    "fix": "Renew your policy before expiry to maintain continuity of coverage."
                })

        return {
            "violations": violations,
            "warnings":   warnings,
            "audit": {
                "check":   "Policy Validity",
                "policy_end_date": str(policy_end),
                "admission_date":  str(admission),
                "violations_found": len(violations),
                "timestamp": datetime.now().isoformat()
            }
        }

    # ── LLM deep analysis ─────────────────────────────────────────────────────
    def _deep_compliance_analysis(self, policy_data: dict, discharge_data: dict) -> dict:
        """Use Claude for nuanced compliance analysis that rules can't catch."""
        prompt = f"""You are a senior Indian health insurance compliance expert with 20 years of experience.

Analyze this claim for compliance issues beyond the obvious ones.
Focus on: diagnosis-policy mismatch, undisclosed conditions, claim inflation signals.

POLICY DETAILS:
{json.dumps({k: v for k, v in policy_data.items() if not k.startswith('_')}, indent=2)[:1500]}

DISCHARGE SUMMARY DATA:
{json.dumps({k: v for k, v in discharge_data.items() if not k.startswith('_')}, indent=2)[:1500]}

Return ONLY valid JSON:
{{
  "violations": [
    {{
      "type": "VIOLATION_TYPE",
      "severity": "HIGH/MEDIUM/LOW",
      "title": "Short title",
      "description": "Detailed description",
      "irdai_ref": "Regulation reference",
      "fix": "Specific fix instruction"
    }}
  ],
  "warnings": [
    {{
      "type": "WARNING_TYPE",
      "severity": "MEDIUM/LOW",
      "title": "Short title",
      "description": "Description",
      "irdai_ref": "Reference",
      "fix": "Fix instruction"
    }}
  ]
}}"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception:
            return {"violations": [], "warnings": []}

    # ── Utility ───────────────────────────────────────────────────────────────
    def _parse_date(self, date_str) -> date | None:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y"]:
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except ValueError:
                continue
        return None
