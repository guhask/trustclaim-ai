"""
Audit Trail Agent
Logs every agent decision with: timestamp, agent name, input summary,
reasoning, source clause / IRDAI regulation, and final output.
Generates the professional PDF audit report for judges and real-world use.
"""

import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable, KeepTogether)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


class AuditTrailAgent:

    BRAND_TEAL   = HexColor("#0F6E56")
    BRAND_LIGHT  = HexColor("#E1F5EE")
    RED          = HexColor("#E24B4A")
    AMBER        = HexColor("#EF9F27")
    GREEN        = HexColor("#1D9E75")
    GRAY         = HexColor("#888780")
    LIGHT_GRAY   = HexColor("#F1EFE8")
    DARK         = HexColor("#2C2C2A")

    def __init__(self):
        self.agent_name = "Audit Trail Agent"
        self.entries    = []

    # ── Safe number formatter ─────────────────────────────────────────────────
    @staticmethod
    def _fmt_amount(value) -> str:
        """Safely format a value as Indian number. Returns 'N/A' for non-numbers."""
        if value is None:
            return "N/A"
        try:
            num = float(str(value).replace(",", "").replace("Rs.", "").strip())
            return f"{num:,.0f}"
        except (ValueError, TypeError):
            return str(value) if value else "N/A"

    # ── Log an entry ──────────────────────────────────────────────────────────
    def log(self, agent: str, action: str, input_summary: str,
            output_summary: str, regulation_ref: str = "", details: dict = None):
        self.entries.append({
            "timestamp":      datetime.now().isoformat(),
            "agent":          agent,
            "action":         action,
            "input_summary":  input_summary,
            "output_summary": output_summary,
            "regulation_ref": regulation_ref,
            "details":        details or {}
        })

    def get_trail(self) -> list:
        return self.entries

    # ── Generate PDF Report ───────────────────────────────────────────────────
    def generate_pdf(self, output_path: str, policy_data: dict, bill_data: dict,
                     discharge_data: dict, compliance_report: dict,
                     prediction: dict) -> str:
        """Generate a professional, audit-ready PDF report."""

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2*cm,
            rightMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        story  = []

        # ── Header ────────────────────────────────────────────────────────────
        story.extend(self._build_header(styles, policy_data, prediction))

        # ── Executive Summary ─────────────────────────────────────────────────
        story.extend(self._build_summary_card(styles, prediction, compliance_report))

        # ── Claim Details ─────────────────────────────────────────────────────
        story.extend(self._build_claim_details(styles, policy_data, bill_data, discharge_data))

        # ── Compliance Findings ───────────────────────────────────────────────
        story.extend(self._build_compliance_section(styles, compliance_report))

        # ── Fix Guide ─────────────────────────────────────────────────────────
        story.extend(self._build_fix_guide(styles, prediction))

        # ── Audit Trail ───────────────────────────────────────────────────────
        story.extend(self._build_audit_section(styles))

        # ── Footer ────────────────────────────────────────────────────────────
        story.extend(self._build_footer(styles))

        doc.build(story)
        return output_path

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self, styles, policy_data, prediction):
        elements = []

        header_data = [[
            Paragraph("<font color='#0F6E56'><b>TrustClaim AI</b></font><br/>"
                      "<font size='9' color='#888780'>Pre-Filing Claim Intelligence Report</font>",
                      ParagraphStyle('h', fontName='Helvetica', fontSize=18)),
            Paragraph(
                f"<font size='8' color='#888780'>Report Generated<br/>"
                f"{datetime.now().strftime('%d %b %Y, %I:%M %p')}<br/><br/>"
                f"Insurer: {policy_data.get('insurer_name', 'N/A')}<br/>"
                f"Policy No: {policy_data.get('policy_number', 'N/A')}</font>",
                ParagraphStyle('rh', fontName='Helvetica', fontSize=9,
                               alignment=TA_RIGHT)
            )
        ]]
        t = Table(header_data, colWidths=[10*cm, 7*cm])
        t.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ]))
        elements.append(t)
        elements.append(HRFlowable(width="100%", thickness=2,
                                    color=self.BRAND_TEAL, spaceAfter=12))
        return elements

    # ── Summary card ──────────────────────────────────────────────────────────
    def _build_summary_card(self, styles, prediction, compliance_report):
        elements = []
        score = prediction.get("approval_probability", 0)

        # Color based on score
        if score >= 80:
            score_color = "#1D9E75"
            bg_color    = "#E1F5EE"
        elif score >= 60:
            score_color = "#EF9F27"
            bg_color    = "#FAEEDA"
        else:
            score_color = "#E24B4A"
            bg_color    = "#FCEBEB"

        summary_data = [[
            Paragraph(
                f"<font size='32' color='{score_color}'><b>{score}%</b></font><br/>"
                f"<font size='11' color='#444441'>Approval Probability</font>",
                ParagraphStyle('sc', fontName='Helvetica', fontSize=11,
                               alignment=TA_CENTER)
            ),
            Paragraph(
                f"<b>{prediction.get('probability_label', '')}</b><br/><br/>"
                f"{prediction.get('key_insight', '')}<br/><br/>"
                f"<font color='#888780' size='9'>"
                f"Violations: {compliance_report.get('total_violations', 0)} | "
                f"Warnings: {compliance_report.get('total_warnings', 0)} | "
                f"IRDAI Regulations Checked: {compliance_report.get('irdai_regulations_checked', 0)}"
                f"</font>",
                ParagraphStyle('si', fontName='Helvetica', fontSize=10)
            ),
            Paragraph(
                "<b>Estimated Payable</b><br/>"
                "<font size='14'>"
                "Rs. " + self._fmt_amount(prediction.get('estimated_payable', {}).get('estimated_payable')) +
                "</font><br/><br/>"
                "<font color='#888780' size='8'>"
                + str(prediction.get('estimated_payable', {}).get('note', '')) + "</font>",
                ParagraphStyle('ep', fontName='Helvetica', fontSize=10,
                               alignment=TA_CENTER)
            ),
        ]]

        t = Table(summary_data, colWidths=[4.5*cm, 9*cm, 4.5*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), HexColor(bg_color)),
            ("ROUNDEDCORNERS", [6]),
            ("PADDING",       (0,0), (-1,-1), 12),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LINEABOVE",     (0,0), (-1,0), 0.5, HexColor(score_color)),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4*cm))

        # Recommendation box
        rec = prediction.get("recommendation", "")
        if rec:
            rec_para = Paragraph(
                f"<b>Recommendation: </b>{rec}",
                ParagraphStyle('rec', fontName='Helvetica', fontSize=10,
                               leftIndent=8, spaceBefore=4)
            )
            rec_table = Table([[rec_para]], colWidths=[17*cm])
            rec_table.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (-1,-1), HexColor("#E6F1FB")),
                ("PADDING",     (0,0), (-1,-1), 10),
                ("LINEABOVE",   (0,0), (-1,0),  2, HexColor("#185FA5")),
            ]))
            elements.append(rec_table)

        elements.append(Spacer(1, 0.5*cm))
        return elements

    # ── Claim details table ───────────────────────────────────────────────────
    def _build_claim_details(self, styles, policy_data, bill_data, discharge_data):
        elements = []
        elements.append(Paragraph(
            "Claim Details",
            ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=12,
                           textColor=self.BRAND_TEAL, spaceBefore=8)
        ))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=self.BRAND_TEAL, spaceAfter=6))

        details = [
            ["Policy Number",    policy_data.get("policy_number", "N/A"),
             "Insurer",          policy_data.get("insurer_name", "N/A")],
            ["Sum Insured",      "Rs. " + self._fmt_amount(policy_data.get("sum_insured")),
             "Plan Name",        policy_data.get("plan_name", "N/A")],
            ["Policy Period",
             str(policy_data.get('policy_start_date','N/A')) + " to " + str(policy_data.get('policy_end_date','N/A')),
             "Policy Status",    str(policy_data.get("policy_status", "N/A")).upper()],
            ["Patient Name",     discharge_data.get("patient_name", "N/A"),
             "Hospital",         discharge_data.get("hospital_name") or bill_data.get("hospital_name","N/A")],
            ["Primary Diagnosis", discharge_data.get("primary_diagnosis", "N/A"),
             "Admission Type",    discharge_data.get("admission_type", "N/A")],
            ["Admission Date",   str(discharge_data.get("admission_date", "N/A")),
             "Discharge Date",    str(discharge_data.get("discharge_date", "N/A"))],
            ["Total Bill",       "Rs. " + self._fmt_amount(bill_data.get("total_bill_amount")),
             "Room Type",        bill_data.get("room_type", "N/A")],
        ]

        table_data = []
        for row in details:
            table_data.append([
                Paragraph(f"<font color='#888780' size='8'>{row[0]}</font>",
                          ParagraphStyle('lbl', fontName='Helvetica', fontSize=8)),
                Paragraph(f"<b><font size='9'>{row[1]}</font></b>",
                          ParagraphStyle('val', fontName='Helvetica', fontSize=9)),
                Paragraph(f"<font color='#888780' size='8'>{row[2]}</font>",
                          ParagraphStyle('lbl2', fontName='Helvetica', fontSize=8)),
                Paragraph(f"<b><font size='9'>{row[3]}</font></b>",
                          ParagraphStyle('val2', fontName='Helvetica', fontSize=9)),
            ])

        t = Table(table_data, colWidths=[3.5*cm, 5*cm, 3.5*cm, 5*cm])
        t.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, HexColor("#F9F9F7")]),
            ("PADDING",        (0,0), (-1,-1), 6),
            ("GRID",           (0,0), (-1,-1), 0.25, HexColor("#D3D1C7")),
            ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4*cm))
        return elements

    # ── Compliance section ────────────────────────────────────────────────────
    def _build_compliance_section(self, styles, compliance_report):
        elements = []
        elements.append(Paragraph(
            "Compliance Findings",
            ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=12,
                           textColor=self.BRAND_TEAL, spaceBefore=8)
        ))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=self.BRAND_TEAL, spaceAfter=6))

        all_items = (
            [("VIOLATION", v) for v in compliance_report.get("violations", [])] +
            [("WARNING",   w) for w in compliance_report.get("warnings", [])]
        )

        if not all_items:
            elements.append(Paragraph(
                "✓ No compliance violations or warnings found. Claim appears compliant.",
                ParagraphStyle('ok', fontName='Helvetica', fontSize=10,
                               textColor=self.GREEN, spaceBefore=4)
            ))
        else:
            for item_type, item in all_items:
                color = self.RED if item_type == "VIOLATION" else self.AMBER
                label = "VIOLATION" if item_type == "VIOLATION" else "WARNING"

                finding_data = [[
                    Paragraph(
                        f"<font color='white'><b> {label} </b></font>",
                        ParagraphStyle('badge', fontName='Helvetica-Bold',
                                       fontSize=8, alignment=TA_CENTER)
                    ),
                    Paragraph(
                        f"<b>{item.get('title','')}</b>  "
                        f"<font size='8' color='#888780'>IRDAI Ref: {item.get('irdai_ref','N/A')}</font><br/>"
                        f"<font size='9'>{item.get('description','')}</font><br/>"
                        f"<font size='9' color='#185FA5'><b>Fix: </b>{item.get('fix','')}</font>",
                        ParagraphStyle('fi', fontName='Helvetica', fontSize=9,
                                       leftIndent=4)
                    )
                ]]
                t = Table(finding_data, colWidths=[1.8*cm, 15.2*cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND",  (0,0), (0,0),  color),
                    ("BACKGROUND",  (1,0), (1,0),
                     HexColor("#FCEBEB") if item_type == "VIOLATION" else HexColor("#FAEEDA")),
                    ("PADDING",     (0,0), (-1,-1), 8),
                    ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
                    ("LINEBELOW",   (0,0), (-1,-1), 0.25, HexColor("#D3D1C7")),
                ]))
                elements.append(KeepTogether([t, Spacer(1, 0.2*cm)]))

        elements.append(Spacer(1, 0.4*cm))
        return elements

    # ── Fix guide ─────────────────────────────────────────────────────────────
    def _build_fix_guide(self, styles, prediction):
        elements = []
        fix_guide = prediction.get("fix_guide", [])

        if not fix_guide:
            return elements

        elements.append(Paragraph(
            "Action Plan — What To Do Before Filing",
            ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=12,
                           textColor=self.BRAND_TEAL, spaceBefore=8)
        ))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=self.BRAND_TEAL, spaceAfter=6))

        priority_colors = {
            "CRITICAL": "#E24B4A", "HIGH": "#E24B4A",
            "MEDIUM": "#EF9F27",   "LOW": "#1D9E75"
        }

        for step in fix_guide:
            p_color = priority_colors.get(step.get("priority", "MEDIUM"), "#EF9F27")
            step_data = [[
                Paragraph(
                    f"<font color='white'><b>STEP {step.get('step','')}</b></font>",
                    ParagraphStyle('sn', fontName='Helvetica-Bold',
                                   fontSize=9, alignment=TA_CENTER)
                ),
                Paragraph(
                    f"<b>{step.get('action','')}</b><br/>"
                    f"<font size='9'>{step.get('detail','')}</font><br/>"
                    f"<font size='8' color='#888780'>Ref: {step.get('irdai_ref','')}</font>",
                    ParagraphStyle('sd', fontName='Helvetica', fontSize=10,
                                   leftIndent=4)
                )
            ]]
            t = Table(step_data, colWidths=[1.8*cm, 15.2*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0,0), (0,0), HexColor(p_color)),
                ("BACKGROUND",  (1,0), (1,0), HexColor("#F9F9F7")),
                ("PADDING",     (0,0), (-1,-1), 8),
                ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
                ("LINEBELOW",   (0,0), (-1,-1), 0.25, HexColor("#D3D1C7")),
            ]))
            elements.append(KeepTogether([t, Spacer(1, 0.2*cm)]))

        elements.append(Spacer(1, 0.4*cm))
        return elements

    # ── Audit trail table ──────────────────────────────────────────────────────
    def _build_audit_section(self, styles):
        elements = []
        elements.append(Paragraph(
            "Agent Decision Audit Trail",
            ParagraphStyle('sh', fontName='Helvetica-Bold', fontSize=12,
                           textColor=self.BRAND_TEAL, spaceBefore=8)
        ))
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=self.BRAND_TEAL, spaceAfter=6))

        if not self.entries:
            elements.append(Paragraph("No audit entries recorded.",
                            ParagraphStyle('na', fontName='Helvetica', fontSize=9)))
            return elements

        header = [
            Paragraph("<b><font size='8'>Timestamp</font></b>",
                      ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8)),
            Paragraph("<b><font size='8'>Agent</font></b>",
                      ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8)),
            Paragraph("<b><font size='8'>Action</font></b>",
                      ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8)),
            Paragraph("<b><font size='8'>Regulation</font></b>",
                      ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8)),
            Paragraph("<b><font size='8'>Outcome</font></b>",
                      ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8)),
        ]

        table_data = [header]
        for e in self.entries:
            ts = e["timestamp"].replace("T", " ")[:16]
            table_data.append([
                Paragraph(f"<font size='7'>{ts}</font>",
                          ParagraphStyle('ac', fontName='Helvetica', fontSize=7)),
                Paragraph(f"<font size='7'>{e['agent']}</font>",
                          ParagraphStyle('ac', fontName='Helvetica', fontSize=7)),
                Paragraph(f"<font size='7'>{e['action']}</font>",
                          ParagraphStyle('ac', fontName='Helvetica', fontSize=7)),
                Paragraph(f"<font size='7'>{e.get('regulation_ref','—')}</font>",
                          ParagraphStyle('ac', fontName='Helvetica', fontSize=7)),
                Paragraph(f"<font size='7'>{e['output_summary'][:80]}</font>",
                          ParagraphStyle('ac', fontName='Helvetica', fontSize=7)),
            ])

        t = Table(table_data, colWidths=[2.8*cm, 3*cm, 3.5*cm, 3*cm, 4.7*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), self.BRAND_TEAL),
            ("TEXTCOLOR",     (0,0), (-1,0), white),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [white, HexColor("#F9F9F7")]),
            ("GRID",          (0,0), (-1,-1), 0.25, HexColor("#D3D1C7")),
            ("PADDING",       (0,0), (-1,-1), 5),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4*cm))
        return elements

    # ── Footer ────────────────────────────────────────────────────────────────
    def _build_footer(self, styles):
        elements = []
        elements.append(HRFlowable(width="100%", thickness=0.5,
                                    color=self.GRAY, spaceBefore=8))
        elements.append(Paragraph(
            "<font size='7' color='#888780'>"
            "This report is generated by TrustClaim AI for pre-filing advisory purposes only. "
            "It does not guarantee claim approval or constitute legal advice. "
            "Actual claim decisions rest with the insurer as per policy terms and IRDAI regulations. "
            "Built for ET AI Hackathon 2026 | Problem Statement 5 — Domain-Specialized AI Agents"
            "</font>",
            ParagraphStyle('ft', fontName='Helvetica', fontSize=7,
                           alignment=TA_CENTER, spaceBefore=4)
        ))
        return elements
