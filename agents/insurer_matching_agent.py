"""
Insurer Matching Agent
Given a diagnosis or health condition, recommends the best Indian health
insurers ranked by suitability, coverage terms, and claim experience.
Also works in reverse — given a policy, shows coverage gaps.
"""

import json
import sys
import os
from datetime import datetime
from anthropic import Anthropic

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from data.insurer_data.insurer_profiles import INSURER_PROFILES, CONDITION_INSURER_MAP


class InsurerMatchingAgent:

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Insurer Matching Agent"
        self.insurers   = {i["id"]: i for i in INSURER_PROFILES}

    # ── Main entry: match insurers to condition ───────────────────────────────
    def match(self, condition: str, age: int = 35,
              budget: str = "medium", existing_policy: str = None) -> dict:
        """
        Find best insurers for a health condition.

        Args:
            condition:       Diagnosis or health condition (e.g. "diabetes", "knee surgery")
            age:             Age of the patient/policyholder
            budget:          "low" | "medium" | "high"
            existing_policy: Name of existing insurer if checking gaps

        Returns:
            Ranked list of insurers with reasoning, scores, and action items.
        """

        # Step 1: Rule-based pre-filter using condition map
        candidate_ids = self._rule_based_match(condition)

        # Step 2: Score all insurers
        scored = self._score_insurers(condition, age, budget, candidate_ids)

        # Step 3: LLM deep analysis
        llm_result = self._llm_analysis(condition, age, budget,
                                         scored[:5], existing_policy)

        # Step 4: Build final ranked list
        ranked = self._build_ranked_list(scored, llm_result)

        # Step 5: Generate action items
        actions = self._generate_actions(condition, ranked[:3],
                                          existing_policy, llm_result)

        return {
            "_agent":           self.agent_name,
            "_timestamp":       datetime.now().isoformat(),
            "condition":        condition,
            "age":              age,
            "budget":           budget,
            "total_insurers":   len(INSURER_PROFILES),
            "ranked_insurers":  ranked,
            "top_pick":         ranked[0] if ranked else None,
            "action_items":     actions,
            "llm_summary":      llm_result.get("summary", ""),
            "key_warning":      llm_result.get("key_warning", ""),
            "irdai_note":       llm_result.get("irdai_note", ""),
        }

    # ── Rule-based pre-filter ─────────────────────────────────────────────────
    def _rule_based_match(self, condition: str) -> list:
        """Return list of insurer IDs that are known good for this condition."""
        condition_lower = condition.lower()
        matched_ids = set()

        for keyword, ids in CONDITION_INSURER_MAP.items():
            if keyword in condition_lower:
                matched_ids.update(ids)

        # If no specific match, return all
        if not matched_ids:
            matched_ids = set(self.insurers.keys())

        return list(matched_ids)

    # ── Score all insurers ────────────────────────────────────────────────────
    def _score_insurers(self, condition: str, age: int,
                         budget: str, priority_ids: list) -> list:
        """
        Score each insurer 0-100 based on:
        - Condition-specific coverage (40pts)
        - Claim settlement ratio (20pts)
        - Age suitability (15pts)
        - Budget fit (15pts)
        - Network size (10pts)
        """
        scored = []
        condition_lower = condition.lower()

        for ins in INSURER_PROFILES:
            score = 0
            reasons = []
            warnings = []

            # ── Condition match (40pts) ───────────────────────────────────────
            cond_score = 0
            if ins["id"] in priority_ids:
                cond_score += 25
                reasons.append("Specialised coverage for this condition")

            # Check special coverages
            for cond_key, cov_detail in ins.get("special_coverages", {}).items():
                if cond_key in condition_lower or any(
                    word in condition_lower for word in cond_key.split()
                ):
                    cond_score += 15
                    reasons.append(f"Special coverage: {cov_detail[:80]}")
                    break

            # Check best_for list
            for tag in ins.get("best_for", []):
                if tag in condition_lower or condition_lower in tag:
                    cond_score = min(cond_score + 10, 40)
                    break

            score += min(cond_score, 40)

            # ── Claim settlement ratio (20pts) ────────────────────────────────
            csr = ins["claim_settlement_ratio"]
            if csr >= 99:
                score += 20; reasons.append(f"Excellent claim settlement: {csr}%")
            elif csr >= 97:
                score += 16; reasons.append(f"Very good claim settlement: {csr}%")
            elif csr >= 95:
                score += 12; reasons.append(f"Good claim settlement: {csr}%")
            elif csr >= 90:
                score += 8
            else:
                score += 4
                warnings.append(f"Claim settlement ratio is {csr}% — below industry average")

            # ── Age suitability (15pts) ───────────────────────────────────────
            if age <= ins["entry_age_max"]:
                if age >= 60:
                    if "senior" in " ".join(ins.get("best_for", [])):
                        score += 15
                        reasons.append("Dedicated senior citizen plan available")
                    else:
                        score += 8
                        warnings.append("Not specialised for senior citizens")
                else:
                    score += 15
            else:
                score += 0
                warnings.append(f"Age {age} may exceed entry limit for some plans")

            # ── Budget fit (15pts) ────────────────────────────────────────────
            if budget == "low":
                if ins["id"] in ["new_india", "united_india", "oriental"]:
                    score += 15
                    reasons.append("Government insurer — lowest premium")
                elif ins["id"] in ["star_health", "care_health"]:
                    score += 8
                else:
                    score += 5
                    warnings.append("Premium may be higher than budget")
            elif budget == "medium":
                if ins["id"] in ["star_health", "icici_lombard", "bajaj_allianz"]:
                    score += 15
                    reasons.append("Good value for mid-range budget")
                else:
                    score += 10
            else:  # high
                if ins["id"] in ["hdfc_ergo", "niva_bupa", "care_health",
                                   "reliance_health"]:
                    score += 15
                    reasons.append("Premium plans with no room rent capping")
                else:
                    score += 8

            # ── Network size (10pts) ──────────────────────────────────────────
            net = ins["network_hospitals"]
            if net >= 12000:
                score += 10
            elif net >= 9000:
                score += 8
            elif net >= 7000:
                score += 6
            else:
                score += 4
                warnings.append(f"Network of {net:,} hospitals may be limited in some areas")

            # ── PED waiting period bonus ──────────────────────────────────────
            ped = ins["ped_waiting_months"]
            if ped <= 36:
                score += 3
                reasons.append(f"Shorter PED waiting period: {ped} months")

            # ── Room rent capping penalty ─────────────────────────────────────
            if "no room" in ins["room_rent_limit"].lower():
                score += 2
                reasons.append("No room rent capping on premium plans")
            else:
                warnings.append("Room rent sub-limit applies — check before admission")

            scored.append({
                "insurer":      ins,
                "score":        min(score, 100),
                "reasons":      reasons[:4],
                "warnings":     warnings[:3],
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ── LLM deep analysis ────────────────────────────────────────────────────
    def _llm_analysis(self, condition: str, age: int, budget: str,
                       top_scored: list, existing_policy: str) -> dict:
        """Use Claude for nuanced, expert-level insurer recommendation."""

        top_names = [s["insurer"]["name"] for s in top_scored]

        prompt = f"""You are India's foremost health insurance advisor with 25 years of experience 
helping patients choose the right insurer for their specific medical conditions.

A patient needs advice on health insurance.

CONDITION: {condition}
AGE: {age} years
BUDGET: {budget}
EXISTING POLICY: {existing_policy or "None"}

TOP INSURERS BY RULE-BASED SCORING:
{chr(10).join(f"{i+1}. {name}" for i, name in enumerate(top_names))}

Based on your deep expertise of Indian health insurance market, provide:

Return ONLY valid JSON:
{{
  "summary": "2-3 sentence expert summary of best choice for this condition",
  "top_recommendation": "name of single best insurer for this specific condition and age",
  "top_reason": "specific reason why this insurer is best for this exact condition",
  "key_warning": "most important thing patient must check before buying — specific to this condition",
  "irdai_note": "relevant IRDAI regulation the patient should know for this condition",
  "gap_analysis": "if existing policy mentioned, what gaps exist",
  "buying_tip": "one specific actionable tip for buying insurance for this condition"
}}"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=800,
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
                "summary": f"Based on your condition ({condition}), "
                           f"{top_names[0] if top_names else 'Star Health'} "
                           f"is the recommended insurer.",
                "top_recommendation": top_names[0] if top_names else "Star Health",
                "top_reason": "Best claim settlement ratio and condition-specific plans",
                "key_warning": "Always disclose pre-existing conditions at proposal stage",
                "irdai_note": "PED waiting period cannot exceed 48 months under IRDAI regulations",
                "gap_analysis": "",
                "buying_tip": "Buy before any hospitalisation — claims on new policies within 30 days are rejected"
            }

    # ── Build ranked list ─────────────────────────────────────────────────────
    def _build_ranked_list(self, scored: list, llm_result: dict) -> list:
        ranked = []
        llm_top = llm_result.get("top_recommendation", "").lower()

        for i, item in enumerate(scored[:10]):
            ins    = item["insurer"]
            rank   = i + 1
            is_top = (llm_top in ins["name"].lower() or
                      llm_top in ins["short_name"].lower())

            # Boost LLM top pick to rank 1 if it's in top 3
            if is_top and rank <= 3:
                rank = 1

            ranked.append({
                "rank":             rank,
                "insurer_id":       ins["id"],
                "name":             ins["name"],
                "short_name":       ins["short_name"],
                "logo_color":       ins["logo_color"],
                "score":            item["score"],
                "claim_settlement": ins["claim_settlement_ratio"],
                "network":          ins["network_hospitals"],
                "ped_waiting":      ins["ped_waiting_months"],
                "room_rent":        ins["room_rent_limit"],
                "sum_insured":      ins["sum_insured_range"],
                "copay":            ins["copay"],
                "best_plans":       ins["plans"][:3],
                "strengths":        ins["strengths"][:3],
                "warnings":         item["warnings"][:2],
                "reasons":          item["reasons"][:3],
                "helpline":         ins["claims_helpline"],
                "tpa":              ins["tpa"],
                "is_top_pick":      is_top,
                "special_note":     llm_result.get("top_reason", "") if is_top else "",
            })

        # Re-sort: top pick first, then by score
        ranked.sort(key=lambda x: (0 if x["is_top_pick"] else 1, -x["score"]))

        # Re-assign ranks
        for i, item in enumerate(ranked):
            item["rank"] = i + 1

        return ranked

    # ── Generate action items ─────────────────────────────────────────────────
    def _generate_actions(self, condition: str, top_3: list,
                           existing_policy: str, llm_result: dict) -> list:
        actions = []

        if llm_result.get("buying_tip"):
            actions.append({
                "priority": "HIGH",
                "action":   "Key Buying Tip",
                "detail":   llm_result["buying_tip"],
                "icon":     "💡"
            })

        if llm_result.get("key_warning"):
            actions.append({
                "priority": "HIGH",
                "action":   "Important Warning",
                "detail":   llm_result["key_warning"],
                "icon":     "⚠️"
            })

        if top_3:
            actions.append({
                "priority": "MEDIUM",
                "action":   f"Call {top_3[0]['short_name']} for a quote",
                "detail":   f"Helpline: {top_3[0]['helpline']}. Ask specifically "
                            f"for coverage terms for '{condition}' and PED waiting period.",
                "icon":     "📞"
            })

        if llm_result.get("irdai_note"):
            actions.append({
                "priority": "MEDIUM",
                "action":   "Know Your IRDAI Rights",
                "detail":   llm_result["irdai_note"],
                "icon":     "⚖️"
            })

        actions.append({
            "priority": "LOW",
            "action":   "Always disclose pre-existing conditions",
            "detail":   "Non-disclosure of any pre-existing condition at proposal stage "
                        "gives the insurer grounds to repudiate the claim. "
                        "Disclose everything — even conditions you think are minor.",
            "icon":     "📋"
        })

        return actions
