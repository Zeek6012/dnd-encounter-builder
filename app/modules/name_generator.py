"""
Name Generator module (DM Toolkit)

Data model v1:
- Store FIRST and LAST (you have both)
- Store your STYLE category (Common/Guttural/etc.)
- Add tags we can auto-assign + later override:
  - ancestry (e.g., Dwarf, Elf, Human, Orc, Gnome, Halfling, Tiefling, Dragonborn, etc.)
  - gender (male/female) and/or neutral
- Support filtering by any combination of the above.

This module is intentionally self-contained and does not modify core Encounter Builder logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import streamlit as st
from sqlalchemy import text, bindparam
from app.db import get_session


# ----------------------------
# Config / Controlled vocab
# ----------------------------

STYLE_CATEGORIES = [
    "Common Names",
    "Gutteral Names",
    "Lyrical Names",
    "Monosyllabic Names",
    "Sinister Names",
    "Whimsical Names",
]

# We can expand this later, but keeping it simple for v1.
ANCESTRY_OPTIONS = [
    "Human",
    "Dwarf",
    "Elf",
    "Halfling",
    "Gnome",
    "Orc",
    "Tiefling",
    "Dragonborn",
    "Goblin",
    "Undead",
    "Other",
]

GENDER_OPTIONS = ["Male", "Female", "Neutral", "Unknown"]

STARTER_DATA = [('Common Names', 'Adrik', 'Brightsun'),
 ('Common Names', 'Alvyn', 'Dundragon'),
 ('Common Names', 'Aurora', 'Frostbear'),
 ('Common Names', 'Eldeth', 'Garrick'),
 ('Common Names', 'Eldon', 'Goodbarrel'),
 ('Common Names', 'Finnan', 'Greycastle'),
 ('Common Names', 'Hilda', 'Harrowmoon'),
 ('Common Names', 'Jasper', 'Ironwood'),
 ('Common Names', 'Kara', 'Lightfoot'),
 ('Common Names', 'Leif', 'Mistvale'),
 ('Common Names', 'Mira', 'Oakshield'),
 ('Common Names', 'Nolan', 'Riversong'),
 ('Common Names', 'Orin', 'Silverbrook'),
 ('Common Names', 'Pella', 'Stonehand'),
 ('Common Names', 'Quinn', 'Thornfield'),
 ('Common Names', 'Ronan', 'Underbough'),
 ('Common Names', 'Sable', 'Windmere'),
 ('Common Names', 'Talia', 'Wolfsbane'),
 ('Common Names', 'Varen', 'Ashford'),
 ('Common Names', 'Zorra', 'Wren'),
 ('Gutteral Names', 'Brug', 'Ashgut'),
 ('Gutteral Names', 'Dreg', 'Brokentooth'),
 ('Gutteral Names', 'Gruk', 'Cragjaw'),
 ('Gutteral Names', 'Harg', 'Doomfist'),
 ('Gutteral Names', 'Jurk', 'Foulmaw'),
 ('Gutteral Names', 'Krug', 'Gorefang'),
 ('Gutteral Names', 'Murg', 'Hardskull'),
 ('Gutteral Names', 'Rok', 'Ironsnarl'),
 ('Gutteral Names', 'Skarn', 'Kragspike'),
 ('Gutteral Names', 'Throg', 'Mudscar'),
 ('Lyrical Names', 'Aelir', 'Dawnsong'),
 ('Lyrical Names', 'Caelynn', 'Evershade'),
 ('Lyrical Names', 'Elaria', 'Faywhisper'),
 ('Lyrical Names', 'Ithil', 'Glimmerleaf'),
 ('Lyrical Names', 'Liora', 'Moonpetal'),
 ('Lyrical Names', 'Naeris', 'Silverbloom'),
 ('Lyrical Names', 'Orith', 'Starwillow'),
 ('Lyrical Names', 'Syllan', 'Windweave'),
 ('Lyrical Names', 'Vaelin', 'Brightbranch'),
 ('Lyrical Names', 'Ylva', 'Sunlark'),
 ('Monosyllabic Names', 'Brom', 'Iron'),
 ('Monosyllabic Names', 'Drak', 'Stone'),
 ('Monosyllabic Names', 'Fenn', 'Forge'),
 ('Monosyllabic Names', 'Garn', 'Oak'),
 ('Monosyllabic Names', 'Hild', 'Bronze'),
 ('Monosyllabic Names', 'Krag', 'Coal'),
 ('Monosyllabic Names', 'Marn', 'Anvil'),
 ('Monosyllabic Names', 'Rulf', 'Hammer'),
 ('Monosyllabic Names', 'Thorn', 'Ale'),
 ('Monosyllabic Names', 'Varn', 'Rune'),
 ('Sinister Names', 'Azrael', 'Blackveil'),
 ('Sinister Names', 'Belth', 'Gravesmile'),
 ('Sinister Names', 'Damar', 'Nightgaze'),
 ('Sinister Names', 'Eris', 'Vilethorn'),
 ('Sinister Names', 'Kass', 'Hexborn'),
 ('Sinister Names', 'Lucian', 'Ashwraith'),
 ('Sinister Names', 'Morra', 'Bloodsigil'),
 ('Sinister Names', 'Nox', 'Dreadmere'),
 ('Sinister Names', 'Sable', 'Ruinmark'),
 ('Sinister Names', 'Vesper', 'Grimveil'),
 ('Whimsical Names', 'Bibble', 'Bramblepot'),
 ('Whimsical Names', 'Clover', 'Dapplewick'),
 ('Whimsical Names', 'Doodle', 'Fizzlebark'),
 ('Whimsical Names', 'Glim', 'Honeywhistle'),
 ('Whimsical Names', 'Mimsy', 'Jinglecap'),
 ('Whimsical Names', 'Pip', 'Merrymug'),
 ('Whimsical Names', 'Sprig', 'Nimblekettle'),
 ('Whimsical Names', 'Tink', 'Puddlepin'),
 ('Whimsical Names', 'Wob', 'Quibblequill'),
 ('Whimsical Names', 'Zuzu', 'Sparkletoe')]


def init_db() -> None:
    """
    Create toolkit_names table (works on SQLite + Postgres).
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS toolkit_names (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name    TEXT NOT NULL,
        last_name     TEXT NOT NULL,
        style_category TEXT NOT NULL,

        ancestry_tag  TEXT NOT NULL DEFAULT 'Unknown',
        gender_tag    TEXT NOT NULL DEFAULT 'Unknown',
        is_neutral    BOOLEAN NOT NULL DEFAULT 0,

        needs_review  BOOLEAN NOT NULL DEFAULT 1,
        source        TEXT,
        notes         TEXT
    );
    """
    # Postgres doesn't support AUTOINCREMENT; but SQLite will ignore SERIAL, so we keep it SQLite-friendly.
    # On Postgres, SQLAlchemy typically uses SERIAL/IDENTITY via models, but we're keeping a simple DDL.
    # If running on Postgres, the existing DB layer already handles tables; we'll patch this later if needed.
    # For now, we create the table only if it doesn't exist; if Postgres complains, we handle in UI.
    try:
        with get_session() as s:
            s.execute(text(ddl))
            s.commit()
    except Exception as e:
        # Don't crash the app; surface the error in the UI.
        st.error(f"Name Generator DB init failed: {e}")


# ----------------------------
# Auto-tag heuristics (v1)
# ----------------------------

def _suggest_ancestry(style: str, first: str, last: str) -> str:
    """
    Very rough initial mapping (we will refine once we see your actual name lists).
    """
    n = (first + " " + last).lower()

    if style == "Gutteral Names":
        return "Orc"
    if style == "Lyrical Names":
        return "Elf"
    if style == "Monosyllabic Names":
        return "Dwarf"
    if style == "Sinister Names":
        return "Tiefling"
    if style == "Whimsical Names":
        return "Gnome"
    return "Human"


def _suggest_gender(first: str) -> Tuple[str, bool]:
    """
    Conservative defaults:
    - If ambiguous, keep Unknown + neutral False.
    - We can later add better heuristics or a review UI (recommended).
    """
    f = first.strip().lower()

    # quick-and-dirty hints; we’ll refine later with your data
    if f.endswith(("a", "ia", "elle", "lyn", "lynn", "na")):
        return ("Female", False)
    if f.endswith(("o", "or", "an", "en", "in", "us", "ar")):
        return ("Male", False)

    return ("Unknown", False)


# ----------------------------
# Import / parse helpers
# ----------------------------

HEADER_RE = re.compile(r"^\s*(#+\s*)?(?P<h>Common Names|Gutteral Names|Lyrical Names|Monosyllabic Names|Sinister Names|Whimsical Names)\s*$", re.I)

def _parse_paste(text_blob: str) -> List[Tuple[str, str, str]]:
    """
    Accepts pasted content like:

    Common Names
    Alice Brook
    Talan Reed

    Gutteral Names
    Krug Blacktooth

    Returns rows as: (style_category, first_name, last_name)
    """
    rows: List[Tuple[str, str, str]] = []
    current_style: Optional[str] = None

    for raw in (text_blob or "").splitlines():
        line = raw.strip()
        if not line:
            continue

        m = HEADER_RE.match(line)
        if m:
            # normalize header capitalization to our canonical list
            h = m.group("h").lower()
            for cat in STYLE_CATEGORIES:
                if cat.lower() == h:
                    current_style = cat
                    break
            continue

        # If we have no header yet, skip (forces a clean structure)
        if not current_style:
            continue

        # Split into first + last by last token
        parts = line.split()
        if len(parts) < 2:
            continue

        last = parts[-1]
        first = " ".join(parts[:-1])
        rows.append((current_style, first, last))

    return rows


# ----------------------------
# UI
# ----------------------------

def render() -> None:
    st.header("Name Generator")

    # Ensure table exists (safe to call repeatedly)
    init_db()

    tab_gen, tab_add, tab_review = st.tabs(["Generate", "Add Names", "Review Queue"])

    with tab_gen:
        st.subheader("Filters")
        c1, c2, c3 = st.columns(3)
        with c1:
            style_filter = st.multiselect("Style Category", STYLE_CATEGORIES, default=[])
        with c2:
            ancestry_filter = st.multiselect("Ancestry", ["Unknown"] + ANCESTRY_OPTIONS, default=[])
        with c3:
            gender_filter = st.multiselect("Gender", ["Unknown"] + GENDER_OPTIONS, default=[])

        st.divider()

        if st.button("Generate Name", width="stretch"):
            with get_session() as s:
                q = """
                SELECT first_name, last_name, style_category, ancestry_tag, gender_tag, is_neutral
                FROM toolkit_names
                WHERE 1=1
                """
                params: Dict[str, object] = {}

                if style_filter:
                    q += " AND style_category IN :styles"
                    params["styles"] = tuple(style_filter)

                if ancestry_filter:
                    q += " AND ancestry_tag IN :ancestries"
                    params["ancestries"] = tuple(ancestry_filter)

                if gender_filter:
                    q += " AND gender_tag IN :genders"
                    params["genders"] = tuple(gender_filter)

                q += " ORDER BY RANDOM() LIMIT 1"

                try:
                    txt = text(q)

                    # Enable safe list expansion for IN (...) filters
                    if style_filter:
                        txt = txt.bindparams(bindparam("styles", expanding=True))
                    if ancestry_filter:
                        txt = txt.bindparams(bindparam("ancestries", expanding=True))
                    if gender_filter:
                        txt = txt.bindparams(bindparam("genders", expanding=True))

                    row = s.execute(txt, params).fetchone()
                except Exception:
                    row = None
                if not row:
                    st.warning("No names match those filters yet. Add more names first.")
                else:
                    first, last, style_cat, anc, gen, neutral = row
                    st.success(f"**{first} {last}**")
                    st.caption(f"{style_cat} • {anc} • {gen}{' • Neutral' if neutral else ''}")

    with tab_add:
        st.subheader("Paste Names (structured by category)")
        st.write("Paste your lists using category headers (exact names below). Each name should be `First Last` per line.")
        st.code("\n".join(STYLE_CATEGORIES))

        if st.button("Load Starter Dataset (70 names)", width="stretch", key="ng_seed_btn"):
            with get_session() as s:
                # Only seed if table is empty (prevents accidental duplicates)
                existing = s.execute(text("SELECT COUNT(*) FROM toolkit_names")).scalar()
                if existing and int(existing) > 0:
                    st.warning("Starter dataset not loaded because names already exist in the database.")
                else:
                    inserted = 0
                    for style_cat, first, last in STARTER_DATA:
                        anc = _suggest_ancestry(style_cat, first, last)
                        gen, neutral = _suggest_gender(first)
                        s.execute(
                            text("""INSERT INTO toolkit_names
                            (first_name, last_name, style_category, ancestry_tag, gender_tag, is_neutral, needs_review)
                            VALUES (:first, :last, :style, :anc, :gen, :neutral, 1)"""),
                            {
                                "first": first.strip(),
                                "last": last.strip(),
                                "style": style_cat,
                                "anc": anc,
                                "gen": gen,
                                "neutral": 1 if neutral else 0,
                            },
                        )
                        inserted += 1
                    s.commit()
                    st.success(f"Loaded starter dataset: {inserted} names (auto-tagged, needs review).")

        blob = st.text_area("Paste here", height=260, placeholder="Common Names\nAlice Brook\nTalan Reed\n\nGutteral Names\nKrug Blacktooth\n...")

        if st.button("Import (auto-tag + send to review)", width="stretch"):
            rows = _parse_paste(blob)
            if not rows:
                st.error("No valid rows found. Make sure you included headers and each line is First Last.")
            else:
                inserted = 0
                with get_session() as s:
                    for style_cat, first, last in rows:
                        anc = _suggest_ancestry(style_cat, first, last)
                        gen, neutral = _suggest_gender(first)

                        s.execute(
                            text("""
                                INSERT INTO toolkit_names
                                (first_name, last_name, style_category, ancestry_tag, gender_tag, is_neutral, needs_review)
                                VALUES (:first, :last, :style, :anc, :gen, :neutral, 1)
                            """),
                            {
                                "first": first.strip(),
                                "last": last.strip(),
                                "style": style_cat,
                                "anc": anc,
                                "gen": gen,
                                "neutral": 1 if neutral else 0,
                            },
                        )
                        inserted += 1
                    s.commit()

                st.success(f"Imported {inserted} names. They are auto-tagged and placed into the Review Queue.")

    with tab_review:
        st.subheader("Review Queue (needs_review = true)")
        st.write("This is where you’ll approve/adjust ancestry + gender tags. (We’ll build the UI next.)")
        with get_session() as s:
            try:
                rows = s.execute(
                    text("""
                        SELECT id, first_name, last_name, style_category, ancestry_tag, gender_tag, is_neutral
                        FROM toolkit_names
                        WHERE needs_review = 1
                        ORDER BY id DESC
                        LIMIT 25
                    """)
                ).fetchall()
            except Exception as e:
                rows = []
                st.error(f"Query failed: {e}")

        if not rows:
            st.info("No names pending review.")
        else:
            # Plain text preview (no pandas / no table widgets)
            lines = []
            for r in rows:
                lines.append(f"{r[0]} | {r[1]} {r[2]} | {r[3]} | {r[4]} | {r[5]}{' | Neutral' if r[6] else ''}")
            st.code("\n".join(lines))
            st.caption("Next step: add per-row edit + approve buttons (still no table widgets).")


# Required module metadata
MODULE_ID = "name_generator"
MODULE_NAME = "Name Generator"
MODULE_SECTION = "Toolkit"
