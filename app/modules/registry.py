"""
Module registry for DM Toolkit-style add-ons.

Design goals:
- New generators live in app/modules/<module>.py
- Core Encounter Builder stays stable.
- Modules can be enabled/disabled without touching core features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import streamlit as st


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    section: str  # "Toolkit", "Admin", etc.
    render: Callable[[], None]
    init_db: Optional[Callable[[], None]] = None


def toolkit_enabled() -> bool:
    """
    Safety switch. Default OFF unless explicitly enabled.
    - Streamlit Cloud: put enable_toolkit=true in Secrets.
    - Local: set env var ENABLE_TOOLKIT=true (optional).
    """
    try:
        val = st.secrets.get("enable_toolkit", False)
        return bool(val)
    except Exception:
        return False


def get_modules() -> List[Module]:
    """
    Return registered modules.
    For now, this list will be empty until we add Name Generator.
    """
    return []


def init_all_module_tables() -> None:
    """
    Call init_db() for all registered modules that define it.
    Safe to call multiple times.
    """
    for m in get_modules():
        if m.init_db:
            m.init_db()
