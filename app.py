"""Multipage Streamlit entry point for the ED resource study."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import streamlit as st

from ed_simulation.ui.state import initialize_session_state


def main() -> None:
    """Configure the app shell and run the selected page."""

    st.set_page_config(
        page_title="Flujo de emergencias",
        page_icon=":material/emergency:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    initialize_session_state()
    pages = [
        st.Page("app_pages/summary.py", title="Resumen", icon=":material/dashboard:", default=True),
        st.Page("app_pages/model.py", title="Modelo", icon=":material/account_tree:"),
        st.Page("app_pages/laboratory.py", title="Laboratorio", icon=":material/science:"),
        st.Page("app_pages/optimization.py", title="Optimización", icon=":material/tune:"),
        st.Page("app_pages/evidence.py", title="Evidencia", icon=":material/analytics:"),
    ]
    navigation = st.navigation(pages, position="sidebar", expanded=True)
    with st.sidebar:
        st.divider()
        st.caption("CC3074 · Proyecto 2 · evidencia NHAMCS 2022")
        st.warning(
            "La mejora presentada es simulada; no es una intervención observada "
            "en un hospital real.",
            icon=":material/info:",
        )
    navigation.run()


if __name__ == "__main__":
    main()
