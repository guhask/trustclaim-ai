"""
Grievance Letter Generator Agent
When a claim is rejected, generates two documents:
1. Formal grievance letter to the insurer (IRDAI-cited)
2. Insurance Ombudsman complaint template (if insurer doesn't respond)

This closes the full claim lifecycle:
Pre-filing → Filing → Rejection → Appeal → Ombudsman
"""

import json
from datetime import datetime, date
from anthropic import Anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                 Spacer, HRFlowable, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL


class GrievanceLetter:

    TEAL      = HexColor("#0F6E56")
    TEAL_DARK = HexColor("#0A4A38")
    TEAL_LT   = HexColor("#E1F5EE")
    BLUE      = HexColor("#185FA5")
    RED       = HexColor("#E24B4A")
    GRAY      = HexColor("#555555")
    LGRAY     = HexColor("#F5F5F2")
    BORDER    = HexColor("#D8D8D2")
    INK       = HexColor("#1A1A1A")

    def __init__(self):
        self.client     = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.agent_name = "Grievance Letter Generator"

    # ── Main entry point ──────────────────────────────────────────────────────
    def generate(self, rejection_details: dict,
                 policy_data: dict, output_path: str) -> dict:
        """
        Generate grievance letter and ombudsman complaint.
        rejection_details: {
            insurer_name, policy_number, claim_number,
            rejection_date, rejection_reason, rejection_amount,
            patient_name, policyholder_name, policyholder_address,
            policyholder_phone, policyholder_email,
            hospital_name, admission_date, discharge_date,
            diagnosis, irdai_violations (list of strings)
        }
        Returns: { letter_path, ombudsman_path, key_arguments }
        """

        # Step 1: Build legal arguments from rejection reason
        arguments = self._build_arguments(rejection_details, policy_data)

        # Step 2: Generate letter body via LLM
        letter_body = self._llm_letter(rejection_details, arguments)

        # Step 3: Generate ombudsman complaint body
        ombudsman_body = self._llm_ombudsman(rejection_details, arguments)

        # Step 4: Render grievance letter PDF
        letter_path     = output_path.replace(".pdf", "_grievance.pdf")
        ombudsman_path  = output_path.replace(".pdf", "_ombudsman.pdf")

        self._render_grievance_pdf(letter_path, rejection_details,
                                    letter_body, arguments)
        self._render_ombudsman_pdf(ombudsman_path, rejection_details,
                                    ombudsman_body, arguments)

        return {
            "_agent":          self.agent_name,
            "_timestamp":      datetime.now().isoformat(),
            "letter_path":     letter_path,
            "ombudsman_path":  ombudsman_path,
            "key_arguments":   arguments,
            "letter_preview":  letter_body.get("opening", ""),
        }

    # ── Build legal arguments ─────────────────────────────────────────────────
    def _build_arguments(self, rd: dict, policy_data: dict) -> list:
        """Map rejection reason to IRDAI regulations the insurer may have violated."""
        arguments = []
        reason = str(rd.get("rejection_reason", "")).lower()

        # Vague rejection — IRDAI mandates specific written reason
        arguments.append({
            "argument":  "Right to Written Rejection with Specific Clause",
            "irdai_ref": "IRDAI/HLT/CIR/2020/154",
            "law":       "IRDAI regulations require that claim rejections must cite "
                         "the exact policy clause or regulation violated. Verbal or "
                         "vague rejections without written specific grounds are invalid.",
            "strength":  "HIGH"
        })

        # Settlement timeline violation
        arguments.append({
            "argument":  "Claim Settlement Timeline Violation",
            "irdai_ref": "IRDAI/HLT/CIR/2024/017",
            "law":       "Under IRDAI mandate, all health insurance claims must be "
                         "settled within 30 days of receiving the last necessary document. "
                         "Delays attract penal interest at 2% above bank rate per annum.",
            "strength":  "HIGH"
        })

        # PED-related rejection
        if any(w in reason for w in ["pre-existing", "ped", "pre existing",
                                      "prior condition", "pre-condition"]):
            arguments.append({
                "argument":  "Pre-Existing Disease Disclosure Was Complete",
                "irdai_ref": "IRDAI/HLT/REG/2016/143 Clause 4",
                "law":       "IRDAI defines PED as conditions diagnosed within 48 months "
                             "prior to policy inception. Insurer must demonstrate the condition "
                             "was diagnosed before policy start date with medical evidence. "
                             "PED waiting period cannot exceed 48 months under IRDAI.",
                "strength":  "HIGH"
            })

        # Documentation rejection
        if any(w in reason for w in ["document", "incomplete", "missing",
                                      "insufficient", "records"]):
            arguments.append({
                "argument":  "Cannot Reject for Documents Beyond Standard List",
                "irdai_ref": "IRDAI/HLT/CIR/2021/189",
                "law":       "IRDAI mandates that insurers cannot reject a claim solely "
                             "for want of additional documents beyond the standard required list. "
                             "The standard document checklist is prescribed by IRDAI and is exhaustive.",
                "strength":  "HIGH"
            })

        # Exclusion-based rejection
        if any(w in reason for w in ["excluded", "exclusion", "not covered",
                                      "not payable"]):
            arguments.append({
                "argument":  "Exclusion Not Clearly Disclosed at Policy Inception",
                "irdai_ref": "IRDAI/HLT/REG/2016/143 Schedule II",
                "law":       "IRDAI requires all exclusions to be clearly communicated "
                             "to the policyholder at the time of policy issuance. Exclusions "
                             "not explicitly disclosed in the policy schedule cannot be invoked "
                             "to reject a claim.",
                "strength":  "MEDIUM"
            })

        # Cashless/pre-auth rejection
        if any(w in reason for w in ["cashless", "pre-auth", "pre auth",
                                      "authorization", "network"]):
            arguments.append({
                "argument":  "Cashless Pre-Authorization Timeline Violated",
                "irdai_ref": "IRDAI/HLT/CIR/2023/205",
                "law":       "IRDAI Master Circular 2023 mandates cashless authorization "
                             "within 1 hour for planned admissions and 30 minutes for emergencies. "
                             "Failure to respond within this timeline is a regulatory violation.",
                "strength":  "HIGH"
            })

        # Waiting period rejection
        if any(w in reason for w in ["waiting period", "waiting", "inception",
                                      "30 days", "initial"]):
            arguments.append({
                "argument":  "Treatment Was for Accidental Injury — Waiting Period Not Applicable",
                "irdai_ref": "IRDAI/HLT/REG/2016/143",
                "law":       "The initial 30-day waiting period does not apply to accidental "
                             "injuries requiring immediate hospitalisation. If treatment was "
                             "accident-related, the waiting period exclusion cannot be applied.",
                "strength":  "MEDIUM"
            })

        # Ombudsman right — always include
        arguments.append({
            "argument":  "Right to Approach Insurance Ombudsman",
            "irdai_ref": "IRDAI Ombudsman Rules 2017",
            "law":       "If the insurer does not resolve the grievance within 30 days, "
                         "the policyholder has the right to approach the Insurance Ombudsman "
                         "free of cost within 1 year of the rejection date. The Ombudsman "
                         "decision is binding on the insurer.",
            "strength":  "HIGH"
        })

        return arguments

    # ── LLM letter generation ─────────────────────────────────────────────────
    def _llm_letter(self, rd: dict, arguments: list) -> dict:
        """
        Generate letter paragraphs. First builds rich content directly from
        rejection details, then tries LLM to enhance further.
        The direct-generation fallback is strong enough to stand on its own.
        """
        # ── Direct generation (works without LLM) ────────────────────────────
        insurer  = rd.get("insurer_name", "the Insurance Company")
        policy   = rd.get("policy_number", "N/A")
        claim    = rd.get("claim_number", "N/A")
        amount   = rd.get("rejection_amount", "N/A")
        patient  = rd.get("patient_name", rd.get("policyholder_name", "the patient"))
        hospital = rd.get("hospital_name", "the hospital")
        diag     = rd.get("diagnosis", "the diagnosed condition")
        adm      = rd.get("admission_date", "")
        dis      = rd.get("discharge_date", "")
        reason   = rd.get("rejection_reason", "reasons not clearly specified")
        rej_date = rd.get("rejection_date", "")

        adm_dis = ""
        if adm and dis:
            adm_dis = f"from {adm} to {dis}"
        elif adm:
            adm_dis = f"on {adm}"

        # Pick most relevant IRDAI refs from arguments
        top_refs = " | ".join(
            f"{a['irdai_ref']}" for a in arguments[:3]
        )

        direct = {
            "opening": (
                f"I, {rd.get('policyholder_name', 'the undersigned')}, hold Policy No. {policy} "
                f"issued by {insurer}. I am writing to formally appeal and challenge the rejection of "
                f"my health insurance claim (Claim No. {claim}) amounting to Rs.{amount}, "
                f"communicated to me{f' on {rej_date}' if rej_date else ''}. "
                f"I submit that the rejection is unjustified, procedurally defective, and in "
                f"violation of IRDAI regulations."
            ),
            "background": (
                f"{patient} was admitted to {hospital} {adm_dis} "
                f"for treatment of {diag}. "
                f"All required documents were submitted as per the standard checklist prescribed "
                f"by IRDAI/HLT/CIR/2021/189. A claim of Rs.{amount} was filed in accordance with "
                f"the terms and conditions of the above policy. Despite complete documentation "
                f"and a valid claim, {insurer} has rejected the claim citing: "
                f"'{reason}'."
            ),
            "grievance": (
                f"The rejection by {insurer} is legally untenable on the following grounds: "
                f"First, under IRDAI/HLT/CIR/2020/154, rejection letters must cite the exact "
                f"policy clause or regulation violated — a vague or general reason does not "
                f"meet this standard. "
                f"Second, under IRDAI/HLT/CIR/2024/017, claims must be settled within 30 days "
                f"of the last document; undue delay attracts penal interest at 2% above bank rate. "
                f"Third, the grounds cited ({reason}) do not constitute a valid basis for rejection "
                f"under the applicable IRDAI framework ({top_refs}). "
                f"I reserve the right to seek all remedies available under IRDAI regulations and "
                f"the Insurance Ombudsman Rules, 2017."
            ),
            "demand": (
                f"I hereby demand that {insurer} reconsider and settle Claim No. {claim} "
                f"for Rs.{amount} in full within <b>15 days</b> of receipt of this letter. "
                f"In the event of non-compliance or continued silence, I will, without further "
                f"notice, approach the Insurance Ombudsman under the IRDAI (Insurance Ombudsman) "
                f"Rules, 2017, and also file a complaint with IRDAI's Bima Bharosa grievance "
                f"portal. I also reserve the right to claim penal interest under "
                f"IRDAI/HLT/CIR/2024/017 for the delay already incurred."
            ),
            "closing": (
                f"I trust that {insurer} will act in accordance with IRDAI regulations and "
                f"settle this matter without necessitating further escalation. "
                f"I remain available for any clarification required."
            )
        }

        # ── Try LLM enhancement ───────────────────────────────────────────────
        try:
            args_text = "\n".join(
                f"- {a['argument']} ({a['irdai_ref']})"
                for a in arguments[:4]
            )
            prompt = f"""You are an expert insurance consumer rights lawyer in India.
Enhance the grievance paragraphs below to be more forceful and legally precise.
Keep the same structure. Incorporate the legal arguments naturally.
Return ONLY valid JSON with same keys: opening, background, grievance, demand, closing.

REJECTION REASON: {reason}
INSURER: {insurer}
AMOUNT: Rs.{amount}
LEGAL ARGUMENTS: {args_text}

CURRENT PARAGRAPHS:
{json.dumps(direct, indent=2)[:2000]}"""

            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            enhanced = json.loads(raw.strip())
            # Only use enhanced if all keys present
            if all(k in enhanced for k in direct.keys()):
                return enhanced
        except Exception:
            pass  # Fall through to direct generation

        return direct

    # ── LLM ombudsman complaint ───────────────────────────────────────────────
    def _llm_ombudsman(self, rd: dict, arguments: list) -> dict:
        prompt = f"""Draft a concise Insurance Ombudsman complaint for a rejected health 
insurance claim in India. The complaint should be factual, reference IRDAI rules,
and clearly state the relief sought.

DETAILS:
- Insurer: {rd.get('insurer_name', 'N/A')}
- Policy No: {rd.get('policy_number', 'N/A')}
- Claim rejected: Rs.{rd.get('rejection_amount', 'N/A')}
- Rejection reason: {rd.get('rejection_reason', 'N/A')}
- Grievance filed with insurer: Yes (no response within 30 days)

Return ONLY valid JSON:
{{
  "statement_of_facts": "2-3 sentence factual summary of the dispute",
  "grounds_of_complaint": "2-3 sentence grounds citing IRDAI violations",
  "relief_sought": "Specific relief requested (settlement amount + interest)",
  "declaration": "Standard declaration sentence"
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
            amount  = rd.get("rejection_amount", "N/A")
            insurer = rd.get("insurer_name", "the insurer")
            patient = rd.get("patient_name", rd.get("policyholder_name", "the patient"))
            hospital = rd.get("hospital_name", "the hospital")
            diag    = rd.get("diagnosis", "the diagnosed condition")
            reason  = rd.get("rejection_reason", "not clearly specified")
            adm     = rd.get("admission_date", "")
            dis     = rd.get("discharge_date", "")
            return {
                "statement_of_facts": (
                    f"I hold Policy No. {rd.get('policy_number','N/A')} with {insurer}. "
                    f"{patient} was admitted to {hospital}{f' from {adm} to {dis}' if adm and dis else ''} "
                    f"for {diag}. A claim of Rs.{amount} was submitted with complete documentation. "
                    f"{insurer} rejected the claim citing '{reason}'. "
                    f"A formal grievance was sent to the insurer but no response was received "
                    f"within 30 days as required by IRDAI/HLT/CIR/2024/017."
                ),
                "grounds_of_complaint": (
                    f"The rejection by {insurer} violates multiple IRDAI regulations: "
                    f"(1) IRDAI/HLT/CIR/2020/154 — Rejection does not cite specific policy clause. "
                    f"(2) IRDAI/HLT/CIR/2024/017 — Claim not settled within 30 days of last document. "
                    f"(3) IRDAI/HLT/CIR/2021/189 — Cannot reject for documents beyond standard list. "
                    f"The stated reason '{reason}' does not constitute valid grounds for rejection "
                    f"under applicable IRDAI framework."
                ),
                "relief_sought": (
                    f"(1) Settlement of Claim No. {rd.get('claim_number','N/A')} for Rs.{amount} in full. "
                    f"(2) Penal interest at 2% above bank rate per annum from date of claim submission "
                    f"until date of actual settlement, as per IRDAI/HLT/CIR/2024/017. "
                    f"(3) Compliance direction to {insurer} to follow IRDAI claim settlement guidelines."
                ),
                "declaration": (
                    "I declare that the information provided in this complaint is true and correct "
                    "to the best of my knowledge. I have not filed any complaint before any other "
                    "forum on the same subject matter."
                )
            }

    # ── Render grievance PDF ──────────────────────────────────────────────────
    def _render_grievance_pdf(self, path: str, rd: dict,
                               body: dict, arguments: list):
        doc = SimpleDocTemplate(path, pagesize=A4,
                                 leftMargin=2.5*cm, rightMargin=2.5*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        story = []

        def ps(name, **kw):
            defaults = dict(fontName='Helvetica', fontSize=10,
                            leading=15, textColor=self.INK)
            defaults.update(kw)
            return ParagraphStyle(name, **defaults)

        def hline(c=self.BORDER, t=0.5, sb=6, sa=6):
            return HRFlowable(width="100%", thickness=t,
                              color=c, spaceBefore=sb, spaceAfter=sa)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = Table([[
            Paragraph(
                f"<font size='7' color='#0F6E56'><b>FORMAL GRIEVANCE — HEALTH INSURANCE CLAIM REJECTION APPEAL</b></font><br/>"
                f"<font size='14'><b>{rd.get('policyholder_name', 'Policyholder')}</b></font><br/>"
                f"<font size='8' color='#555'>{rd.get('policyholder_address', '')}</font>",
                ps('ph', fontName='Helvetica', fontSize=14)
            ),
            Paragraph(
                f"<font size='8' color='#555'>Date: {date.today().strftime('%d %B %Y')}<br/>"
                f"Policy No: {rd.get('policy_number','N/A')}<br/>"
                f"Claim No: {rd.get('claim_number','N/A')}<br/>"
                f"Phone: {rd.get('policyholder_phone','N/A')}<br/>"
                f"Email: {rd.get('policyholder_email','N/A')}</font>",
                ps('pr', fontName='Helvetica', fontSize=8,
                   alignment=TA_RIGHT)
            )
        ]], colWidths=[11*cm, 6.5*cm])
        hdr.setStyle(TableStyle([
            ("VALIGN",  (0,0), (-1,-1), "TOP"),
            ("PADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(hdr)
        story.append(hline(self.TEAL, 1.5, 8, 8))

        # ── Addressee ─────────────────────────────────────────────────────────
        story.append(Paragraph("To,", ps('to', fontSize=10)))
        story.append(Paragraph(
            f"<b>The Grievance Officer</b><br/>"
            f"{rd.get('insurer_name', 'Insurance Company')}<br/>"
            f"(via Registered Post / Email to Grievance Cell)",
            ps('addr', fontSize=10, leading=16)
        ))
        story.append(Spacer(1, 0.3*cm))

        # ── Subject ───────────────────────────────────────────────────────────
        story.append(Paragraph(
            f"<b>Subject: Formal Grievance and Appeal against Rejection of Health Insurance "
            f"Claim No. {rd.get('claim_number','N/A')} under Policy No. {rd.get('policy_number','N/A')}</b>",
            ps('subj', fontSize=10, leading=15,
               textColor=self.TEAL_DARK)
        ))
        story.append(hline(self.TEAL_LT, 0.5, 4, 8))

        # ── Salutation ────────────────────────────────────────────────────────
        story.append(Paragraph("Dear Sir / Madam,",
                                ps('sal', fontSize=10)))
        story.append(Spacer(1, 0.2*cm))

        # ── Letter body ───────────────────────────────────────────────────────
        for para_key in ["opening", "background", "grievance", "demand", "closing"]:
            text = body.get(para_key, "")
            if text:
                story.append(Paragraph(text, ps(f'b_{para_key}',
                                                  fontSize=10, leading=16,
                                                  alignment=TA_JUSTIFY,
                                                  spaceAfter=8)))

        story.append(Spacer(1, 0.3*cm))

        # ── Claim facts table ─────────────────────────────────────────────────
        story.append(Paragraph("<b>Claim Details (For Reference):</b>",
                                ps('ct', fontSize=10,
                                   fontName='Helvetica-Bold')))
        story.append(Spacer(1, 0.1*cm))

        facts = [
            ["Patient Name",     rd.get("patient_name","N/A"),
             "Hospital",         rd.get("hospital_name","N/A")],
            ["Admission Date",   str(rd.get("admission_date","N/A")),
             "Discharge Date",   str(rd.get("discharge_date","N/A"))],
            ["Diagnosis",        rd.get("diagnosis","N/A"),
             "Rejected Amount",  f"Rs.{rd.get('rejection_amount','N/A')}"],
            ["Rejection Date",   str(rd.get("rejection_date","N/A")),
             "Rejection Reason", rd.get("rejection_reason","N/A")[:50]+"..." if len(str(rd.get("rejection_reason",""))) > 50 else rd.get("rejection_reason","N/A")],
        ]

        tbl_data = []
        for row in facts:
            tbl_data.append([
                Paragraph(f"<font color='#555' size='8'>{row[0]}</font>",
                          ps(f'fl_{row[0][:3]}', fontSize=8)),
                Paragraph(f"<b><font size='8'>{row[1]}</font></b>",
                          ps(f'fv_{row[0][:3]}', fontSize=8)),
                Paragraph(f"<font color='#555' size='8'>{row[2]}</font>",
                          ps(f'fl2_{row[0][:3]}', fontSize=8)),
                Paragraph(f"<b><font size='8'>{row[3]}</font></b>",
                          ps(f'fv2_{row[0][:3]}', fontSize=8)),
            ])

        facts_tbl = Table(tbl_data,
                          colWidths=[3.5*cm, 5.5*cm, 3.5*cm, 5*cm])
        facts_tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0,0), (-1,-1),
             [white, HexColor("#F9F9F7")]),
            ("GRID",    (0,0), (-1,-1), 0.3, self.BORDER),
            ("PADDING", (0,0), (-1,-1), 5),
            ("VALIGN",  (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(facts_tbl)
        story.append(Spacer(1, 0.3*cm))

        # ── IRDAI regulations cited ────────────────────────────────────────────
        story.append(Paragraph(
            "<b>IRDAI Regulations Supporting This Appeal:</b>",
            ps('rt', fontSize=10, fontName='Helvetica-Bold')
        ))
        story.append(Spacer(1, 0.1*cm))

        for i, arg in enumerate(arguments[:5], 1):
            color = self.RED if arg["strength"] == "HIGH" else self.TEAL
            story.append(Paragraph(
                f"<font color='#0F6E56'><b>{i}. {arg['argument']}</b></font> "
                f"<font size='8' color='#555'>[{arg['irdai_ref']}]</font><br/>"
                f"<font size='9' color='#444'>{arg['law']}</font>",
                ps(f'arg_{i}', fontSize=9, leading=14,
                   leftIndent=8, spaceAfter=6)
            ))

        story.append(Spacer(1, 0.4*cm))

        # ── Signature block ───────────────────────────────────────────────────
        story.append(Paragraph("Yours faithfully,",
                                ps('yf', fontSize=10)))
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(
            f"<b>{rd.get('policyholder_name','')}</b><br/>"
            f"Policy No: {rd.get('policy_number','N/A')}<br/>"
            f"Date: {date.today().strftime('%d %B %Y')}",
            ps('sig', fontSize=10, leading=16)
        ))

        story.append(hline(self.TEAL_LT, 0.5, 8, 4))
        story.append(Paragraph(
            f"<font size='7' color='#888'>Generated by TrustClaim AI — Pre-Filing Claim Intelligence Platform | "
            f"This letter is for consumer rights purposes. Consult a legal professional for complex disputes.</font>",
            ps('ft', fontSize=7, alignment=TA_CENTER, textColor=self.GRAY)
        ))

        doc.build(story)

    # ── Render ombudsman PDF ──────────────────────────────────────────────────
    def _render_ombudsman_pdf(self, path: str, rd: dict,
                               body: dict, arguments: list):
        doc = SimpleDocTemplate(path, pagesize=A4,
                                 leftMargin=2.5*cm, rightMargin=2.5*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        story = []

        def ps(name, **kw):
            defaults = dict(fontName='Helvetica', fontSize=10,
                            leading=15, textColor=self.INK)
            defaults.update(kw)
            return ParagraphStyle(name, **defaults)

        def hline(c=self.BORDER, t=0.5, sb=6, sa=6):
            return HRFlowable(width="100%", thickness=t,
                              color=c, spaceBefore=sb, spaceAfter=sa)

        # Header band
        hdr_tbl = Table([[
            Paragraph(
                "<font size='8' color='#0F6E56'><b>COMPLAINT TO INSURANCE OMBUDSMAN</b></font><br/>"
                "<font size='13'><b>Form of Complaint</b></font><br/>"
                "<font size='8' color='#555'>Under IRDAI (Insurance Ombudsman) Rules, 2017</font>",
                ps('oh', fontName='Helvetica', fontSize=13)
            ),
            Paragraph(
                f"<font size='8' color='#555'>"
                f"Date: {date.today().strftime('%d %B %Y')}<br/>"
                f"Ref: {rd.get('policy_number','N/A')}<br/>"
                f"Against: {rd.get('insurer_name','N/A')}</font>",
                ps('ohr', fontSize=8, alignment=TA_RIGHT)
            )
        ]], colWidths=[11*cm, 6.5*cm])
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN",  (0,0), (-1,-1), "TOP"),
            ("PADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(hdr_tbl)
        story.append(hline(self.BLUE, 1.5, 8, 8))

        # Important notice box
        notice = Table([[
            Paragraph(
                "<b>⚠️ When to use this form:</b> File this complaint with your "
                "regional Insurance Ombudsman ONLY if: (1) the insurer has rejected "
                "your grievance OR (2) the insurer has not responded within 30 days "
                "of your formal grievance letter. Filing is FREE. Find your Ombudsman at "
                "<font color='#185FA5'>ecoi.co.in</font>",
                ps('notice', fontSize=8, leading=13, textColor=HexColor("#185FA5"))
            )
        ]], colWidths=[17*cm])
        notice.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), HexColor("#E6F1FB")),
            ("PADDING",    (0,0), (-1,-1), 10),
            ("LINEABOVE",  (0,0), (-1,0),  1, self.BLUE),
        ]))
        story.append(notice)
        story.append(Spacer(1, 0.3*cm))

        # Part A: Complainant details
        story.append(Paragraph("<b>PART A — COMPLAINANT DETAILS</b>",
                                ps('pah', fontSize=10, fontName='Helvetica-Bold',
                                   textColor=self.TEAL_DARK)))
        story.append(hline(self.TEAL_LT, 0.5, 2, 6))

        comp_data = [
            ["Full Name of Complainant", rd.get("policyholder_name",""), "Policy Number", rd.get("policy_number","")],
            ["Contact Number", rd.get("policyholder_phone",""), "Email Address", rd.get("policyholder_email","")],
            ["Address", rd.get("policyholder_address",""), "Insurer Name", rd.get("insurer_name","")],
        ]
        comp_rows = []
        for row in comp_data:
            comp_rows.append([
                Paragraph(f"<font size='8' color='#555'>{row[0]}</font>",
                          ps(f'cl_{row[0][:3]}', fontSize=8)),
                Paragraph(f"<b><font size='9'>{row[1]}</font></b>",
                          ps(f'cv_{row[0][:3]}', fontSize=9)),
                Paragraph(f"<font size='8' color='#555'>{row[2]}</font>",
                          ps(f'cl2_{row[0][:3]}', fontSize=8)),
                Paragraph(f"<b><font size='9'>{row[3]}</font></b>",
                          ps(f'cv2_{row[0][:3]}', fontSize=9)),
            ])
        comp_tbl = Table(comp_rows, colWidths=[4*cm, 5*cm, 3.5*cm, 5*cm])
        comp_tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, HexColor("#F9F9F7")]),
            ("GRID",    (0,0), (-1,-1), 0.3, self.BORDER),
            ("PADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(comp_tbl)
        story.append(Spacer(1, 0.25*cm))

        # Part B: Statement of facts
        story.append(Paragraph("<b>PART B — STATEMENT OF FACTS</b>",
                                ps('pbh', fontSize=10, fontName='Helvetica-Bold',
                                   textColor=self.TEAL_DARK)))
        story.append(hline(self.TEAL_LT, 0.5, 2, 6))
        story.append(Paragraph(body.get("statement_of_facts", ""),
                                ps('sof', fontSize=10, leading=16,
                                   alignment=TA_JUSTIFY)))
        story.append(Spacer(1, 0.2*cm))

        # Part C: Grounds
        story.append(Paragraph("<b>PART C — GROUNDS OF COMPLAINT</b>",
                                ps('pch', fontSize=10, fontName='Helvetica-Bold',
                                   textColor=self.TEAL_DARK)))
        story.append(hline(self.TEAL_LT, 0.5, 2, 6))
        story.append(Paragraph(body.get("grounds_of_complaint", ""),
                                ps('goc', fontSize=10, leading=16,
                                   alignment=TA_JUSTIFY)))
        story.append(Spacer(1, 0.2*cm))

        # IRDAI regulations
        story.append(Paragraph("<b>Applicable IRDAI Regulations:</b>",
                                ps('ar', fontSize=9, fontName='Helvetica-Bold')))
        for arg in arguments[:3]:
            ref_key = arg['irdai_ref'][:6].replace('/', '_')
            story.append(Paragraph(
                f"• <b>{arg['irdai_ref']}</b> — {arg['argument']}",
                ps(f'oarg_{ref_key}', fontSize=9,
                   leading=13, leftIndent=10, spaceAfter=3)
            ))
        story.append(Spacer(1, 0.2*cm))

        # Part D: Relief sought
        story.append(Paragraph("<b>PART D — RELIEF SOUGHT</b>",
                                ps('pdh', fontSize=10, fontName='Helvetica-Bold',
                                   textColor=self.TEAL_DARK)))
        story.append(hline(self.TEAL_LT, 0.5, 2, 6))
        story.append(Paragraph(body.get("relief_sought", ""),
                                ps('rs', fontSize=10, leading=16)))
        story.append(Spacer(1, 0.2*cm))

        # Documents to attach
        story.append(Paragraph("<b>PART E — DOCUMENTS ATTACHED</b>",
                                ps('peh', fontSize=10, fontName='Helvetica-Bold',
                                   textColor=self.TEAL_DARK)))
        story.append(hline(self.TEAL_LT, 0.5, 2, 6))
        docs = ["Copy of insurance policy", "Copy of claim rejection letter",
                "Copy of grievance letter sent to insurer",
                "Copy of hospital discharge summary",
                "Copy of hospital bills (itemized)",
                "Copy of all investigation reports",
                "Any other correspondence with insurer"]
        for i, d in enumerate(docs, 1):
            story.append(Paragraph(f"{i}. {d} ☐",
                                    ps(f'doc_{i}', fontSize=9,
                                       spaceAfter=3, leftIndent=8)))
        story.append(Spacer(1, 0.3*cm))

        # Declaration and signature
        story.append(Paragraph(
            f"<b>Declaration:</b> {body.get('declaration','')}",
            ps('decl', fontSize=9, leading=14,
               textColor=self.GRAY)
        ))
        story.append(Spacer(1, 0.8*cm))

        sig_tbl = Table([[
            Paragraph("Signature: _______________",
                      ps('s1', fontSize=10)),
            Paragraph(f"Name: {rd.get('policyholder_name','')}",
                      ps('s2', fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"Date: {date.today().strftime('%d %B %Y')}",
                      ps('s3', fontSize=10, alignment=TA_RIGHT))
        ]], colWidths=[5.5*cm, 6*cm, 6*cm])
        sig_tbl.setStyle(TableStyle([
            ("VALIGN",  (0,0), (-1,-1), "BOTTOM"),
            ("PADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(sig_tbl)

        story.append(hline(self.TEAL_LT, 0.5, 8, 4))
        story.append(Paragraph(
            "<font size='7' color='#888'>Generated by TrustClaim AI | "
            "Find your regional Ombudsman at ecoi.co.in | "
            "IRDAI Bima Bharosa: bimabharosa.irdai.gov.in | "
            "Filing is FREE — no lawyer required</font>",
            ps('ft', fontSize=7, alignment=TA_CENTER, textColor=self.GRAY)
        ))

        doc.build(story)
