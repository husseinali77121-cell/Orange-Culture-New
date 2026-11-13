# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""Single-agent rules: D-test, fusidic acid, penicillinase, nitrofurantoin renal limit.

Every rule has the same shape:  rule(cx, dg, out) -> None
    cx   TherapyContext  the case: organism, specimen, host, mechanism (read-only)
    dg   DrugUnderTest   one agent of the panel and its S/I/R result (read-only)
    out  Outcome         where the rule records a ban / caution / note
"""
from cdss.therapy.intrinsic import build_banned_item


def rule_d_test(cx, dg, out):
    """Inducible clindamycin resistance (erythromycin R + clindamycin S needs a D-test)."""
    # ── D-test: Inducible Clindamycin Resistance (CLSI M100 Ed36) ──────────
    # cx.d_test comes from the RAW panel (cdss.common.aux_tests). It used to be
    # read from the normalised S/I/R map, where a "Negative" had already been
    # dropped -- so a recorded negative D-test could never release clindamycin
    # and a positive one was labelled "Not Confirmed".
    if "clindamycin" in dg.low and dg.result == "S":
        erythro_r = cx.sir.get("Erythromycin") == "R"
        if erythro_r:
            d_test_val = cx.d_test
            if d_test_val == "NEGATIVE":
                pass  # Confirmed D-test negative → safe to use
            else:
                label = "D-test Positive" if d_test_val == "POSITIVE" else "D-test Not Confirmed"
                out.ban(build_banned_item(
                    dg.name, "d_test_inducible",
                    f"مقاومة Clindamycin المستحثة — {label}",
                    f"Erythromycin=R + Clindamycin=S → MLSB inducible resistance محتملة. "
                    f"لا تُستخدم Clindamycin إلا بعد تأكيد D-test سالب. CLSI M100 Ed36 · EUCAST Breakpoint Tables v16.1.",
                ))
                return


def rule_fusidic_alert(cx, dg, out):
    """Fusidic acid is never monotherapy in systemic infection."""
    # ── Fusidic acid: لا monotherapy في العدوى الجهازية ─────────────────────
    if "fusidic" in dg.low and dg.info.get("no_monotherapy_systemic"):
        # Substring match rather than equality: culture_type comes from the
        # selectbox today, but an exact-match test fails silently the moment a
        # label gains a suffix ("Sputum Culture"), and losing a "never use as
        # monotherapy" warning is not a failure that should happen quietly.
        _ct = (cx.specimen or "").lower()
        if any(k in _ct for k in ("blood", "csf", "sputum")):
            cx.alerts.append(
                "⚠️ Fusidic acid: never as monotherapy in systemic infection — resistance "
                "emerges rapidly; combination is mandatory (+ Rifampicin or + Vancomycin)."
            )


def rule_staph_penicillinase(cx, dg, out):
    """Penicillinase-labile penicillins against staphylococci."""
    # ── Penicillin: Penicillinase في المكورات العنقودية ─────────────────────
    if ("penicillin" in dg.low and "oxacillin" not in dg.low
            and dg.info.get("penicillinase_sensitive")):
        org_l = (cx.organism or "").lower()
        is_staph = ("staphylococcus aureus" in org_l or "mrsa" in org_l
                    or "mssa" in org_l or "staph" in org_l)
        if is_staph and dg.result != "S":
            out.ban(build_banned_item(
                dg.name, "penicillinase_producer",
                "إنتاج Beta-lactamase (Penicillinase)",
                "90%+ من S. aureus تنتج Penicillinase → Penicillin غير فعال. "
                "استخدم Cefazolin أو Oxacillin (MSSA) أو Vancomycin (MRSA).",
            ))
            return


def rule_oxacillin_alert(cx, dg, out):
    """MSSA bacteraemia: cefazolin is non-inferior to (flu)cloxacillin."""
    # ── Oxacillin: MSSA alert للـ bacteremia ─────────────────────────────────
    if "oxacillin" in dg.low and dg.result == "S" and cx.spec_cat == "blood":
        cx.alerts.append(
            "ℹ️ Oxacillin=S (MSSA confirmed). In bacteraemia cefazolin is non-inferior to (flu)cloxacillin "
            "with less kidney injury — CloCeBa (Lancet 2025) / SNAP (NEJM 2026)."
        )


def rule_enterococcus_tmp_smx(cx, dg, out):
    """Enterococci + TMP-SMX: in-vitro S, clinically unreliable."""
    # ── Enterococcus + TMP-SMX: in-vitro S but clinically unreliable ─────────
    # Enterococci use exogenous folate/thymidine in vivo, bypassing folate
    # inhibition, so TMP-SMX may test S yet fail clinically. CLSI/EUCAST warn
    # against reporting/using it for enterococcal infections.
    if (("trimethoprim" in dg.low or "sulfamethoxazole" in dg.low or "smx" in dg.low)
            and "enterococc" in (cx.organism or "").lower()):
        out.ban(build_banned_item(
            dg.name, "organism",
            "غير موثوق سريرياً ضد Enterococcus (رغم حساسية المختبر).",
            "المكورات المعوية تستخدم الفولات/الثيميدين الخارجي داخل الجسم فتتجاوز "
            "تثبيط الفولات؛ لذلك قد يظهر TMP-SMX حساساً في المختبر لكنه يفشل سريرياً. "
            "لا يُعتمد عليه لعلاج عدوى Enterococcus (CLSI/EUCAST). استخدم "
            "Ampicillin/Amoxicillin (أو Vancomycin/Linezolid حسب الحساسية).",
        ))
        return


def rule_nitrofurantoin_renal(cx, dg, out):
    """Nitrofurantoin below its renal threshold."""
    # Nitrofurantoin: contraindicated below its renal threshold (EMA/BNF 2025 = 45)
    _nf_limit = dg.info.get("renal_limit", 45)
    if cx.is_renal and "nitrofurantoin" in dg.low and cx.crcl is not None and cx.crcl < _nf_limit:
        out.ban(build_banned_item(
            dg.name, "renal",
            f"ممنوع -- CrCl {cx.crcl:.1f} < {_nf_limit} ml/min",
            f"CrCl = {cx.crcl:.1f} مل/د -- أقل من الحد المطلوب ({_nf_limit} مل/د). "
            f"خطر عدم كفاءة علاجية + تراكم سمي (EMA/BNF 2025).{cx.crcl_src}",
        ))
        return
