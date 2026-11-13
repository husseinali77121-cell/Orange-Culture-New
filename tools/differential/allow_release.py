"""Classifier for the final differential (original monolith vs delivered package).

Every difference must be one of:
  * the new engine is STRICTER or EQUAL (a caution no longer ends the rule walk), or
  * one of the deliberate, documented fixes (D-test / penicillinase results now
    reach the rules; truthful possible-MRSA note).
Anything else is UNEXPLAINED and fails the run.
"""
from cdss.common.aux_tests import read_aux_tests

RANK = {"allowed": 0, "warned": 1, "preg_warn": 1, "banned": 2}
WHY = []


def buckets(res):
    out = {}
    for b in ("allowed", "warned", "preg_warn", "banned"):
        for it in res.get(b) or []:
            out.setdefault(it.get("name"), []).append((b, it))
    return out


def classify(o, n, case):
    WHY.clear()
    ro, rn = o.get("run_analysis"), n.get("run_analysis")
    if not isinstance(ro, dict) or not isinstance(rn, dict):
        WHY.append(f"non-dict result: {str(ro)[:120]} | {str(rn)[:120]}")
        return None
    aux = read_aux_tests(case["sir"])
    sir_u = {str(k).strip(): str(v or "").strip().upper() for k, v in case["sir"].items()}
    i_guard = any(sir_u.get(d) in ("I", "INTERMEDIATE") for d in ("Oxacillin", "Cefoxitin"))
    screen_s = any(sir_u.get(d) in ("S", "SENSITIVE", "SUSCEPTIBLE") for d in ("Cefoxitin", "Oxacillin"))
    I_FIX = "FIX oxacillin/cefoxitin I is flagged (no such category for staphylococci)"
    from cdss.common.aux_tests import is_aux_key
    if case["sir"] and all(is_aux_key(k) for k in case["sir"]):
        return "FIX a panel holding only a supplementary test is an empty panel"
    bo, bn = buckets(ro), buckets(rn)
    if set(bo) != set(bn):
        WHY.append(f"drug set differs: {sorted(set(bo) ^ set(bn))}")
        return None
    labels = set()
    for name in bo:
        if len(bo[name]) != 1 or len(bn[name]) != 1:
            WHY.append(f"{name} in several buckets")
            return None
        (b0, i0), (b1, i1) = bo[name][0], bn[name][0]
        if RANK[b1] < RANK[b0]:
            if name == "Clindamycin" and aux["d_test"] == "NEGATIVE" and i0.get("category") == "d_test_inducible":
                labels.add("FIX D-test NEGATIVE now releases clindamycin")
                continue
            if name in ("Penicillin", "Ampicillin", "Amoxicillin") and aux["penicillinase"] == "NEGATIVE":
                labels.add("FIX penicillinase NEGATIVE now clears the penicillin caution")
                continue
            WHY.append(f"LAXER {name}: {b0}[{i0.get('category') or i0.get('warning_reason')}] -> {b1}")
            return None
        if b0 != b1:
            cat = i1.get("category") or i1.get("warning_reason") or ""
            was = i0.get("warning_reason") or i0.get("category") or ""
            if cat == "penicillinase_producer" and aux["penicillinase"] == "POSITIVE":
                labels.add("FIX penicillinase POSITIVE now bans the penicillin")
            else:
                labels.add(f"STRICTER {b0}[{was}] -> {b1}[{cat}]")
        elif b0 == "banned" and i0 != i1 and (
                i0.get("category") != i1.get("category") or i0.get("reason_short") != i1.get("reason_short")):
            labels.add(f"REASON banned[{i0.get('category')}] -> banned[{i1.get('category')}]")
        elif (i0 != i1 and i1.get("warning_reason") == "possible_mrsa"
              and i0.get("warning_reason") != "possible_mrsa"
              and any(str(case["sir"].get(d) or "").strip().upper() in ("I", "INTERMEDIATE")
                      for d in ("Oxacillin", "Cefoxitin"))):
            labels.add("FIX oxacillin/cefoxitin I is flagged (no such category for staphylococci)")
        elif i0 != i1:
            keys = sorted(k for k in set(i0) | set(i1) if i0.get(k) != i1.get(k))
            for k in keys:
                a, b = str(i0.get(k) or ""), str(i1.get(k) or "")
                if b.startswith(a):
                    labels.add(f"NOTE+ {b0}[{i0.get('warning_reason') or i0.get('category') or ''}] {k}")
                elif k == "possible_mrsa_note" and screen_s and not i_guard:
                    labels.add("FIX possible-MRSA note states the screen that IS on the panel")
                elif i_guard and (i1.get("warning_reason") == "possible_mrsa" or "preg_note" in k):
                    labels.add(I_FIX)
                elif aux["penicillinase"] == "NEGATIVE" and name in ("Penicillin", "Ampicillin", "Amoxicillin"):
                    labels.add("FIX penicillinase NEGATIVE now clears the penicillin caution")
                elif b0 == "banned":
                    labels.add(f"REASON banned item text ({k})")
                else:
                    WHY.append(f"{name} {b0} key {k}: {a[:150]!r} -> {b[:150]!r}")
                    return None
    if not labels:
        if [i.get("name") for i in ro["banned"]] != [i.get("name") for i in rn["banned"]] \
                and sorted(map(str, ro["banned"])) == sorted(map(str, rn["banned"])):
            labels.add("ORDER banned list now in panel order")
        if set(ro.get("interactions") or []) < set(rn.get("interactions") or []):
            labels.add("ALERT+ extra side alert")
        po = {p.get("phenotype"): p for p in ro.get("phenotypes") or []}
        pn = {p.get("phenotype"): p for p in rn.get("phenotypes") or []}
        if set(po) == set(pn) and po != pn and "Possible MRSA" in po:
            labels.add("FIX possible-MRSA note states the screen that IS on the panel")
        if set(pn) - set(po) == {"Possible MRSA"} and any(
                case["sir"].get(d) == "I" for d in ("Oxacillin", "Cefoxitin")):
            labels.add("FIX oxacillin/cefoxitin I is flagged (no such category for staphylococci)")
        named = {"MRSA": "mrsa", "VRE": "vre"}
        added = set(pn) - set(po)
        org_l = str(case["organism"] or "").lower()
        if added and added <= set(named) and all(named[a] in org_l for a in added):
            labels.add("FIX phenotype stated by the organism name (MRSA / VRE) is reported")
        if not labels:
            WHY.append("buckets identical; a derived output differs")
            return None
    return " | ".join(sorted(labels))
