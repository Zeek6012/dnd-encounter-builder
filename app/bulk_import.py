from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Dict, List, Tuple

import streamlit as st
from sqlalchemy import select

from db import get_session, Monster, NPC

# --------------------------------------------------------------------------------------
# CSV Columns
# --------------------------------------------------------------------------------------

# Data columns closely matching DB fields.
DATA_COLUMNS: List[str] = [
    "name",
    "creature_type",
    "size",
    "alignment",
    "ac",
    "has_shield",  # 0/1 or true/false/yes/no
    "hp",
    "speed",
    "str_score",
    "dex_score",
    "con_score",
    "int_score",
    "wis_score",
    "cha_score",
    "save_str",
    "save_dex",
    "save_con",
    "save_int",
    "save_wis",
    "save_cha",
    "saves",  # optional free-text
    "skills",
    "damage_vulnerabilities",
    "damage_resistances",
    "damage_immunities",
    "condition_immunities",
    "senses",
    "languages",
    "cr",
    "pb",
    "traits",
    "actions",
    "bonus_actions",
    "reactions",
    "legendary_actions",
    "lair_actions",
    "equipment",
    "notes",
]

# Target columns (optional in CSV, but included in the template)
TARGET_COLUMNS: List[str] = [
    "to_monsters",
    "to_npcs",
]

TEMPLATE_COLUMNS: List[str] = DATA_COLUMNS + TARGET_COLUMNS


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def _truthy(v: str) -> bool:
    s = (v or "").strip().lower()
    return s in ("1", "true", "t", "yes", "y", "on")


def _boolish_to_int(v: str) -> int:
    # Used for DB fields like has_shield
    return 1 if _truthy(v) else 0


def _to_int(v: str, default: int) -> int:
    s = (v or "").strip()
    if s == "":
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def _clean(s: str) -> str:
    return (s or "").strip()

def _normalize_cr(v: str) -> str:
    """
    Fix common spreadsheet auto-conversions like '8-Jan' (from '1/8').
    Also accepts decimals: 0.125/0.25/0.5 -> 1/8, 1/4, 1/2.
    """
    s = _clean(v)
    if not s:
        return s

    low = s.lower().strip()

    # Decimal forms (common if users choose to avoid fractions)
    if low in ("0.125", ".125"):
        return "1/8"
    if low in ("0.25", ".25"):
        return "1/4"
    if low in ("0.5", ".5"):
        return "1/2"

    # Excel/Sheets fraction->date conversions (e.g., 8-Jan, Jan-8, Jan-08)
    m = re.match(r"^(?:jan)\s*-\s*(\d{1,2})$", low) or re.match(r"^(\d{1,2})\s*-\s*(?:jan)$", low)
    if m:
        day = int(m.group(1))
        if day == 8:
            return "1/8"
        if day == 4:
            return "1/4"
        if day == 2:
            return "1/2"

    # If the string contains 'jan' and a standalone 2/4/8, map it (covers some locale variants)
    if "jan" in low:
        dm = re.search(r"\b(2|4|8)\b", low)
        if dm:
            day = int(dm.group(1))
            return {2: "1/2", 4: "1/4", 8: "1/8"}[day]

    return s



def _template_csv() -> str:
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(TEMPLATE_COLUMNS)
    # One empty starter row (easy to tab through)
    w.writerow(["" for _ in TEMPLATE_COLUMNS])
    return buf.getvalue()


def _read_csv(upload) -> Tuple[List[Dict[str, str]], List[str]]:
    raw = upload.getvalue().decode("utf-8-sig", errors="replace")
    rdr = csv.DictReader(StringIO(raw))
    if not rdr.fieldnames:
        return [], ["CSV has no headers. Download the template and try again."]

    # Normalize header names (case/whitespace)
    normalized_fieldnames = [fn.strip() for fn in rdr.fieldnames if fn]
    if "name" not in normalized_fieldnames:
        return [], ["CSV must include a 'name' column. Use the template."]

    # Accept extra columns; ignore them.
    rows: List[Dict[str, str]] = []
    for r in rdr:
        rr = {}
        for k, v in r.items():
            kk = (k or "").strip()
            if kk:
                rr[kk] = v
        rows.append(rr)

    # Warnings: missing non-target template columns are ok, treated as blank.
    missing_data_cols = [c for c in DATA_COLUMNS if c not in normalized_fieldnames]
    warnings: List[str] = []
    if missing_data_cols:
        warnings.append(
            "Some template columns are missing (they will be treated as blank): "
            + ", ".join(missing_data_cols)
        )

    # Targets are optional; no warning if missing.
    return rows, warnings


def _model_for(kind: str):
    return Monster if kind == "monster" else NPC


