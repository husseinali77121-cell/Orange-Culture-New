# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Availability flags for the QC / safety modules."""
from typing import Dict
from typing import List

from cdss.common.log import logger


# AST Quality-Check engine (validates susceptibility-result internal consistency)
try:
    from cdss.astqc.ast_qa_engine import run_ast_qa_engine
    AST_QA_AVAILABLE = True
except Exception:
    run_ast_qa_engine = None
    AST_QA_AVAILABLE = False

# AST reportability + internal-consistency rule modules (shared with the Orange
# Lab version -- single source of truth across both products). Optional: if the
# files are absent the QC report simply falls back to the inline phenotype rules.
try:
    from cdss.astqc.ast_reportability import (
        check_reportability as _check_reportability_ext,
        format_issue as _fmt_reportability,
    )
    from cdss.astqc.ast_consistency import (
        check_consistency as _check_consistency_ext,
        format_issue as _fmt_consistency,
    )
    AST_RULES_MODULES_AVAILABLE = True
    AST_RULES_IMPORT_ERROR = ""
except Exception as _ast_rules_exc:
    # A bare `except: pass` here is how the whole reportability + consistency QC
    # layer can switch itself off in production with nothing on screen. One
    # NameError in a rule table (a helper referenced before it is defined is
    # enough) silently downgrades the product from ~60 traceable rules to the
    # small inline fallback set. Record the reason and surface it in
    # get_startup_validation_issues() so it can never be invisible again.
    _check_reportability_ext = None
    _check_consistency_ext = None
    _fmt_reportability = None
    _fmt_consistency = None
    AST_RULES_MODULES_AVAILABLE = False
    AST_RULES_IMPORT_ERROR = f"{type(_ast_rules_exc).__name__}: {_ast_rules_exc}"
    logger.error("ast_reportability/ast_consistency unavailable -- AST QC is "
                 "running on the inline fallback rules only: %s", _ast_rules_exc)

# AST Panel Completeness -- "was enough tested at all", not "was what was
# tested interpreted correctly" (that's the block above). Same optional-import
# pattern: absence of this file must never crash the report -- but unlike the
# block above, this one used to swallow the exception completely with no
# captured message, no log line, and no entry in _MODULE_HEALTH below. That
# meant an import failure here was PERMANENTLY INVISIBLE: no card, no error,
# no clue anywhere in the app about why. Found 2026-08-22 when the card
# simply never appeared and there was nothing to look at to find out why.
try:
    from cdss.astqc.ast_panel_completeness import check_panel_completeness as _check_panel_completeness_ext
    PANEL_COMPLETENESS_AVAILABLE = True
    PANEL_COMPLETENESS_IMPORT_ERROR = ""
except Exception as _panel_completeness_exc:
    _check_panel_completeness_ext = None
    PANEL_COMPLETENESS_AVAILABLE = False
    PANEL_COMPLETENESS_IMPORT_ERROR = (
        f"{type(_panel_completeness_exc).__name__}: {_panel_completeness_exc}"
    )
    logger.error("ast_panel_completeness unavailable -- the Panel Completeness "
                 "card and its QC findings will not appear anywhere in the "
                 "report: %s", _panel_completeness_exc)

# Terminal safety gate + unified clinical constraint map. This is the layer that
# adds site penetration (can the drug physically reach the infection?) on top of
# the organism/host reasoning the main engine already does. Treated as CRITICAL
# in _MODULE_HEALTH: without it the app silently loses meningeal-penetration
# checking and the hepatic layer, and nothing on screen would say so.
try:
    from cdss.therapy.safety_gate import apply_safety_gate, GATE_VERSION
    from cdss.therapy.clinical_matrix import MATRIX_VERSION
    SAFETY_GATE_AVAILABLE = True
except Exception as _sg_exc:
    apply_safety_gate = None
    GATE_VERSION = MATRIX_VERSION = "unavailable"
    SAFETY_GATE_AVAILABLE = False
    logger.error("safety_gate/clinical_matrix unavailable: %s", _sg_exc)

# ============================================================================
#  INTRINSIC_RESISTANCE — moved to clinical_data.py (SINGLE SOURCE OF TRUTH)
# ----------------------------------------------------------------------------
#  It used to be defined inline here, while ast_qa_engine.py imported it from a
#  `clinical_data` module that did not exist in this repository. That import
#  silently fell back to {}, so the QA engine's intrinsic-resistance level was
#  dead for every Gram-negative while THIS copy was driving the Avoid list — the
#  two halves of the product disagreed with nobody noticing. The table now lives
#  in clinical_data.py and both halves import the same rows.
#
#  Matching is EXACT drug-name (see _remove_intrinsic_resistance /
#  is_intrinsically_avoided), so every spelling variant used anywhere in the app
#  must appear verbatim in the list. Extra variants that match no real drug are
#  harmless. ONLY intrinsically-INACTIVE agents are listed — anti-pseudomonal
#  beta-lactams (Ceftazidime/Cefepime/Cefoperazone/Pip-Tazo/Aztreonam/carbapenems)
#  are deliberately EXCLUDED and judged on their own AST result.
# ============================================================================
try:
    from cdss.organisms.clinical_data import INTRINSIC_RESISTANCE
    INTRINSIC_TABLE_OK = True
except Exception as _intrinsic_exc:          # pragma: no cover - deployment fault
    logger.error("clinical_data.py is missing or unreadable (%s) -- the "
                 "intrinsic-resistance table is EMPTY; Avoid-routing and MDR "
                 "stripping are degraded.", _intrinsic_exc)
    INTRINSIC_RESISTANCE: Dict[str, List[str]] = {}
    INTRINSIC_TABLE_OK = False
