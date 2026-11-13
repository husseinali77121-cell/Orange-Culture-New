"""Import the ORIGINAL monolith (untouched copy) as module `old_app`."""
import importlib.util, os, sys
OLD = None            # set by diff_engine.py from its first argument


def load_old():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import st_stub
    st = st_stub.install()
    st.session_state["authenticated"] = True
    if OLD not in sys.path:
        sys.path.append(OLD)          # appended: new package wins on name clashes (there are none)
    cwd = os.getcwd(); os.chdir(OLD)
    try:
        spec = importlib.util.spec_from_file_location("old_app", os.path.join(OLD, "streamlit_app.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["old_app"] = mod
        try:
            spec.loader.exec_module(mod)
        except st_stub.Stop:
            pass
    finally:
        os.chdir(cwd)
    return mod
