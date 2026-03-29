import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# FantaTennis — User App
# Robust version with:
# - fallback from public/latest to raw for md_players and team_rosters
# - column auto-detection
# - diagnostics page
# ------------------------------------------------------------

st.set_page_config(page_title="FantaTennis", layout="wide")

BASE_DIR = Path(".")
PUBLIC_DIR = Path(os.getenv("FT_PUBLIC_DIR", "data/public/latest"))
RAW_DIR = Path(os.getenv("FT_RAW_DIR", "data/raw"))
MANIFEST_NAME = os.getenv("FT_MANIFEST_NAME", "manifest.json")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fmt_dt(s: str) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(str(s).replace("Z", "")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(s)


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in out.columns
    ]
    return out


@st.cache_data(ttl=60)
def read_csv_safe(path_str: str) -> Optional[pd.DataFrame]:
    path = Path(path_str)
    if not path.exists():
        return None

    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
    seps = [",", ";"]
    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep)
                if df.shape[1] > 0:
                    return normalize_cols(df)
            except Exception:
                pass
    return None


@st.cache_data(ttl=60)
def read_manifest(public_dir: str) -> dict:
    path = Path(public_dir) / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def candidate_paths(filename: str) -> List[Path]:
    paths = []
    if filename in {"md_players.csv", "team_rosters.csv"}:
        paths.append(PUBLIC_DIR / filename)
        paths.append(RAW_DIR / filename)
    else:
        paths.append(PUBLIC_DIR / filename)
    return paths


def read_with_fallback(filename: str) -> Tuple[Optional[pd.DataFrame], Optional[Path]]:
    for p in candidate_paths(filename):
        df = read_csv_safe(str(p))
        if df is not None:
            return df, p
    return None, None


def detect_player_name_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["full_name", "player", "name"]:
        if c in df.columns:
            return c
    return None


