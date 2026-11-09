"""Stable Streamlit session-state initialization."""

from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st


STATE_DEFAULTS: dict[str, Any] = {
    "laboratory_result": None,
    "laboratory_error": None,
    "optimization_result": None,
    "optimization_error": None,
}


def initialize_session_state(
    state: MutableMapping[str, Any] | None = None,
) -> MutableMapping[str, Any]:
    """Create every app key once and return the state mapping."""

    target = st.session_state if state is None else state
    for key, value in STATE_DEFAULTS.items():
        if key not in target:
            target[key] = value
    return target
