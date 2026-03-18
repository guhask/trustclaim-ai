"""
Orchestrator Agent
The master controller that sequences all agents, manages state,
handles errors gracefully, and produces the final consolidated result.
This is the brain of TrustClaim AI.
"""

import os
import tempfile
from datetime import datetime
from typing import Callable
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agents.document_agent   import DocumentIntelligenceAgent
from agents.compliance_agent  import ComplianceGuardrailAgent
from agents.prediction_agent  import ClaimPredictionAgent
from agents.audit_agent       import AuditTrailAgent
from agents.preauth_agent     import PreAuthSimulatorAgent


class Orchestrator:

    def __init__(self):
        self.doc_agent        = DocumentIntelligenceAgent()
        self.compliance_agent = ComplianceGuardrailAgent()
        self.prediction_agent = ClaimPredictionAgent()
        self.audit_agent      = AuditTrailAgent()
        self.preauth_agent    = PreAuthSimulatorAgent()

        self.session_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.status_log   = []

    # ── Main pipeline ─────────────────────────────────────────────────────────
    def run(self, policy_path: str, bill_path: str, discharge_path: str,
            progress_callback: Callable = None) -> dict:
        """
        Run the full TrustClaim AI pipeline.
        progress_callback(step: int, total: int, message: str) — optional UI hook.
        Returns consolidated result dict.
        """

        def update(step, msg):
            self.status_log.append({"step": step, "msg": msg,
                                     "ts": datetime.now().isoformat()})
            if progress_callback:
                progress_callback(step, 7, msg)

        try:
            # ── Step 1: Extract policy ────────────────────────────────────────
            update(1, "Document Intelligence Agent — Extracting policy details...")
            policy_data = self.doc_agent.extract(policy_path, "policy")
            policy_completeness = self.doc_agent.validate_completeness(policy_data, "policy")

            self.audit_agent.log(
                agent="Document Intelligence Agent",
                action="Policy document extraction",
                input_summary=f"File: {os.path.basename(policy_path)}",
                output_summary=(
                    f"Extracted {len([v for v in policy_data.values() if v])} fields. "
                    f"Completeness: {policy_completeness['completeness_score']}%"
                ),
                regulation_ref="N/A",
                details={"completeness": policy_completeness}
            )

            # ── Step 2: Extract hospital bill ─────────────────────────────────
            update(2, "Document Intelligence Agent — Extracting hospital bill...")
            bill_data = self.doc_agent.extract(bill_path, "bill")
            bill_completeness = self.doc_agent.validate_completeness(bill_data, "bill")

            self.audit_agent.log(
                agent="Document Intelligence Agent",
                action="Hospital bill extraction",
                input_summary=f"File: {os.path.basename(bill_path)}",
                output_summary=(
                    f"Total bill: ₹{bill_data.get('total_bill_amount','N/A')}. "
                    f"Completeness: {bill_completeness['completeness_score']}%"
                ),
                regulation_ref="IRDAI/HLT/CIR/2021/189"
            )

            # ── Step 3: Extract discharge summary ─────────────────────────────
            update(3, "Document Intelligence Agent — Extracting discharge summary...")
            discharge_data = self.doc_agent.extract(discharge_path, "discharge")
            discharge_completeness = self.doc_agent.validate_completeness(
                discharge_data, "discharge"
            )

            self.audit_agent.log(
                agent="Document Intelligence Agent",
                action="Discharge summary extraction",
                input_summary=f"File: {os.path.basename(discharge_path)}",
                output_summary=(
                    f"Diagnosis: {discharge_data.get('primary_diagnosis','N/A')}. "
                    f"Completeness: {discharge_completeness['completeness_score']}%"
                ),
                regulation_ref="N/A"
            )

            # ── Step 4: Compliance check ──────────────────────────────────────
            update(4, "Compliance Guardrail Agent — Checking IRDAI regulations...")
            compliance_report = self.compliance_agent.check(
                policy_data, bill_data, discharge_data
            )

            self.audit_agent.log(
                agent="Compliance Guardrail Agent",
                action="IRDAI compliance check",
                input_summary="Policy + Bill + Discharge data",
                output_summary=(
                    f"Status: {compliance_report['compliance_status']}. "
                    f"Violations: {compliance_report['total_violations']}. "
                    f"Warnings: {compliance_report['total_warnings']}."
                ),
                regulation_ref="IRDAI/HLT/REG/2016/143",
                details={"status": compliance_report["compliance_status"]}
            )

            # ── Step 5: Claim prediction ──────────────────────────────────────
            update(5, "Claim Prediction Agent — Calculating approval probability...")
            prediction = self.prediction_agent.predict(
                policy_data, bill_data, discharge_data, compliance_report
            )

            self.audit_agent.log(
                agent="Claim Prediction Agent",
                action="Approval probability prediction",
                input_summary="Compliance report + extracted documents",
                output_summary=(
                    f"Approval probability: {prediction['approval_probability']}%. "
                    f"Label: {prediction['probability_label']}. "
                    f"Confidence: {prediction['confidence_level']}."
                ),
                regulation_ref="N/A",
                details={"probability": prediction["approval_probability"]}
            )

            # ── Step 6: Pre-auth simulation ───────────────────────────────────
            update(6, "Pre-Auth Simulator — Simulating TPA cashless response...")
            preauth_result = self.preauth_agent.simulate(
                policy_data, bill_data, discharge_data,
                compliance_report, prediction
            )

            self.audit_agent.log(
                agent="Pre-Auth Simulator Agent",
                action="TPA pre-authorization simulation",
                input_summary="Policy + Compliance + Prediction data",
                output_summary=(
                    f"Simulated decision: {preauth_result['decision']}. "
                    f"Approved: Rs.{preauth_result['approved_amount']:,}. "
                    f"Queries: {len(preauth_result['tpa_queries'])}."
                ),
                regulation_ref="IRDAI/HLT/CIR/2023/205"
            )

            # ── Step 7: Generate audit PDF ────────────────────────────────────
            update(7, "Audit Trail Agent — Generating compliance report PDF...")
            pdf_path = os.path.join(
                tempfile.gettempdir(),
                f"TrustClaim_Report_{self.session_id}.pdf"
            )
            self.audit_agent.generate_pdf(
                pdf_path, policy_data, bill_data,
                discharge_data, compliance_report, prediction
            )

            self.audit_agent.log(
                agent="Audit Trail Agent",
                action="PDF report generation",
                input_summary="All agent outputs",
                output_summary=f"Report generated: {os.path.basename(pdf_path)}",
                regulation_ref="IRDAI/HLT/CIR/2020/154"
            )

            return {
                "success":           True,
                "session_id":        self.session_id,
                "policy_data":       policy_data,
                "bill_data":         bill_data,
                "discharge_data":    discharge_data,
                "compliance_report": compliance_report,
                "prediction":        prediction,
                "preauth_result":    preauth_result,
                "pdf_path":          pdf_path,
                "audit_trail":       self.audit_agent.get_trail(),
                "status_log":        self.status_log,
                "completeness": {
                    "policy":    policy_completeness,
                    "bill":      bill_completeness,
                    "discharge": discharge_completeness,
                }
            }

        except Exception as e:
            self.audit_agent.log(
                agent="Orchestrator",
                action="Pipeline error",
                input_summary="Full pipeline",
                output_summary=f"Error: {str(e)}",
                regulation_ref="N/A"
            )
            return {
                "success": False,
                "error":   str(e),
                "partial_results": {
                    "status_log": self.status_log,
                    "audit_trail": self.audit_agent.get_trail()
                }
            }
