# Differential harness — old single-file app vs this package

Used once, for the 2026-11-12 restructure, to prove what did and did not change.
Kept so the proof can be re-run.

```bash
# <old_tree> = an unpacked copy of the last single-file release
python tools/differential/diff_engine.py <old_tree> . 12000 90001 --allow allow_release --show 1
```

For every case (the project's own scenario matrix with a random host, plus N random
panels over every organism / specimen / host / option) both engines are run in one
process and compared deeply: `run_analysis()`, `run_ast_qc()`, the QA confidence, the
final checklist, the text report and the PDF HTML in Arabic and English.

`allow_release.py` is the only place that decides what counts as an acceptable
difference. It accepts exactly:

| label | meaning |
|---|---|
| `STRICTER a -> b` | a drug moved to a stricter bucket (a caution no longer hides a later ban / pregnancy caution) |
| `REASON banned[x] -> banned[y]` | banned before and banned now; the engine states the specific reason itself instead of leaving it to the safety gate |
| `NOTE+` | same bucket; a note gained text (a fact that used to be skipped) |
| `ORDER` | the banned list is in panel order |
| `ALERT+` | an extra side alert |
| `FIX ...` | one of the documented fixes (D-test, penicillinase, possible-MRSA wording, oxacillin/cefoxitin I) |

A drug moving to a **laxer** bucket for any other reason is `UNEXPLAINED` and the run fails.

Needs the same optional libraries the old file imported at load time to be either
present or absent on both sides; no Streamlit is required (`st_stub.py`).
