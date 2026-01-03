from __future__ import annotations

import csv
from dataclasses import asdict
from io import StringIO
from typing import Dict, List, Tuple

import streamlit as st
from sqlalchemy import select

from db import get_session, Monster, NPC


# Keep columns "one field per cell" and match DB fields closely.
TEMPLATE_COLUMNS: List[str] = [
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


def _boolish_to_int(v: str) -> int:
    s = (v or "").strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return 1
    if s in ("0", "false", "f", "no", "n", "off", ""):
        return 0
    # If someone types weird stuff, treat non-empty as true.
    return 1


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


def _template_csv() -> str:
    buf = StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(TEMPLATE_COLUMNS)
    # One empty starter row (makes it easy to tab through)
    w.writerow(["" for _ in TEMPLATE_COLUMNS])
    return buf.getvalue()


def _read_csv(upload) -> Tuple[List[Dict[str, str]], List[str]]:
    raw = upload.getvalue().decode("utf-8-sig", errors="replace")
    rdr = csv.DictReader(StringIO(raw))
    if not rdr.fieldnames:
        return [], ["CSV has no headers. Download the template and try again."]

    # Normalize header names (case/whitespace)
    field_map = {fn: fn.strip() for fn in rdr.fieldnames}
    rows: List[Dict[str, str]] = []

    missing = [c for c in TEMPLATE_COLUMNS if c not in field_map.values()]
    # Name is the only *required* column for import; others can be absent but template expects them.
    if "name" not in field_map.values():
        return [], ["CSV must include a 'name' column. Use the template."]

    # Accept extra columns; ignore them.
    for r in rdr:
        # Normalize keys
        rr = {}
        for k, v in r.items():
            kk = (k or "").strip()
            if kk:
                rr[kk] = v
        rows.append(rr)

    warnings = []
    if missing:
        warnings.append(f"Template columns missing (will be treated as blank): {', '.join(missing)}")
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
    for col in TEMPLATE_COLUMNS:
        if col == "name":
            continue
        if not hasattr(obj, col):
            continue
        incoming = row.get(col, "")
        if col in ("str_score","dex_score","con_score","int_score","wis_score","cha_score"):
            val = _to_int(incoming, getattr(obj, col, 10) or 10)
            setattr(obj, col, val)
            continue
        if col == "has_shield":
            setattr(obj, col, _boolish_to_int(incoming))
            continue

        val = _clean(incoming)
        if overwrite_nonblank_only and val == "":
            continue
        setattr(obj, col, val)


def page_bulk_import():
    st.header("Bulk Import (CSV)")

    kind_label = st.selectbox("Import target", ["Monsters", "NPCs"], index=0)
    kind = "monster" if kind_label == "Monsters" else "npc"

    st.subheader("1) Download template")
    st.download_button(
        label=f"Download {kind_label} CSV template",
        data=_template_csv(),
        file_name=f"{kind_label.lower()}_template.csv",
        mime="text/csv",
        use_container_width=True,
        key=f"dl_template_{kind}",
    )

    st.subheader("2) Upload CSV")
    upload = st.file_uploader("Upload a filled template CSV", type=["csv"], key=f"upload_{kind}")

    if not upload:
        st.info("Upload a CSV to preview/import.")
        return

    rows, warnings = _read_csv(upload)
    for w in warnings:
        st.warning(w)

    # Clean rows: keep only those with a name
    cleaned = []
    for r in rows:
        name = _clean(r.get("name", ""))
        if name:
            cleaned.append(r)

    if not cleaned:
        st.error("No rows with a non-empty name were found.")
        return

    st.caption(f"Rows with names found: {len(cleaned)}")

    dup_mode = st.radio(
        "If an uploaded name already exists in the database…",
        ["Skip duplicates", "Rename duplicates (Name (1), (2) …)", "Overwrite existing"],
        index=0,
        key=f"dup_mode_{kind}",
    )

    overwrite_nonblank_only = False
    if dup_mode == "Overwrite existing":
        overwrite_nonblank_only = st.checkbox(
            "Overwrite only non-blank fields (recommended)",
            value=True,
            key=f"overwrite_nonblank_{kind}",
        )

    dry_run = st.checkbox("Dry run (preview only, no database changes)", value=True, key=f"dryrun_{kind}")

    # IMPORTANT: Choose the target table first, then check duplicates only within that table.
    Model = _model_for(kind)
    existing = _existing_names(Model)
    taken = set(existing)

    to_insert = []
    to_update = []
    skipped_dupes = []
    renamed = []

    # Plan actions
    for r in cleaned:
        base_name = _clean(r.get("name",""))
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
            # Insert new, but still avoid within-file duplicates
            new_name = _unique_name(base_name, taken)
            rr = dict(r)
            rr["name"] = new_name
            if new_name != base_name:
                renamed.append((base_name, new_name))
            to_insert.append(rr)

    st.subheader("3) Preview")
    st.write(f"Planned inserts: **{len(to_insert)}**")
    st.write(f"Planned overwrites: **{len(to_update)}**" if dup_mode == "Overwrite existing" else "Planned overwrites: **0**")
    st.write(f"Duplicates skipped: **{len(skipped_dupes)}**" if skipped_dupes else "Duplicates skipped: **0**")
    if skipped_dupes:
        st.caption("Skipped duplicates:")
        st.code(", ".join(skipped_dupes))

    if renamed:
        st.caption("Renamed to avoid duplicates:")
        st.code("\n".join([f"{a} -> {b}" for a,b in renamed][:200]))

    # Show a small preview table (first 50)
    preview = (to_insert + to_update)[:50]
    if preview:
        st.dataframe(preview, use_container_width=True, hide_index=True)

    if dry_run:
        st.info("Dry run is ON — no database changes will be made.")
        return

    if not st.button("Apply Import", use_container_width=True, key=f"apply_import_{kind}"):
        return

    # Execute
    inserted = 0
    updated = 0

    with get_session() as s:
        if dup_mode == "Overwrite existing":
            for r in to_update:
                nm = _clean(r.get("name",""))
                obj = s.scalar(select(Model).where(Model.name == nm))
                if not obj:
                    # If it disappeared, insert it instead
                    obj = Model(name=nm)
                    s.add(obj)
                    _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
                    inserted += 1
                else:
                    _apply_row_to_model(obj, r, overwrite_nonblank_only=overwrite_nonblank_only)
                    updated += 1

        for r in to_insert:
            nm = _clean(r.get("name",""))
            obj = Model(name=nm)
            _apply_row_to_model(obj, r, overwrite_nonblank_only=False)
            s.add(obj)
            inserted += 1

        s.commit()

    st.success(f"Import complete. Inserted: {inserted}. Updated: {updated}. Skipped duplicates: {len(skipped_dupes)}.")
