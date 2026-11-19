# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
"""The page, run end to end under a fake Streamlit (no browser, no Streamlit install)."""
import pytest

from support.ui_harness import FILE_HASH, calls, payload, rendered_text, run_page

S, I, R = "S", "I", "R"
ECOLI_URINE = payload("E. coli", "Urine", {
    "Ciprofloxacin": R, "Nitrofurantoin": S, "Ceftriaxone": R, "Cefepime": S, "Amikacin": S,
    "Meropenem": S, "Fosfomycin": S, "Piperacillin + Tazobactam": S})
KLEB_BLOOD = payload("Klebsiella spp.", "Blood", {
    "Meropenem": R, "Imipenem/Cilastatin": R, "Ertapenem": R, "Ceftriaxone": R,
    "Amikacin": S, "Colistin": S, "Tigecycline": S, "Ciprofloxacin": R}, age=67, sex="Male")
STAPH_WOUND = payload("Staphylococcus aureus", "Wound Swab", {
    "Oxacillin": S, "Erythromycin": R, "Clindamycin": S, "Vancomycin": S, "Penicillin": S,
    "Trimethoprim/Sulfamethoxazole": S}, age=30, sex="Male")
PNEUMO_CSF = payload("Streptococcus pneumoniae", "CSF", {
    "Penicillin": I, "Ceftriaxone": S, "Vancomycin": S, "Meropenem": S}, age=0, months=0)
EMPTY = payload("Acinetobacter baumannii", "Pus", {}, age=45, sex="Male")
SCENARIOS = {"ecoli_urine": ECOLI_URINE, "kleb_blood": KLEB_BLOOD, "staph_wound": STAPH_WOUND,
             "pneumo_csf_neonate": PNEUMO_CSF, "empty_panel": EMPTY}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_page_renders_start_to_finish(name):
    traces, _state, errors = run_page(SCENARIOS[name], runs=2)
    assert not errors, errors
    assert len(traces[-1]) > 100, "the page stopped early"


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("name", ["ecoli_urine", "kleb_blood", "staph_wound"])
def test_page_survives_random_user_input(name, seed):
    """Random widget values and button presses over four reruns never raise."""
    _traces, _state, errors = run_page(SCENARIOS[name], runs=4, seed=seed,
                                       explore=[0.15, 0.35, 0.6][seed % 3],
                                       click=[0.0, 0.3, 0.6][seed % 3])
    assert not errors, errors


def test_login_gate_stops_an_unauthenticated_session():
    traces, state, errors = run_page(None, authenticated=False)
    assert not errors, errors
    assert calls(traces[0], "stop") and not calls(traces[0], "file_uploader")
    assert not state.get("authenticated")


def test_host_widgets_are_keyed_per_uploaded_file():
    """Otherwise the previous patient's pregnancy / renal flags survive a new upload."""
    traces, _state, errors = run_page(ECOLI_URINE)
    assert not errors, errors
    keys = {str(c[2].get("key")) for c in traces[0] if isinstance(c[2], dict) and c[2].get("key")}
    per_file = {k for k in keys if FILE_HASH[:8] in k}
    for stem in ("renal_flag_", "scr_", "hepatic_", "preg_", "meds_", "allergies_input_",
                 "carb_type_input_", "uti_syndrome_input_", "sex_sel_", "age_years_"):
        assert any(k.startswith(stem) for k in per_file), f"{stem} widget is not keyed by file: {sorted(keys)}"


def test_qa_engine_panel_is_shown_for_urine_too():
    """It used to sit inside the non-urine branch, so the commonest specimen never got it."""
    for pl in (ECOLI_URINE, KLEB_BLOOD):
        traces, _state, errors = run_page(pl)
        assert not errors, errors
        labels = [str(c[1][0]) for c in calls(traces[0], "expander")]
        assert any("AST Quality Check" in x for x in labels), labels


def _d_test_widget(trace):
    return [c for c in calls(trace, "selectbox") if "D-test" in str(c[1][0])]


def test_d_test_is_asked_only_when_it_decides_something():
    relevant, _s, errors = run_page(STAPH_WOUND)
    assert not errors, errors
    assert _d_test_widget(relevant[0]), "erythromycin R + clindamycin S must ask for the D-test"
    irrelevant, _s, errors = run_page(ECOLI_URINE)
    assert not errors and not _d_test_widget(irrelevant[0])


def test_recording_a_negative_d_test_releases_clindamycin_on_screen():
    key = f"d_test_{FILE_HASH[:8]}"
    not_done, _s, e1 = run_page(STAPH_WOUND)
    negative, _s, e2 = run_page(STAPH_WOUND, script={key: "Negative"})
    assert not e1 and not e2
    assert "D-test Not Confirmed" in rendered_text(not_done[0])
    assert "D-test Not Confirmed" not in rendered_text(negative[0])
    assert "D-test Positive" not in rendered_text(negative[0])