def _existing_names(kind: str) -> set[str]:
    Model = _model_for(kind)
    with get_session() as s:
        names = s.scalars(select(Model.name)).all()
    return set(names or [])


def _unique_name(base: str, taken: set[str]) -> str:
    if base not in taken:
        taken.add(base)
        return base
    i = 1
    while True:
        candidate = f"{base} ({i})"
        if candidate not in taken:
            taken.add(candidate)
            return candidate
        i += 1


def _apply_row_to_model(obj, row: Dict[str, str], overwrite_nonblank_only: bool):
    # Only fields that exist on the ORM model
    for col in DATA_COLUMNS:
        if col == "name":
            continue
        if not hasattr(obj, col):
            continue

        incoming = row.get(col, "")

        if col in ("str_score", "dex_score", "con_score", "int_score", "wis_score", "cha_score"):
            val = _to_int(incoming, getattr(obj, col, 10) or 10)
            setattr(obj, col, val)
            continue

        if col == "has_shield":
            setattr(obj, col, _boolish_to_int(incoming))
            continue

        val = _clean(incoming)
        if col == "cr":
            val = _normalize_cr(val)
        if overwrite_nonblank_only and val == "":
            continue
        setattr(obj, col, val)


def _plan_import(kind: str, cleaned_rows: List[Dict[str, str]], dup_mode: str):
    """
    Returns:
      to_insert, to_update, skipped_dupes, renamed
    """
    existing = _existing_names(kind)
    taken = set(existing)

    to_insert: List[Dict[str, str]] = []
    to_update: List[Dict[str, str]] = []
    skipped_dupes: List[str] = []
    renamed: List[Tuple[str, str]] = []

    # Plan actions
    for r in cleaned_rows:
        base_name = _clean(r.get("name", ""))
        if not base_name:
            continue

        if base_name in existing:
            if dup_mode == "Skip duplicates":
                skipped_dupes.append(base_name)
                continue
            if dup_mode.startswith("Rename"):
                new_name = _unique_name(base_name, taken)
                if new_name != base_name:
                    renamed.append((base_name, new_name))
                rr = dict(r)
                rr["name"] = new_name
                to_insert.append(rr)
                continue
            # Overwrite existing
            to_update.append(r)
        else:
            # Insert new, avoid within-file duplicates
            new_name = _unique_name(base_name, taken)
            rr = dict(r)
            rr["name"] = new_name
            if new_name != base_name:
                renamed.append((base_name, new_name))
            to_insert.append(rr)

    return to_insert, to_update, skipped_dupes, renamed


# --------------------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------------------

