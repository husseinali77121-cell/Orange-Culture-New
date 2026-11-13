# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Organism and specimen pick-lists shared by the engine and the UI."""
from cdss.formulary.abx_guidelines import DEFAULT_SPECIMENS
from cdss.organisms.organism_profile import ORGANISM_PROFILE
from cdss.organisms.specimen_organism_map import SPECIMEN_ORDER


BACTERIA_TYPES  = list(ORGANISM_PROFILE.keys())

SPECIMEN_TYPES  = list(SPECIMEN_ORDER or DEFAULT_SPECIMENS)

AWARE_COLORS = {
    "Access":  "🟢 Access",
    "Watch":   "🟡 Watch",
    "Reserve": "🔴 Reserve",
}
