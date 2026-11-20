# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Start-up dependency and data-table validation."""
from typing import List
import streamlit as st

from cdss.formulary.abx_guidelines import ABX_GUIDELINES
from cdss.formulary.abx_guidelines import validate_abx_guidelines
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.organisms.organism_profile import validate_organism_profile
from cdss.organisms.specimen_organism_map import validate_specimen_organism_map
from cdss.common.catalog import (
    SPECIMEN_TYPES,
)
from cdss.health import (
    AST_QA_AVAILABLE,
    AST_RULES_IMPORT_ERROR,
    AST_RULES_MODULES_AVAILABLE,
    INTRINSIC_TABLE_OK,
    PANEL_COMPLETENESS_AVAILABLE,
    PANEL_COMPLETENESS_IMPORT_ERROR,
)
from cdss.therapy.tables import (
    _PREG_ALIASES,
)
import cdss_ui.auth as _auth


@st.cache_data(show_spinner=False)
def get_startup_validation_issues() -> List[str]:
    issues: List[str] = []
    issues.extend(validate_abx_guidelines(
        known_organisms=list(ORGANISM_PROFILE.keys()),
        known_specimens=SPECIMEN_TYPES
    ))
    issues.extend(validate_organism_profile(known_antibiotics=list(ABX_GUIDELINES.keys())))
    issues.extend(validate_specimen_organism_map(known_organisms=list(ORGANISM_PROFILE.keys())))
    if not _auth.SUBSCRIBER_HASHES:
        issues.append(
            "[SECURITY] No subscriber_hashes secret is configured -- login is by "
            "email address alone, so anyone who knows a customer's address has "
            "full access. Add a secrets entry: subscriber_hashes = "
            '{"user@lab.com": "pbkdf2_sha256$..."} (generate with '
            "make_password_hash())."
        )
    else:
        _open = sorted(e for e in _auth.SUBSCRIBERS if e not in _auth.SUBSCRIBER_HASHES)
        if _open:
            issues.append(
                f"[SECURITY] {len(_open)} subscriber account(s) still have no "
                f"password set: {', '.join(_open[:5])}"
                + (" ..." if len(_open) > 5 else "")
            )
    # v7.8: the login-attempt store must be owner-only -- verified (on Windows
    # by its NTFS ACL), not assumed from a chmod that Windows ignores
    try:
        import os as _os
        from cdss.security import auth_service as _as
        if _os.path.exists(_as.store_path()) and not _as.restrict_to_owner(_as.store_path()):
            issues.append(
                "[SECURITY] The login-attempt store could not be restricted to the account "
                f"running the app ({_as.store_path()}); other local users may read it.")
    except Exception:
        pass
    _bad_preg = sorted(
        f"{d} = {i.get('preg_status')!r}" for d, i in ABX_GUIDELINES.items()
        if str(i.get("preg_status") or "").strip().upper() not in _PREG_ALIASES
    )
    if _bad_preg:
        issues.append(
            "[WARNING] preg_status values outside the Safe/Warn/Banned enum -- "
            "they are being treated as 'Warn' (fail-closed) but should be "
            f"corrected in abx_guidelines.py: {', '.join(_bad_preg)}"
        )
    if not AST_RULES_MODULES_AVAILABLE:
        issues.append(
            "[CRITICAL] ast_reportability / ast_consistency failed to load -- the "
            "AST QC report is running on the small inline fallback rule set. "
            "Intrinsic-resistance and panel-discrepancy findings will be MISSING "
            f"from every report. Reason: {AST_RULES_IMPORT_ERROR or 'unknown'}"
        )
    if not AST_QA_AVAILABLE:
        issues.append(
            "[CRITICAL] ast_qa_engine failed to load -- Level-1 AST QA checks are "
            "disabled."
        )
    if not PANEL_COMPLETENESS_AVAILABLE:
        issues.append(
            "[WARNING] ast_panel_completeness failed to load -- the '🧫 AST "
            "Panel Completeness' card will not appear anywhere in the report "
            f"and no 'missing expected agent' findings will be generated. "
            f"Reason: {PANEL_COMPLETENESS_IMPORT_ERROR or 'unknown'}"
        )
    if not INTRINSIC_TABLE_OK:
        issues.append(
            "[CRITICAL] clinical_data.py not found -- INTRINSIC_RESISTANCE is empty. "
            "Intrinsically inactive agents will NOT be routed to Avoid and will NOT be "
            "stripped before MDR counting. Upload clinical_data.py next to streamlit_app.py."
        )
    deduped: List[str] = []
    seen:    set        = set()
    for issue in issues:
        if issue not in seen:
            deduped.append(issue)
            seen.add(issue)
    return deduped
