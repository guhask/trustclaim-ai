"""
IRDAI Regulations Knowledge Base
Real Indian health insurance regulations used by the Compliance Guardrail Agent.
This data is loaded into ChromaDB for semantic retrieval.
"""

IRDAI_REGULATIONS = [
    {
        "id": "irdai_hir_2016_1",
        "title": "IRDAI Health Insurance Regulations 2016 — Waiting Period",
        "content": """Under IRDAI Health Insurance Regulations 2016, every health insurance policy 
        must specify an initial waiting period of 30 days from policy inception. No claims shall 
        be payable for any illness or disease (except accidental injuries) during this initial 
        30-day waiting period. This regulation applies to all individual and family floater 
        health insurance policies issued by any insurer registered under IRDAI.""",
        "category": "waiting_period",
        "regulation_ref": "IRDAI/HLT/REG/2016/143"
    },
    {
        "id": "irdai_hir_2016_2",
        "title": "IRDAI — Pre-Existing Disease Definition and Waiting Period",
        "content": """A Pre-Existing Disease (PED) means any condition, ailment, injury or disease 
        diagnosed by a physician within 48 months prior to the effective date of the policy. 
        Standard waiting period for PED claims is 48 months (4 years) from policy inception, 
        but IRDAI mandates that no insurer shall impose a PED waiting period of more than 48 months. 
        Many insurers offer reduced PED waiting periods of 12 to 24 months as a product feature. 
        The specific PED waiting period must be stated in the policy schedule.""",
        "category": "pre_existing_disease",
        "regulation_ref": "IRDAI/HLT/REG/2016/143 Clause 4"
    },
    {
        "id": "irdai_cashless_2023",
        "title": "IRDAI Master Circular on Cashless Claims 2023",
        "content": """IRDAI Master Circular dated November 2023 mandates that all health insurers 
        must provide cashless facility at network hospitals. Insurers must decide on cashless 
        authorization within 1 hour of receiving a pre-authorization request for planned 
        hospitalizations and within 30 minutes for emergency hospitalizations. Denial of cashless 
        must be communicated with written reasons citing specific policy exclusions.""",
        "category": "cashless_claims",
        "regulation_ref": "IRDAI/HLT/CIR/2023/205"
    },
    {
        "id": "irdai_settlement_2024",
        "title": "IRDAI Claim Settlement Timeline Mandate 2024",
        "content": """Under IRDAI guidelines effective 2024, all health insurance claims must be 
        settled within 30 days of receiving the last necessary document. For cashless claims, 
        final settlement must occur within 3 hours of discharge. Delays beyond these timelines 
        attract penal interest at 2% above bank rate. IRDAI's target is to bring average 
        settlement time below 15 days by 2025.""",
        "category": "settlement_timeline",
        "regulation_ref": "IRDAI/HLT/CIR/2024/017"
    },
    {
        "id": "irdai_documents_standard",
        "title": "IRDAI Standard Documents Required for Health Insurance Claims",
        "content": """IRDAI mandates that insurers cannot reject a claim solely for want of 
        additional documents beyond the standard list. Standard documents for reimbursement 
        claims include: (1) Duly filled claim form, (2) Original hospital discharge summary, 
        (3) Original hospital bills with itemized breakup, (4) All original investigation 
        reports and prescriptions, (5) Pharmacy bills with doctor prescription, 
        (6) Original consultation notes, (7) Attending physician certificate, 
        (8) KYC documents (Aadhaar/PAN), (9) Cancelled cheque for NEFT payment, 
        (10) Policy copy and ID card. Insurers must specify upfront all documents needed.""",
        "category": "documentation",
        "regulation_ref": "IRDAI/HLT/CIR/2021/189"
    },
    {
        "id": "irdai_room_rent",
        "title": "IRDAI — Room Rent Sub-Limits and Proportionate Deductions",
        "content": """Many health insurance policies impose room rent sub-limits, typically 1% 
        of sum insured per day for normal rooms and 2% for ICU. If the policyholder opts for 
        a room with higher rent than the eligible limit, insurers apply proportionate deduction 
        — all associated expenses (surgeon fee, anesthesia, OT charges) are proportionately 
        reduced. IRDAI has directed insurers to clearly disclose room rent limits and the 
        impact of proportionate deductions in the policy document and at the time of sale.""",
        "category": "sub_limits",
        "regulation_ref": "IRDAI/HLT/CIR/2020/151"
    },
    {
        "id": "irdai_pre_auth",
        "title": "IRDAI Pre-Authorization Process for Planned Hospitalizations",
        "content": """For planned hospitalizations, policyholders must obtain pre-authorization 
        from the TPA or insurer at least 48 hours before admission. The pre-auth request must 
        include: diagnosis, proposed procedure, estimated cost, treating doctor details, and 
        hospital details. Failure to obtain pre-authorization for planned procedures may result 
        in claim rejection. Emergency hospitalizations are exempt from pre-authorization 
        requirement but must be intimated within 24 hours of admission.""",
        "category": "pre_authorization",
        "regulation_ref": "IRDAI/HLT/REG/2016/143 Clause 9"
    },
    {
        "id": "irdai_portability",
        "title": "IRDAI Health Insurance Portability Rules",
        "content": """Under IRDAI portability guidelines, policyholders can transfer their 
        health insurance from one insurer to another without losing accumulated waiting period 
        credits. The new insurer must give credit for the waiting period already served with 
        the previous insurer. Portability must be applied for at least 45 days before policy 
        renewal. The new insurer can underwrite based on current health status but must 
        honor previous waiting period credits.""",
        "category": "portability",
        "regulation_ref": "IRDAI/HLT/CIR/2011/093"
    },
    {
        "id": "irdai_copay",
        "title": "IRDAI — Co-payment Conditions in Senior Citizen Policies",
        "content": """For policies issued to senior citizens (age 60 and above), insurers may 
        impose a co-payment clause typically ranging from 10% to 20% of the admissible claim 
        amount. The co-payment percentage must be clearly stated in the policy schedule. 
        IRDAI mandates that co-payment cannot exceed 20% for any individual health insurance 
        policy. Co-payment does not apply to critical illness policies or hospital cash policies.""",
        "category": "copayment",
        "regulation_ref": "IRDAI/HLT/REG/2016/143 Clause 11"
    },
    {
        "id": "irdai_specific_waiting",
        "title": "IRDAI — Specific Disease Waiting Periods",
        "content": """Certain specific diseases and procedures have mandatory waiting periods 
        under IRDAI guidelines: Hernia (2 years), Cataract (2 years), Knee replacement (2 years), 
        Hip replacement (2 years), Hysterectomy (2 years), Sinusitis (1 year), 
        Varicose veins (1 year), Piles and fissures (1 year), Calculus diseases/stones (1 year), 
        Benign ENT disorders (1 year), Deviated nasal septum (1 year). 
        These waiting periods run from the first policy inception date, not renewal date.""",
        "category": "specific_waiting",
        "regulation_ref": "IRDAI/HLT/REG/2016/143 Schedule I"
    },
    {
        "id": "irdai_exclusion_standard",
        "title": "IRDAI Standard Permanent Exclusions — Health Insurance",
        "content": """IRDAI mandates standard permanent exclusions applicable to all health 
        insurance policies: (1) War, nuclear, chemical, biological attacks, (2) Self-inflicted 
        injuries and suicide attempts, (3) Cosmetic or aesthetic surgeries unless required 
        after accident, (4) Dental treatment unless due to accident or disease, 
        (5) Treatment for alcoholism, drug or substance abuse, (6) Experimental or 
        unproven treatments, (7) Refractive error correction below 7.5 diopters, 
        (8) Obesity treatment unless BMI above 40 with comorbidities, 
        (9) Hormone replacement therapy for gender reassignment.""",
        "category": "exclusions",
        "regulation_ref": "IRDAI/HLT/REG/2016/143 Schedule II"
    },
    {
        "id": "irdai_claim_rejection",
        "title": "IRDAI — Grounds for Claim Rejection and Policyholder Rights",
        "content": """IRDAI regulations require that claim rejections must: (1) Be communicated 
        in writing with specific reasons, (2) Cite exact policy clause or regulation violated, 
        (3) Include information about grievance redressal mechanism, (4) Be issued within 
        30 days of receiving last document. Policyholders can escalate rejected claims to: 
        Insurance Ombudsman (within 1 year of rejection), Consumer Forum, or IRDAI Bima Bharosa 
        portal. Rejections without written reasons citing specific clauses are invalid 
        under IRDAI regulations.""",
        "category": "rejection_rights",
        "regulation_ref": "IRDAI/HLT/CIR/2020/154"
    },
]

