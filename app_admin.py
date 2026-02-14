
# app_admin.py - FantaTennis Backend (App1)
import streamlit as st
import pandas as pd
from datetime import datetime

from ft_backend.config import RepoPaths
from ft_backend.io.github_store import GitHubConfig, GitHubStore
from ft_backend.normalize.results import normalize_results_upload
from ft_backend.compute.build_marts import add_fantapoints, player_standings_season, team_standings_season
from ft_backend.publish.snapshot import publish_snapshot

st.set_page_config(page_title="FantaTennis Admin Backend", layout="wide")

paths = RepoPaths()

# --- GitHub store (repo-backed persistence) ---
cfg = GitHubConfig(
    token=st.secrets["github"]["token"],
    repo=st.secrets["github"]["repo"],
    branch=st.secrets["github"]["branch"],
)
store = GitHubStore(cfg)

def now_tag():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

st.title("FantaTennis — App1 Backend/Admin")

tab_upload, tab_validate, tab_compute, tab_publish = st.tabs(["1) Upload", "2) Validate", "3) Compute", "4) Publish"])

# Load reference datasets
with st.sidebar:
    st.subheader("Reference data")
    players_df = store.read_csv(paths.players_csv)
    multipliers_df = store.read_csv(paths.multipliers_csv)
    teams = store.read_json(paths.teams_json, default=[])
    st.caption(f"players.csv rows: {len(players_df)}")
    st.caption(f"ranking_multipliers.csv rows: {len(multipliers_df)}")
    st.caption(f"teams.json teams: {len(teams)}")

# Session state holders
if "stage_results" not in st.session_state:
    st.session_state.stage_results = pd.DataFrame()
if "processed_results" not in st.session_state:
    st.session_state.processed_results = pd.DataFrame()
if "processed_players" not in st.session_state:
    st.session_state.processed_players = pd.DataFrame()
if "processed_teams" not in st.session_state:
    st.session_state.processed_teams = pd.DataFrame()
if "last_stage_path" not in st.session_state:
    st.session_state.last_stage_path = None

with tab_upload:
    st.header("1) Upload risultati")
    col1, col2, col3 = st.columns(3)
    with col1:
        upload_season = st.number_input("Season", value=datetime.now().year, step=1)
    with col2:
        upload_tournament = st.text_input("Tournament", value="Australian Open")
    with col3:
        upload_type = st.selectbox("Tournament Type", options=["Slam", "1000"], index=0)

    up = st.file_uploader("Carica CSV risultati (formato classico o stats)", type=["csv"])
    if up is not None:
        raw_df = pd.read_csv(up)
        st.write("Preview upload:")
        st.dataframe(raw_df.head(30), use_container_width=True)

        if st.button("➡️ Normalize & Save to STAGE"):
            stage_df = normalize_results_upload(raw_df, int(upload_season), upload_tournament, upload_type)

            tag = now_tag()
            stage_path = f"{paths.stage_results_dir}/results_norm_{tag}.csv"
            store.write_csv(stage_path, stage_df, f"Stage results {tag}")
            st.session_state.stage_results = stage_df
            st.session_state.last_stage_path = stage_path

            st.success(f"Normalized: {len(stage_df)} righe. Salvato in {stage_path}")

with tab_validate:
    st.header("2) Validate (minimo + report)")
    df = st.session_state.stage_results
    if df is None or df.empty:
        st.info("Carica e normalizza un file in tab Upload.")
    else:
        st.caption(f"Usando STAGE: {st.session_state.last_stage_path}")
        issues = []
        required = ["Season","Tournament","Tournament Type","Giocatore","Round Reached","Matches Won","Matches Lost"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            issues.append({"level":"ERROR","msg":f"Missing columns: {missing}"})
        # basic type checks
        if "Matches Won" in df.columns:
            if not pd.api.types.is_numeric_dtype(df["Matches Won"]):
                issues.append({"level":"WARN","msg":"Matches Won non numerico (verrà coerced in compute)."})
        if df["Giocatore"].isna().any():
            issues.append({"level":"WARN","msg":"Ci sono Giocatore null."})

        st.subheader("Report")
        if issues:
            st.dataframe(pd.DataFrame(issues), use_container_width=True)
        else:
            st.success("Nessun problema bloccante rilevato.")

        st.subheader("Stage dataset")
        st.dataframe(df, use_container_width=True)

with tab_compute:
    st.header("3) Compute")
    df = st.session_state.stage_results
    if df is None or df.empty:
        st.info("Serve uno STAGE (tab Upload).")
    else:
        if st.button("🧮 Compute points + standings"):
            df_points = add_fantapoints(df, multipliers_df)
            players_season = player_standings_season(df_points)
            teams_season = team_standings_season(df_points, teams)

            st.session_state.processed_results = df_points
            st.session_state.processed_players = players_season
            st.session_state.processed_teams = teams_season

            tag = now_tag()
            store.write_csv(f"{paths.processed_facts_dir}/results_with_points_{tag}.csv", df_points, f"Processed results {tag}")
            store.write_csv(f"{paths.processed_marts_dir}/players_standings_{tag}.csv", players_season, f"Players standings {tag}")
            store.write_csv(f"{paths.processed_marts_dir}/teams_standings_{tag}.csv", teams_season, f"Teams standings {tag}")

            st.success("Processed salvati in data/processed/ (facts + marts).")

        if not st.session_state.processed_results.empty:
            st.subheader("Results with points (preview)")
            st.dataframe(st.session_state.processed_results.head(50), use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Classifica giocatori (stagionale)")
                st.dataframe(st.session_state.processed_players, use_container_width=True)
            with c2:
                st.subheader("Classifica squadre (stagionale)")
                st.dataframe(st.session_state.processed_teams, use_container_width=True)

with tab_publish:
    st.header("4) Publish (snapshot + latest)")
    if st.session_state.processed_players.empty and st.session_state.processed_teams.empty:
        st.info("Prima fai Compute.")
    else:
        st.caption("Pubblica solo dataset *public* consumati dalla User App.")
        if st.button("🚀 Publish snapshot + update latest"):
            tag = now_tag()
            snap_prefix = f"{paths.public_snapshots_dir}/{tag}"
            latest_prefix = paths.public_latest_dir

            datasets = {
                "standings_players": st.session_state.processed_players,
                "standings_teams": st.session_state.processed_teams,
                "results_with_points": st.session_state.processed_results,
            }
            info = publish_snapshot(
                store=store,
                snapshot_prefix=snap_prefix,
                latest_prefix=latest_prefix,
                datasets=datasets,
                latest_json_path=paths.public_latest_json,
                message_prefix=f"Publish {tag}",
            )
            st.success(f"Published snapshot: {info['snapshot_prefix']}")
            st.json(info["manifest"])