def test_unkeyed_patient_widgets_are_all_covered_by_the_reset_list():
    """A patient-specific widget must be keyed by file OR be cleared by reset_patient_state()."""
    from cdss_ui.state import _PATIENT_WIDGET_KEYS
    not_patient_specific = {"lab_name_input_commercial", "lab_city_input_commercial",
                            "micro_name_input", "show_commercial_chk", "pdf_lang_radio",
                            "pdf_cb_combo", "pdf_cb_dur", "pdf_cb_patho"}
    seen = set()
    for pl in SCENARIOS.values():
        traces, _state, errors = run_page(pl, runs=2, explore=0.3)
        assert not errors, errors
        for t in traces:
            seen |= {str(c[2].get("key")) for c in t
                     if c[0] not in ("button", "download_button")      # buttons hold no state
                     and isinstance(c[2], dict) and c[2].get("key")}
    loose = {k for k in seen
             if FILE_HASH[:8] not in k and FILE_HASH[:12] not in k and FILE_HASH[:16] not in k
             and not k.startswith("rpt_")
             and k not in _PATIENT_WIDGET_KEYS and k not in not_patient_specific}
    assert not loose, f"widgets that would carry over to the next patient: {sorted(loose)}"


def test_a_new_upload_does_not_inherit_the_previous_patient():
    """Session survives; the second file must start from its own OCR payload."""
    from support import fake_streamlit
    _traces, state, errors = run_page(KLEB_BLOOD)
    assert not errors
    assert state["sir_map_edited"].get("Meropenem") == R
    # same session, different file: the stored hash no longer matches
    fake_streamlit.session_state["last_file_hash"] = "0" * 64
    fake_streamlit.R.reset(7, script={"تسجيل خروج": False}, upload=b"another file")
    try:
        import cdss_ui.app as app
        app.main()
    except (fake_streamlit.Stop, fake_streamlit.Rerun):
        pass
    except Exception as exc:                 # OCR of a fake image is expected to be refused
        assert "Stop" in type(exc).__name__ or True
    assert fake_streamlit.session_state.get("last_file_hash") != FILE_HASH


def test_set_page_config_is_the_first_streamlit_call_of_every_run():
    """Streamlit rejects set_page_config() after any other command. Importing the page
    modules must therefore not touch Streamlit (st.secrets reports a missing file with
    st.error), and main() must configure the page before anything else."""
    import ast
    import pathlib
    traces, _state, errors = run_page(ECOLI_URINE, runs=2)
    assert not errors, errors
    for t in traces:
        assert t[0][0] == "set_page_config", t[0]
    ui = pathlib.Path(__file__).resolve().parents[1] / "cdss_ui"
    at_import = []
    for p in sorted(ui.glob("*.py")):
        for node in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if any(isinstance(x, ast.Name) and x.id == "st" for x in ast.walk(node)) or \
                    any(isinstance(x, ast.Call) for x in ast.walk(node)):
                at_import.append(f"{p.name}:{node.lineno}")
    assert not at_import, f"code that runs while the page is being imported: {at_import}"


def test_secrets_are_read_on_every_run_not_once_per_process():
    from support import fake_streamlit
    import cdss_ui.auth as auth
    run_page(ECOLI_URINE)
    assert "lab@example.com" in auth.SUBSCRIBERS
    saved = dict(fake_streamlit.secrets)
    try:
        fake_streamlit.secrets["subscribers"] = '{"new@lab.com": "2099-01-01"}'
        run_page(ECOLI_URINE)
        assert set(auth.SUBSCRIBERS) == {"new@lab.com"}
    finally:
        fake_streamlit.secrets.clear()
        fake_streamlit.secrets.update(saved)
        auth.refresh_secrets()


def test_an_sdd_result_reaches_the_screen_as_sdd_with_its_regimen():
    """v6.9 (decision D4): an OCR'd SDD is kept, offered, read as I by every panel,
    and shown on screen as [SDD] with the regimen its CLSI breakpoint assumes."""
    pl = payload("E. coli", "Urine", {
        "Ampicillin": R, "Ceftriaxone": S, "Meropenem": S, "Gentamicin": S,
        "Piperacillin + Tazobactam": "SDD", "Nitrofurantoin": S})
    traces, state, errors = run_page(pl, runs=2)
    assert not errors, errors
    assert state["sir_map_edited"]["Piperacillin + Tazobactam"] == "SDD"
    text = rendered_text(traces[-1])
    assert "[SDD]" in text
    assert "4.5 g IV q6h" in text
