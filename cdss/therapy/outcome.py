# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Outcome: what the rules decided about ONE drug.

The old engine was a 1,300-line loop in which every caution ended in
`continue`, so whatever came after it in the file never ran for that drug.
Three review rounds each fixed one instance of the same defect (a pregnancy
caution that skipped the hepatic check, an ESBL caution that skipped the renal
check, ...).  This class removes the defect by construction:

  * a BAN is terminal            -- nothing can be stricter, the engine stops;
  * a CAUTION is recorded, and the drug KEEPS WALKING through every later
    rule, each of which can still ban it or add its own fact;
  * a NOTE never decides anything on its own.

So the order of the rules decides which reason is shown first, and never
whether a contraindication is checked at all.
"""
from typing import Any, Dict, List, Optional, Tuple

# (level, text, primary reason, every reason) per drug -- applied after the loop
# (postprocess.apply_clinical_notes). The 4th element (v6.9) lets the English
# report print the English sentence of EVERY note merged on the drug, not only
# the primary one -- an organism caution must not hide a paediatric one.
PostNotes = Dict[str, Tuple[str, str, str, Tuple[str, ...]]]


class Outcome:
    __slots__ = ("banned", "primary", "secondary", "extra", "preg_item", "preg_extra",
                 "skip_mech", "_post_notes")

    def __init__(self, post_notes: PostNotes) -> None:
        self.banned: Optional[Dict[str, Any]] = None      # the ban item, once any rule bans
        self.primary: Optional[Dict[str, Any]] = None     # first caution: decides warning_reason
        self.secondary: List[Dict[str, Any]] = []         # later cautions on the same drug
        self.extra: List[str] = []                        # host facts added to the primary's note
        self.preg_item: Optional[Dict[str, Any]] = None   # pregnancy caution (own bucket)
        self.preg_extra: List[str] = []                   # facts appended to the pregnancy note
        self.skip_mech: bool = False                      # novel agent / AmpC-cefepime: mechanism rules do not apply
        self._post_notes = post_notes

    # ── verdicts ────────────────────────────────────────────────────────────
    def ban(self, item: Dict[str, Any]) -> None:
        """Terminal. The first ban is the one reported."""
        if self.banned is None:
            self.banned = item

    def caution(self, item: Dict[str, Any]) -> None:
        """Non-terminal. The first caution is the primary reason; later ones are kept too."""
        if self.primary is None:
            self.primary = item
        else:
            self.secondary.append(item)

    def note(self, drug: str, level: str, text: str, reason: str) -> None:
        """Merge, never overwrite: an allergy caution must survive a later
        novel-agent note on the same drug. 'warn' beats 'allow'; the reason of
        the first WARNING is kept as the primary one; texts are joined."""
        notes = self._post_notes
        if drug not in notes:
            notes[drug] = (level, text, reason, (reason,))
            return
        old_level, old_text, old_reason, old_all = notes[drug]
        new_level = "warn" if "warn" in (old_level, level) else "allow"
        new_reason = old_reason if (old_level == "warn" or level != "warn") else reason
        notes[drug] = (new_level, old_text if text in old_text else f"{old_text}  \n{text}", new_reason,
                       old_all if reason in old_all else old_all + (reason,))