def detect_team_cols(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    team_id_col = "team_id" if "team_id" in df.columns else None
    team_name_col = "team_name" if "team_name" in df.columns else None
    player_col = "id_player" if "id_player" in df.columns else None

    if team_id_col is None:
        for c in df.columns:
            if "team" in c and "id" in c:
                team_id_col = c
                break

    if team_name_col is None:
        for c in df.columns:
            if "team" in c and "name" in c:
                team_name_col = c
                break

    if player_col is None:
        for c in df.columns:
            if "player" in c and "id" in c:
                player_col = c
                break

    return team_id_col, team_name_col, player_col


def require_df(df: Optional[pd.DataFrame], msg: str):
    if df is None:
        st.error(msg)
        st.stop()


# ------------------------------------------------------------
# Load files
# ------------------------------------------------------------
manifest = read_manifest(str(PUBLIC_DIR))
updated_at = manifest.get("updated_at") or manifest.get("published_at") or ""
version = manifest.get("version") or manifest.get("snapshot_id") or ""

df_standings, standings_src = read_with_fallback("standings.csv")
df_team_points, team_points_src = read_with_fallback("team_points.csv")
df_team_rosters, team_rosters_src = read_with_fallback("team_rosters.csv")
df_player_points, player_points_src = read_with_fallback("player_points.csv")
df_md_players, md_players_src = read_with_fallback("md_players.csv")

st.sidebar.title("FantaTennis")
st.sidebar.caption("User App")
st.sidebar.write(f"**Public dir:** `{PUBLIC_DIR}`")
st.sidebar.write(f"**Raw dir:** `{RAW_DIR}`")
st.sidebar.write(f"**Update:** {fmt_dt(updated_at)}")
if version:
    st.sidebar.write(f"**Version:** `{version}`")

page = st.sidebar.radio(
    "Navigate",
    ["Home", "Standings", "Teams", "Players", "Diagnostics"],
    index=0
)


# ------------------------------------------------------------
# Pages
# ------------------------------------------------------------
if page == "Home":
    st.title("FantaTennis — Home")
    st.caption("Read-only app. For master data, fallback from public/latest to raw is enabled.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Manifest update", fmt_dt(updated_at))
    c2.metric("Version", version or "—")
    c3.metric("Team rosters source", str(team_rosters_src) if team_rosters_src else "missing")

    st.divider()
    st.subheader("Available datasets")
    status = pd.DataFrame([
        {"file": "standings.csv", "source": str(standings_src) if standings_src else "missing"},
        {"file": "team_points.csv", "source": str(team_points_src) if team_points_src else "missing"},
        {"file": "team_rosters.csv", "source": str(team_rosters_src) if team_rosters_src else "missing"},
        {"file": "player_points.csv", "source": str(player_points_src) if player_points_src else "missing"},
        {"file": "md_players.csv", "source": str(md_players_src) if md_players_src else "missing"},
    ])
    st.dataframe(status, use_container_width=True, hide_index=True)

    if df_standings is not None and len(df_standings) > 0:
        st.subheader("Top standings")
        st.dataframe(df_standings.head(10), use_container_width=True, hide_index=True)
    else:
        st.info("standings.csv non disponibile ancora. Teams e Players possono comunque funzionare.")

elif page == "Standings":
    st.title("Classifica Lega")
    require_df(df_standings, "Missing standings.csv in data/public/latest/")
    if "date" in df_standings.columns:
        dates = sorted(df_standings["date"].dropna().astype(str).unique().tolist())
        sel = st.selectbox("Date", dates, index=len(dates)-1 if dates else 0)
        view = df_standings[df_standings["date"].astype(str) == sel].copy()
    else:
        view = df_standings.copy()

    sort_col = "rank" if "rank" in view.columns else None
    if sort_col:
        view = view.sort_values(sort_col)

    st.dataframe(view, use_container_width=True, hide_index=True)

elif page == "Teams":
    st.title("Teams")

    require_df(
        df_team_rosters,
        "team_rosters.csv non trovato né in data/public/latest/ né in data/raw/."
    )
    require_df(
        df_md_players,
        "md_players.csv non trovato né in data/public/latest/ né in data/raw/."
    )

    team_id_col, team_name_col, player_col = detect_team_cols(df_team_rosters)
    if not team_id_col or not player_col:
        st.error(
            "team_rosters.csv non ha le colonne minime richieste. "
            "Servono almeno team_id e id_player."
        )
        st.write("Colonne trovate:", df_team_rosters.columns.tolist())
        st.stop()

    name_col = detect_player_name_col(df_md_players)
    if not name_col:
        st.error(
            "md_players.csv non ha una colonna nome giocatore valida. "
            "Attese: full_name oppure player oppure name."
        )
        st.write("Colonne trovate:", df_md_players.columns.tolist())
        st.stop()

    md = df_md_players.copy()
    if "id_player" not in md.columns:
        st.error("md_players.csv deve contenere la colonna id_player.")
        st.stop()

    roster = df_team_rosters.copy()
    roster[player_col] = roster[player_col].astype(str).str.strip()
    md["id_player"] = md["id_player"].astype(str).str.strip()

    merged = roster.merge(
        md,
        left_on=player_col,
        right_on="id_player",
        how="left",
        suffixes=("", "_md")
    )

    teams_df = merged[[team_id_col] + ([team_name_col] if team_name_col else [])].drop_duplicates()
    if team_name_col:
        teams_df["label"] = teams_df[team_name_col].astype(str) + " (" + teams_df[team_id_col].astype(str) + ")"
        labels = teams_df["label"].tolist()
        selected_label = st.selectbox("Team", labels)
        selected_row = teams_df.loc[teams_df["label"] == selected_label].iloc[0]
        selected_team_id = selected_row[team_id_col]
    else:
        team_ids = sorted(merged[team_id_col].dropna().astype(str).unique().tolist())
        selected_team_id = st.selectbox("Team ID", team_ids)

    team_view = merged[merged[team_id_col].astype(str) == str(selected_team_id)].copy()

    show_cols = []
    for c in [team_id_col, team_name_col, player_col, "slot", "price", "tier", "full_name", "player", "name"]:
        if c and c in team_view.columns and c not in show_cols:
            show_cols.append(c)
    if not show_cols:
        show_cols = team_view.columns.tolist()

    st.caption(f"Source roster: `{team_rosters_src}`")
    st.dataframe(team_view[show_cols], use_container_width=True, hide_index=True)

    missing_names = team_view["id_player"].isna().sum() if "id_player" in team_view.columns else 0
    if missing_names:
        st.warning(f"{missing_names} players in this roster did not match md_players by id_player.")

elif page == "Players":
    st.title("Players")
    require_df(
        df_md_players,
        "md_players.csv non trovato né in data/public/latest/ né in data/raw/."
    )

    md = df_md_players.copy()
    require_df(md, "md_players.csv missing")
    if "id_player" not in md.columns:
        st.error("md_players.csv deve contenere id_player.")
        st.stop()

    name_col = detect_player_name_col(md)
    if not name_col:
        st.error("md_players.csv deve contenere full_name o player o name.")
        st.stop()

    if df_player_points is not None and "id_player" in df_player_points.columns:
        merged = df_player_points.merge(md, on="id_player", how="left", suffixes=("", "_md"))
    else:
        merged = md.copy()

    q = st.text_input("Search player", "")
    view = merged.copy()
    if q:
        view = view[view[name_col].fillna("").astype(str).str.contains(q, case=False)]

    if "date" in view.columns:
        dates = sorted(view["date"].dropna().astype(str).unique().tolist())
        if dates:
            sel = st.selectbox("Date", dates, index=len(dates)-1)
            view = view[view["date"].astype(str) == sel].copy()

    if "points" in view.columns:
        view = view.sort_values("points", ascending=False)

    show_cols = []
    for c in ["id_player", "full_name", "player", "name", "points", "cumulative_points", "tournament"]:
        if c in view.columns and c not in show_cols:
            show_cols.append(c)
    if not show_cols:
        show_cols = view.columns.tolist()

    st.caption(f"Source md_players: `{md_players_src}`")
    if player_points_src:
        st.caption(f"Source player_points: `{player_points_src}`")
    st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

else:
    st.title("Diagnostics")

    rows = []
    for fname in ["standings.csv", "team_points.csv", "team_rosters.csv", "player_points.csv", "md_players.csv", MANIFEST_NAME]:
        srcs = candidate_paths(fname) if fname != MANIFEST_NAME else [PUBLIC_DIR / MANIFEST_NAME]
        for p in srcs:
            rows.append({
                "file": fname,
                "path": str(p),
                "exists": p.exists(),
                "size_bytes": int(p.stat().st_size) if p.exists() else 0,
            })

    st.subheader("File presence")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Detected schemas")
    schema_rows = []
    for label, df in [
        ("team_rosters", df_team_rosters),
        ("md_players", df_md_players),
        ("player_points", df_player_points),
        ("standings", df_standings),
    ]:
        schema_rows.append({
            "dataset": label,
            "loaded": df is not None,
            "columns": ", ".join(df.columns.tolist()) if df is not None else "",
            "rows": int(len(df)) if df is not None else 0,
        })
    st.dataframe(pd.DataFrame(schema_rows), use_container_width=True, hide_index=True)

    if df_team_rosters is not None:
        st.markdown("### team_rosters preview")
        st.dataframe(df_team_rosters.head(20), use_container_width=True, hide_index=True)

    if df_md_players is not None:
        st.markdown("### md_players preview")
        st.dataframe(df_md_players.head(20), use_container_width=True, hide_index=True)

    if manifest:
        st.markdown("### manifest.json")
        st.json(manifest)