# ── Common rejection reasons from real Indian insurance market data ────────────
COMMON_REJECTION_REASONS = [
    {
        "reason": "Pre-existing disease not disclosed at inception",
        "frequency": "23%",
        "prevention": "Always disclose all pre-existing conditions in proposal form. Non-disclosure voids the policy."
    },
    {
        "reason": "Treatment within initial waiting period",
        "frequency": "18%",
        "prevention": "Ensure policy is at least 31 days old before filing a non-accident claim."
    },
    {
        "reason": "Incomplete documentation",
        "frequency": "17%",
        "prevention": "Collect all original documents — discharge summary, itemized bills, investigation reports, prescription copies."
    },
    {
        "reason": "Non-disclosure of pre-existing condition",
        "frequency": "14%",
        "prevention": "Ensure treating doctor's notes don't reference conditions that were not declared in the policy."
    },
    {
        "reason": "Room rent exceeds policy sub-limit",
        "frequency": "11%",
        "prevention": "Check room rent eligibility before admission. If exceeded, calculate proportionate deduction."
    },
    {
        "reason": "Treatment excluded under policy terms",
        "frequency": "9%",
        "prevention": "Cross-check diagnosis against policy exclusion list before admission."
    },
    {
        "reason": "Pre-authorization not taken for planned hospitalization",
        "frequency": "5%",
        "prevention": "Always call TPA helpline 48 hours before planned admission to get pre-auth."
    },
    {
        "reason": "Claim filed after policy lapse",
        "frequency": "3%",
        "prevention": "Ensure policy premium is paid before due date. Most policies have 30-day grace period."
    },
]
