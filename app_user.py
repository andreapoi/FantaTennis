import os
import json
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

# -----------------------------
# FantaTennis - User App (App2)
# Read-only app: consumes only data/public/latest/*
# -----------------------------

DATA_PUBLIC_DIR = os.getenv("FT_PUBLIC_DIR", "data/public/latest")
MANIFEST_NAME = os.getenv("FT_MANIFEST_NAME", "manifest.json")

st.set_page_config(page_title="FantaTennis", layout="wide")

@st.cache_data(ttl=60)
def _read_manifest(public_dir: str) -> dict:
    path = os.path.join(public_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data(ttl=60)
def _read_csv(public_dir: str, filename: str) -> Optional[pd.DataFrame]:
    path = os.path.join(public_dir, filename)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)

def _fmt_dt(s: str) -> str:
    if not s:
        return "—"
    try:
        # accept iso or timestamp-like strings
        return datetime.fromisoformat(s.replace("Z", "")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s

def _require(df: Optional[pd.DataFrame], name: str):
    if df is None:
        st.error(f"Missing required public file: {name} in {DATA_PUBLIC_DIR}")
        st.stop()

manifest = _read_manifest(DATA_PUBLIC_DIR)
updated_at = manifest.get("updated_at") or manifest.get("published_at") or manifest.get("run_timestamp") or ""
version = manifest.get("version") or manifest.get("snapshot_id") or ""

st.sidebar.title("FantaTennis")
st.sidebar.caption("Read-only User App")
st.sidebar.write(f"**Data:** {_fmt_dt(updated_at)}")
if version:
    st.sidebar.write(f"**Version:** `{version}`")

page = st.sidebar.radio(
    "Navigate",
    ["Home", "Standings", "Teams", "Players", "Regolamento / Notes"],
    index=0
)

# Public contract (expected)
df_standings = _read_csv(DATA_PUBLIC_DIR, "standings.csv")
df_team_points = _read_csv(DATA_PUBLIC_DIR, "team_points.csv")
df_team_rosters = _read_csv(DATA_PUBLIC_DIR, "team_rosters.csv")
df_player_points = _read_csv(DATA_PUBLIC_DIR, "player_points.csv")
df_md_players = _read_csv(DATA_PUBLIC_DIR, "md_players.csv")

# Graceful: not all files must exist for MVP; enforce on pages where needed.

if page == "Home":
    st.title("FantaTennis — Home")
    st.caption("Questa app legge **solo** i dataset pubblicati dal backend in `data/public/latest/`.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Last update", _fmt_dt(updated_at))
    with c2:
        st.metric("Version", version or "—")
    with c3:
        st.metric("Public dir", DATA_PUBLIC_DIR)

    st.divider()
    st.subheader("Quick view")
    if df_standings is not None and len(df_standings) > 0:
        st.write("**Top 10**")
        st.dataframe(df_standings.head(10), use_container_width=True, hide_index=True)
    else:
        st.info("Standings not available yet. Publish from Admin app.")

    if manifest:
        with st.expander("Manifest"):
            st.json(manifest)

elif page == "Standings":
    st.title("Classifica Lega")
    _require(df_standings, "standings.csv")
    # Optional filter by date if present
    if "date" in df_standings.columns:
        dates = sorted(df_standings["date"].dropna().unique().tolist())
        sel = st.selectbox("Date", dates, index=len(dates)-1 if dates else 0)
        view = df_standings[df_standings["date"] == sel].copy()
    else:
        view = df_standings.copy()

    st.dataframe(view, use_container_width=True, hide_index=True)

    if df_team_points is not None:
        st.divider()
        st.subheader("Punti Team (raw)")
        st.dataframe(df_team_points, use_container_width=True, hide_index=True)

elif page == "Teams":
    st.title("Teams")
    _require(df_team_rosters, "team_rosters.csv")
    _require(df_md_players, "md_players.csv")

    # Expected columns: team_id, id_player (and optionally team_name, slot)
    # Try to provide best UX even if names differ slightly.
    team_col = "team_id" if "team_id" in df_team_rosters.columns else df_team_rosters.columns[0]
    player_col = "id_player" if "id_player" in df_team_rosters.columns else df_team_rosters.columns[1]

    teams = sorted(df_team_rosters[team_col].dropna().unique().tolist())
    sel_team = st.selectbox("Team", teams)

    roster = df_team_rosters[df_team_rosters[team_col] == sel_team].copy()
    roster = roster.merge(df_md_players, left_on=player_col, right_on="id_player", how="left", suffixes=("", "_p"))

    # Show roster
    show_cols = []
    for c in ["slot", "id_player", "full_name", "name", "price", "tier"]:
        if c in roster.columns:
            show_cols.append(c)
    if not show_cols:
        show_cols = roster.columns.tolist()

    st.subheader("Rosa")
    st.dataframe(roster[show_cols], use_container_width=True, hide_index=True)

    # Team points time series table if available
    if df_team_points is not None:
        st.divider()
        st.subheader("Punti nel tempo")
        if "team_id" in df_team_points.columns and "date" in df_team_points.columns:
            tp = df_team_points[df_team_points["team_id"] == sel_team].copy()
            st.dataframe(tp.sort_values("date"), use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_team_points, use_container_width=True, hide_index=True)

elif page == "Players":
    st.title("Players")
    _require(df_player_points, "player_points.csv")
    _require(df_md_players, "md_players.csv")

    merged = df_player_points.merge(df_md_players, on="id_player", how="left", suffixes=("", "_p"))

    # Search/filter
    name_col = "full_name" if "full_name" in merged.columns else ("name" if "name" in merged.columns else None)
    q = st.text_input("Search player", "")
    view = merged.copy()
    if q and name_col:
        view = view[view[name_col].fillna("").str.contains(q, case=False)]

    # date filter
    if "date" in view.columns:
        dates = sorted(view["date"].dropna().unique().tolist())
        sel = st.selectbox("Date", dates, index=len(dates)-1 if dates else 0)
        view = view[view["date"] == sel].copy()

    # sort
    sort_col = "points" if "points" in view.columns else None
    if sort_col:
        view = view.sort_values(sort_col, ascending=False)

    show_cols = []
    for c in ["id_player", "full_name", "name", "points", "cumulative_points", "tournament", "round"]:
        if c in view.columns:
            show_cols.append(c)
    if not show_cols:
        show_cols = view.columns.tolist()

    st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

    # Player detail
    st.divider()
    st.subheader("Player detail")
    players = sorted(df_md_players["id_player"].dropna().unique().tolist())
    sel_id = st.selectbox("id_player", players)
    p = df_md_players[df_md_players["id_player"] == sel_id].iloc[0].to_dict()
    c1, c2 = st.columns([2, 3])
    with c1:
        st.json(p)
    with c2:
        if "id_player" in df_player_points.columns:
            hist = df_player_points[df_player_points["id_player"] == sel_id].copy()
            if "date" in hist.columns:
                hist = hist.sort_values("date")
            st.dataframe(hist, use_container_width=True, hide_index=True)

else:
    st.title("Regolamento / Notes")
    st.write("Questa sezione può mostrare regole e note pubblicate dal backend.")
    rules = _read_csv(DATA_PUBLIC_DIR, "rules_public.csv")
    if rules is not None:
        st.dataframe(rules, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun file `rules_public.csv` trovato. (Opzionale)")
