"""
Module registry for DM Toolkit-style add-ons.

Design goals:
- New generators live in app/modules/<module>.py
- Core Encounter Builder stays stable.
- Modules can be enabled/disabled without touching core features.
"""

from __future__ import annotations

import os

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

    Enable options:
    - Local: set env var ENABLE_TOOLKIT=true
    - Streamlit Cloud / local secrets: set enable_toolkit=true
    """
    # Local env var (fast for testing)
    env_val = os.getenv("ENABLE_TOOLKIT", "").strip().lower()
    if env_val in ("1", "true", "yes", "on"):
        return True

    # Secrets (Cloud or local .streamlit/secrets.toml)
    try:
        val = st.secrets.get("enable_toolkit", False)
        return bool(val)
    except Exception:
        return False


def get_modules() -> List[Module]:
    """
    Return registered modules.
    """
    # Import inside function to avoid import-time side effects
    from app.modules import name_generator

    return [
        Module(
            id=name_generator.MODULE_ID,
            name=name_generator.MODULE_NAME,
            section=name_generator.MODULE_SECTION,
            render=name_generator.render,
            init_db=name_generator.init_db,
        ),
    ]


def init_all_module_tables() -> None:
    """
    Call init_db() for all registered modules that define it.
    Safe to call multiple times.
    """
    for m in get_modules():
        if m.init_db:
            m.init_db()
