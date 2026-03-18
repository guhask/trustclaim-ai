import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys (set these in .env file) ─────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Model config — Claude only, no OpenAI needed ──────────────────────────────
CLAUDE_MODEL  = "claude-sonnet-4-5"   # Used for reasoning + compliance + prediction
CLAUDE_VISION = "claude-sonnet-4-5"   # Same model handles vision (documents/images)

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_PATH   = os.path.join(os.path.dirname(__file__), "../data/chroma_db")
IRDAI_COLLECTION   = "irdai_regulations"
INSURER_COLLECTION = "insurer_policies"

# ── App settings ──────────────────────────────────────────────────────────────
APP_TITLE     = "TrustClaim AI"
APP_SUBTITLE  = "India's First Pre-Filing Claim Intelligence Platform"
APP_VERSION   = "2.0 — Hackathon Edition"

# ── Indian Insurers covered ───────────────────────────────────────────────────
SUPPORTED_INSURERS = [
    "Star Health", "HDFC ERGO", "Niva Bupa", "Care Health",
    "Bajaj Allianz", "New India Assurance", "United India",
    "Oriental Insurance", "ICICI Lombard", "Reliance Health"
]

# ── Common Indian health insurance exclusions ─────────────────────────────────
STANDARD_EXCLUSIONS = [
    "Pre-existing disease within waiting period",
    "Cosmetic or aesthetic treatments",
    "Dental treatment (unless due to accident)",
    "Refractive error correction",
    "Pregnancy and childbirth (first 9 months)",
    "Self-inflicted injuries",
    "Treatment outside India (for domestic plans)",
    "Experimental or unproven treatments",
    "Obesity treatment and bariatric surgery",
    "Congenital external diseases",
]

# ── IRDAI waiting periods (standard) ──────────────────────────────────────────
WAITING_PERIODS = {
    "initial":       30,   # days — general initial waiting period
    "pre_existing":  365,  # days — pre-existing diseases (1 year; some policies 2-4 yr)
    "specific":      180,  # days — specific illnesses (hernia, cataract, etc.)
    "maternity":     270,  # days — maternity benefit waiting period
}

# ── Risk scoring weights ──────────────────────────────────────────────────────
RISK_WEIGHTS = {
    "waiting_period_violation": 40,
    "exclusion_match":          35,
    "document_missing":         20,
    "sub_limit_breach":         25,
    "policy_lapsed":            50,
    "diagnosis_mismatch":       30,
    "amount_discrepancy":       15,
}