def page_bulk_import():
    st.header("Bulk Import (CSV)")

    with st.expander("CSV instructions (read this once)", expanded=True):
        st.markdown(
            """
**How this works**
- Your CSV can include **two optional targeting columns**:
  - `to_monsters`
  - `to_npcs`
- Values accepted as TRUE (case-insensitive): `TRUE`, `T`, `YES`, `Y`, `1`
- Leaving a target column **blank** means **do not** import that row into that list.
- If a row has **both** target columns blank/falsey, it is considered **Unassigned** and you will be prompted to choose where it goes.

**Examples**
- `to_monsters=TRUE`, `to_npcs=` → goes to Monsters only
- `to_monsters=`, `to_npcs=TRUE` → goes to NPCs only
- `to_monsters=TRUE`, `to_npcs=TRUE` → goes to both
- both blank → must be assigned during upload
"""
        )

    st.subheader("1) Download template")
    st.download_button(
        label="Download Bulk Import CSV template",
        data=_template_csv(),
        file_name="bulk_import_template.csv",
        mime="text/csv",
        width="stretch",
        key="dl_template_bulk_import",
    )

    st.subheader("2) Upload CSV")
    upload = st.file_uploader("Upload a filled template CSV", type=["csv"], key="upload_bulk")

    if not upload:
        st.info("Upload a CSV to preview/import.")
        return

    rows, warnings = _read_csv(upload)
    for w in warnings:
        st.warning(w)

    # Keep only rows with a name
    cleaned: List[Dict[str, str]] = []
    for r in rows:
        name = _clean(r.get("name", ""))
        if name:
            cleaned.append(r)

    if not cleaned:
        st.error("No rows with a non-empty name were found.")
        return

    st.caption(f"Rows with names found: {len(cleaned)}")

    # Determine assignment per row
    assigned_monsters: List[Dict[str, str]] = []
    assigned_npcs: List[Dict[str, str]] = []
    unassigned: List[Dict[str, str]] = []

    def _row_to_m(r: Dict[str, str]) -> bool:
        return _truthy(r.get("to_monsters", ""))

    def _row_to_n(r: Dict[str, str]) -> bool:
        return _truthy(r.get("to_npcs", ""))

    for r in cleaned:
        to_m = _row_to_m(r)
        to_n = _row_to_n(r)
        if not to_m and not to_n:
            unassigned.append(r)
        else:
            if to_m:
                assigned_monsters.append(r)
            if to_n:
                assigned_npcs.append(r)

    # If there are unassigned rows, allow per-row assignment
    # If there are unassigned rows, allow per-row assignment
    if unassigned:
        st.warning(
            f"{len(unassigned)} row(s) have no destination (both target columns blank/falsey). "
            "Assign them below."
        )

        # Build an editor-friendly list-of-dicts (NO pandas)
        def _row_label(r: Dict[str, str]) -> str:
            nm = _clean(r.get("name", ""))
            ct = _clean(r.get("creature_type", ""))
            cr = _normalize_cr(_clean(r.get("cr", "")))
            bits = [nm]
            if ct:
                bits.append(ct)
            if cr:
                bits.append(f"CR {cr}")
            return " — ".join(bits)

        editor_rows = []
        for idx, r in enumerate(unassigned):
            editor_rows.append(
                {
                    "row": idx + 1,
                    "item": _row_label(r),
                    "to_monsters": False,
                    "to_npcs": False,
                }
            )

        # Persist editor state across reruns
        if "bulk_import_unassigned_editor_rows" not in st.session_state:
            st.session_state["bulk_import_unassigned_editor_rows"] = editor_rows

        st.markdown("**Bulk assign helpers (affect only the unassigned rows):**")
        c1, c2, c3, c4 = st.columns(4)

        if c1.button("All → Monsters", width="stretch"):
            rows_state = st.session_state["bulk_import_unassigned_editor_rows"]
            for rr in rows_state:
                rr["to_monsters"] = True
                rr["to_npcs"] = False

        if c2.button("All → NPCs", width="stretch"):
            rows_state = st.session_state["bulk_import_unassigned_editor_rows"]
            for rr in rows_state:
                rr["to_monsters"] = False
                rr["to_npcs"] = True

        if c3.button("All → Both", width="stretch"):
            rows_state = st.session_state["bulk_import_unassigned_editor_rows"]
            for rr in rows_state:
                rr["to_monsters"] = True
                rr["to_npcs"] = True

        if c4.button("Clear All", width="stretch"):
            rows_state = st.session_state["bulk_import_unassigned_editor_rows"]
            for rr in rows_state:
                rr["to_monsters"] = False
                rr["to_npcs"] = False

        st.markdown("**Assign destinations per row:**")

        rows_state = st.session_state["bulk_import_unassigned_editor_rows"]

        for rr in rows_state:
            cols = st.columns([4, 1, 1])
            cols[0].markdown(f"**{rr['item']}**")
            rr["to_monsters"] = cols[1].checkbox(
                "Monsters",
                value=rr["to_monsters"],
                key=f"u_m_{rr['row']}"
            )
            rr["to_npcs"] = cols[2].checkbox(
                "NPCs",
                value=rr["to_npcs"],
                key=f"u_n_{rr['row']}"
            )

        still_unassigned = [
            rr for rr in rows_state
            if not rr["to_monsters"] and not rr["to_npcs"]
        ]
        if still_unassigned:
            st.error(
                f"{len(still_unassigned)} row(s) are still unassigned. "
                "Assign at least one destination per row to continue."
            )
            st.stop()

        for i, rr in enumerate(rows_state):
            unassigned[i]["to_monsters"] = "TRUE" if rr["to_monsters"] else ""
            unassigned[i]["to_npcs"] = "TRUE" if rr["to_npcs"] else ""

        # Now route the resolved rows into their destinations
        for r in unassigned:
            if _truthy(r.get("to_monsters", "")):
                assigned_monsters.append(r)
            if _truthy(r.get("to_npcs", "")):
                assigned_npcs.append(r)

    # Summary (after unassigned rows have been resolved)
    final_both = sum(
        1 for r in cleaned
        if _truthy(r.get("to_monsters", "")) and _truthy(r.get("to_npcs", ""))
    )
    st.subheader("3) Import settings")
    st.write(
        f"Targets — Monsters: **{len(assigned_monsters)}**, NPCs: **{len(assigned_npcs)}**, Both: **{final_both}**"
    )

    dup_mode = st.radio(
        "If an uploaded name already exists in the database…",
        ["Skip duplicates", "Rename duplicates (Name (1), (2) …)", "Overwrite existing"],
        index=0,
        key="dup_mode_bulk",
    )

    overwrite_nonblank_only = False
    if dup_mode == "Overwrite existing":
        overwrite_nonblank_only = st.checkbox(
            "Overwrite only non-blank fields (recommended)",
            value=True,
            key="overwrite_nonblank_bulk",
        )

    dry_run = st.checkbox("Dry run (preview only, no database changes)", value=True, key="dryrun_bulk")

    # Plan per table
    m_ins, m_upd, m_skip, m_ren = _plan_import("monster", assigned_monsters, dup_mode) if assigned_monsters else ([], [], [], [])
    n_ins, n_upd, n_skip, n_ren = _plan_import("npc", assigned_npcs, dup_mode) if assigned_npcs else ([], [], [], [])

    st.subheader("4) Preview")
    st.markdown("**Monsters**")
    st.write(f"Planned inserts: **{len(m_ins)}**")
    st.write(f"Planned overwrites: **{len(m_upd)}**" if dup_mode == "Overwrite existing" else "Planned overwrites: **0**")
    st.write(f"Duplicates skipped: **{len(m_skip)}**" if m_skip else "Duplicates skipped: **0**")

    st.markdown("**NPCs**")
    st.write(f"Planned inserts: **{len(n_ins)}**")
    st.write(f"Planned overwrites: **{len(n_upd)}**" if dup_mode == "Overwrite existing" else "Planned overwrites: **0**")
    st.write(f"Duplicates skipped: **{len(n_skip)}**" if n_skip else "Duplicates skipped: **0**")

    # Show rename info (limited)
    renamed_lines = []
    if m_ren:
        renamed_lines.append("MONSTERS renames:")
        renamed_lines.extend([f"{a} -> {b}" for a, b in m_ren][:100])
    if n_ren:
        renamed_lines.append("NPCS renames:")
        renamed_lines.extend([f"{a} -> {b}" for a, b in n_ren][:100])

    if renamed_lines:
        st.caption("Renamed to avoid duplicates:")
        st.code("\n".join(renamed_lines[:250]))

    # Preview table (first 50 combined)
    preview_rows = []
    for r in (m_ins + m_upd)[:25]:
        rr = dict(r)
        rr["_dest"] = "Monsters"
        preview_rows.append(rr)
    for r in (n_ins + n_upd)[:25]:
        rr = dict(r)
        rr["_dest"] = "NPCs"
        preview_rows.append(rr)

    if preview_rows:
        st.caption("Preview (first 50 rows):")
        lines = []
        for r in preview_rows[:50]:
            dest = (r.get("_dest") or "").strip()
            name = (r.get("name") or "").strip()
            cr = (r.get("cr") or "").strip()
            ctype = (r.get("creature_type") or "").strip()
            lines.append(f"{dest:8} | {name} | {ctype} | CR {cr}")
        st.code("\n".join(lines) if lines else "(no preview rows)")

    if dry_run:
        st.info("Dry run is ON — no database changes will be made.")
        return

    if not st.button("Apply Import", width="stretch", key="apply_import_bulk"):
        return

    inserted_m = updated_m = inserted_n = updated_n = 0

    with get_session() as s:
        # Monsters
        if assigned_monsters:
            ModelM = Monster
            if dup_mode == "Overwrite existing":
                for r in m_upd:
                    nm = _clean(r.get("name", ""))
                    obj = s.scalar(select(ModelM).where(ModelM.name == nm))
                    if not obj:
                        obj = ModelM(name=nm)
                        s.add(obj)
                        _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
                        inserted_m += 1
                    else:
                        _apply_row_to_model(obj, r, overwrite_nonblank_only=overwrite_nonblank_only)
                        updated_m += 1

            for r in m_ins:
                nm = _clean(r.get("name", ""))
                obj = ModelM(name=nm)
                _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
                s.add(obj)
                inserted_m += 1

        # NPCs
        if assigned_npcs:
            ModelN = NPC
            if dup_mode == "Overwrite existing":
                for r in n_upd:
                    nm = _clean(r.get("name", ""))
                    obj = s.scalar(select(ModelN).where(ModelN.name == nm))
                    if not obj:
                        obj = ModelN(name=nm)
                        s.add(obj)
                        _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
                        inserted_n += 1
                    else:
                        _apply_row_to_model(obj, r, overwrite_nonblank_only=overwrite_nonblank_only)
                        updated_n += 1

            for r in n_ins:
                nm = _clean(r.get("name", ""))
                obj = ModelN(name=nm)
                _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
                s.add(obj)
                inserted_n += 1

        s.commit()

    st.success(
        "Import complete. "
        f"Monsters — Inserted: {inserted_m}, Updated: {updated_m}, Skipped: {len(m_skip)}. "
        f"NPCs — Inserted: {inserted_n}, Updated: {updated_n}, Skipped: {len(n_skip)}."
    )
