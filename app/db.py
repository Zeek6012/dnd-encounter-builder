from __future__ import annotations

from datetime import datetime
from typing import Optional
import os
import sqlite3

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DB_PATH = r"data\encounter_builder.sqlite3"

def _get_database_url() -> str:
    """
    Priority:
      1) Streamlit secrets: st.secrets["database"]["url"]
      2) Env var: DATABASE_URL / SQLALCHEMY_DATABASE_URL
      3) Local SQLite file
    """
    # Streamlit secrets (used on Streamlit Community Cloud)
    try:
        import streamlit as st  # type: ignore
        if "database" in st.secrets and "url" in st.secrets["database"]:
            return str(st.secrets["database"]["url"])
    except Exception:
        pass

    # Environment variable fallback (useful for other hosts)
    env_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL")
    if env_url:
        return env_url

    # Local dev fallback
    return f"sqlite:///{DB_PATH}"

DATABASE_URL = _get_database_url()
ENGINE = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class Monster(Base):
    __tablename__ = "monsters"
    __table_args__ = (UniqueConstraint("name", name="uq_monster_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    creature_type: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[str] = mapped_column(String(50), default="")
    alignment: Mapped[str] = mapped_column(String(80), default="")

    ac: Mapped[str] = mapped_column(String(40), default="")
    has_shield: Mapped[int] = mapped_column(Integer, default=0)

    hp: Mapped[str] = mapped_column(String(80), default="")
    speed: Mapped[str] = mapped_column(String(120), default="")

    str_score: Mapped[int] = mapped_column(Integer, default=10)
    dex_score: Mapped[int] = mapped_column(Integer, default=10)
    con_score: Mapped[int] = mapped_column(Integer, default=10)
    int_score: Mapped[int] = mapped_column(Integer, default=10)
    wis_score: Mapped[int] = mapped_column(Integer, default=10)
    cha_score: Mapped[int] = mapped_column(Integer, default=10)

    # Legacy compat: older DBs have monsters.saves NOT NULL
    saves: Mapped[str] = mapped_column(Text, default="", nullable=False)

    save_str: Mapped[str] = mapped_column(String(10), default="")
    save_dex: Mapped[str] = mapped_column(String(10), default="")
    save_con: Mapped[str] = mapped_column(String(10), default="")
    save_int: Mapped[str] = mapped_column(String(10), default="")
    save_wis: Mapped[str] = mapped_column(String(10), default="")
    save_cha: Mapped[str] = mapped_column(String(10), default="")

    skills: Mapped[str] = mapped_column(Text, default="")
    damage_vulnerabilities: Mapped[str] = mapped_column(Text, default="")
    damage_resistances: Mapped[str] = mapped_column(Text, default="")
    damage_immunities: Mapped[str] = mapped_column(Text, default="")
    condition_immunities: Mapped[str] = mapped_column(Text, default="")
    senses: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[str] = mapped_column(Text, default="")
    cr: Mapped[str] = mapped_column(String(40), default="")
    pb: Mapped[str] = mapped_column(String(40), default="")

    traits: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[str] = mapped_column(Text, default="")
    bonus_actions: Mapped[str] = mapped_column(Text, default="")
    reactions: Mapped[str] = mapped_column(Text, default="")
    legendary_actions: Mapped[str] = mapped_column(Text, default="")
    lair_actions: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class NPC(Base):
    __tablename__ = "npcs"
    __table_args__ = (UniqueConstraint("name", name="uq_npc_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    creature_type: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[str] = mapped_column(String(50), default="")
    alignment: Mapped[str] = mapped_column(String(80), default="")

    ac: Mapped[str] = mapped_column(String(40), default="")
    has_shield: Mapped[int] = mapped_column(Integer, default=0)

    hp: Mapped[str] = mapped_column(String(80), default="")
    speed: Mapped[str] = mapped_column(String(120), default="")

    str_score: Mapped[int] = mapped_column(Integer, default=10)
    dex_score: Mapped[int] = mapped_column(Integer, default=10)
    con_score: Mapped[int] = mapped_column(Integer, default=10)
    int_score: Mapped[int] = mapped_column(Integer, default=10)
    wis_score: Mapped[int] = mapped_column(Integer, default=10)
    cha_score: Mapped[int] = mapped_column(Integer, default=10)

    saves: Mapped[str] = mapped_column(Text, default="", nullable=False)

    save_str: Mapped[str] = mapped_column(String(10), default="")
    save_dex: Mapped[str] = mapped_column(String(10), default="")
    save_con: Mapped[str] = mapped_column(String(10), default="")
    save_int: Mapped[str] = mapped_column(String(10), default="")
    save_wis: Mapped[str] = mapped_column(String(10), default="")
    save_cha: Mapped[str] = mapped_column(String(10), default="")

    skills: Mapped[str] = mapped_column(Text, default="")
    damage_vulnerabilities: Mapped[str] = mapped_column(Text, default="")
    damage_resistances: Mapped[str] = mapped_column(Text, default="")
    damage_immunities: Mapped[str] = mapped_column(Text, default="")
    condition_immunities: Mapped[str] = mapped_column(Text, default="")
    senses: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[str] = mapped_column(Text, default="")
    cr: Mapped[str] = mapped_column(String(40), default="")
    pb: Mapped[str] = mapped_column(String(40), default="")

    traits: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[str] = mapped_column(Text, default="")
    bonus_actions: Mapped[str] = mapped_column(Text, default="")
    reactions: Mapped[str] = mapped_column(Text, default="")
    legendary_actions: Mapped[str] = mapped_column(Text, default="")
    lair_actions: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("name", name="uq_campaign_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    encounters: Mapped[list["Encounter"]] = relationship(back_populates="campaign")


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("campaigns.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="encounters")
    entries: Mapped[list["EncounterEntry"]] = relationship(
        back_populates="encounter", cascade="all, delete-orphan"
    )

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class EncounterEntry(Base):
    __tablename__ = "encounter_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounters.id"), nullable=False)

    kind: Mapped[str] = mapped_column(String(20), default="monster")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    ac: Mapped[str] = mapped_column(String(40), default="")
    has_shield: Mapped[int] = mapped_column(Integer, default=0)

    hp: Mapped[str] = mapped_column(String(80), default="")
    speed: Mapped[str] = mapped_column(String(120), default="")
    senses: Mapped[str] = mapped_column(Text, default="")

    str_score: Mapped[int] = mapped_column(Integer, default=10)
    dex_score: Mapped[int] = mapped_column(Integer, default=10)
    con_score: Mapped[int] = mapped_column(Integer, default=10)
    int_score: Mapped[int] = mapped_column(Integer, default=10)
    wis_score: Mapped[int] = mapped_column(Integer, default=10)
    cha_score: Mapped[int] = mapped_column(Integer, default=10)

    save_str: Mapped[str] = mapped_column(String(10), default="")
    save_dex: Mapped[str] = mapped_column(String(10), default="")
    save_con: Mapped[str] = mapped_column(String(10), default="")
    save_int: Mapped[str] = mapped_column(String(10), default="")
    save_wis: Mapped[str] = mapped_column(String(10), default="")
    save_cha: Mapped[str] = mapped_column(String(10), default="")

    traits: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[str] = mapped_column(Text, default="")
    bonus_actions: Mapped[str] = mapped_column(Text, default="")
    reactions: Mapped[str] = mapped_column(Text, default="")
    legendary_actions: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    encounter: Mapped["Encounter"] = relationship(back_populates="entries")


def get_session():
    return SessionLocal()


def init_db() -> None:
    # SQLite: ensure data folder + run lightweight migrations
    if ENGINE.url.get_backend_name() == "sqlite":
        os.makedirs("data", exist_ok=True)
        Base.metadata.create_all(ENGINE)
        migrate_db()
        return

    # Postgres (Supabase): just create tables (no sqlite PRAGMA migrations)
    Base.metadata.create_all(ENGINE)


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    return {r[0] for r in rows}


def _table_cols(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table});")
    return {row[1] for row in cur.fetchall()}


def _add_col(conn: sqlite3.Connection, table: str, col: str, decl: str):
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl};")


def migrate_db() -> None:
    # This migration logic is SQLite-specific (PRAGMA/ALTER). Skip on Postgres.
    if ENGINE.url.get_backend_name() != "sqlite":
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        tables = _existing_tables(conn)

        for table in ["monsters", "npcs"]:
            if table in tables:
                cols = _table_cols(conn, table)

                if "has_shield" not in cols:
                    _add_col(conn, table, "has_shield", "INTEGER DEFAULT 0")

                if "saves" not in cols:
                    _add_col(conn, table, "saves", "TEXT NOT NULL DEFAULT ''")

                for c in ["save_str", "save_dex", "save_con", "save_int", "save_wis", "save_cha"]:
                    if c not in cols:
                        _add_col(conn, table, c, "VARCHAR(10) DEFAULT ''")

        if "encounter_entries" in tables:
            cols = _table_cols(conn, "encounter_entries")
            if "has_shield" not in cols:
                _add_col(conn, "encounter_entries", "has_shield", "INTEGER DEFAULT 0")

        conn.commit()
    finally:
        conn.close()
