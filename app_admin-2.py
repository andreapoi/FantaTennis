import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_RESULTS_DIR = RAW_DIR / "results"
STAGE_DIR = DATA_DIR / "stage"
PROCESSED_DIR = DATA_DIR / "processed"
PUBLIC_DIR = DATA_DIR / "public"
PUBLIC_LATEST_DIR = PUBLIC_DIR / "latest"
PUBLIC_SNAPSHOTS_DIR = PUBLIC_DIR / "snapshots"

RAW_MD_PLAYERS = RAW_DIR / "md_players.csv"
RAW_TEAM_ROSTERS = RAW_DIR / "team_rosters.csv"
STAGE_VALIDATION = STAGE_DIR / "validation_report.json"
PROCESSED_PLAYER_POINTS = PROCESSED_DIR / "player_points.csv"
PROCESSED_STANDINGS = PROCESSED_DIR / "standings.csv"
PUBLIC_MANIFEST = PUBLIC_LATEST_DIR / "manifest.json"

APP_TITLE = "FantaTennis — Admin"
APP_SUBTITLE = "Setup • Upload • Validate • Compute • Publish"

st.set_page_config(page_title=APP_TITLE, layout="wide")


# ============================================================
# HELPERS
# ============================================================
def ensure_directories() -> None:
    dirs = [
        RAW_DIR,
        RAW_RESULTS_DIR,
        STAGE_DIR,
        PROCESSED_DIR,
        PUBLIC_DIR,
        PUBLIC_LATEST_DIR,
        PUBLIC_SNAPSHOTS_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_csv_safe(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if path is None or not path.exists():
        return None

    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
    seps = [",", ";"]
    last_error = None

    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep)
                if df.shape[1] > 1:
                    return df
            except Exception as e:
                last_error = e

    raise RuntimeError(f"Unable to read CSV: {path}. Last error: {last_error}")


def save_uploaded_file(uploaded_file, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in out.columns
    ]
    return out


def build_validation_report(
    md: Optional[pd.DataFrame],
    rosters: Optional[pd.DataFrame],
    results: Optional[pd.DataFrame]
) -> dict:
    report = {
        "created_at": datetime.now().isoformat(),
        "status": "ok",
        "errors": [],
        "warnings": [],
        "counts": {},
    }

    if md is None:
        report["errors"].append("Missing data/raw/md_players.csv")
    if rosters is None:
        report["errors"].append("Missing data/raw/team_rosters.csv")

    if md is not None:
        md = normalize_columns(md)
        required_md = {"id_player", "player"}
        missing = sorted(required_md - set(md.columns))
        if missing:
            report["errors"].append(f"md_players missing columns: {missing}")
        else:
            report["counts"]["md_players_rows"] = int(len(md))
            dup_ids = int(md["id_player"].astype(str).duplicated().sum())
            if dup_ids:
                report["errors"].append(f"md_players has {dup_ids} duplicated id_player values")

    if rosters is not None:
        rosters = normalize_columns(rosters)
        required_rosters = {"team_id", "team_name", "id_player"}
        missing = sorted(required_rosters - set(rosters.columns))
        if missing:
            report["errors"].append(f"team_rosters missing columns: {missing}")
        else:
            report["counts"]["team_rosters_rows"] = int(len(rosters))
            dup_pairs = int(rosters[["team_id", "id_player"]].astype(str).duplicated().sum())
            if dup_pairs:
                report["errors"].append(f"team_rosters has {dup_pairs} duplicated (team_id, id_player) pairs")

    if md is not None and rosters is not None:
        md = normalize_columns(md)
        rosters = normalize_columns(rosters)
        if {"id_player"} <= set(md.columns) and {"id_player"} <= set(rosters.columns):
            md_ids = set(md["id_player"].astype(str).str.strip())
            roster_ids = set(rosters["id_player"].astype(str).str.strip())
            missing_ids = sorted(x for x in roster_ids if x and x not in md_ids)
            if missing_ids:
                sample = missing_ids[:20]
                report["errors"].append(
                    f"{len(missing_ids)} roster player ids are not present in md_players. Sample: {sample}"
                )

    if results is not None:
        results = normalize_columns(results)
        required_results = {"date", "winner", "loser"}
        missing = sorted(required_results - set(results.columns))
        if missing:
            report["warnings"].append(
                f"results file missing recommended columns for compute: {missing}"
            )
        report["counts"]["results_rows"] = int(len(results))

    if report["errors"]:
        report["status"] = "error"
    elif report["warnings"]:
        report["status"] = "warning"

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STAGE_VALIDATION, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def find_latest_results_file() -> Optional[Path]:
    files = sorted(
        RAW_RESULTS_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return files[0] if files else None


def prepare_master_public_files() -> Tuple[bool, str]:
    md = read_csv_safe(RAW_MD_PLAYERS)
    rosters = read_csv_safe(RAW_TEAM_ROSTERS)

    if md is None or rosters is None:
        return False, "Missing md_players.csv or team_rosters.csv in data/raw/"

    md = normalize_columns(md)
    rosters = normalize_columns(rosters)

    if "player" not in md.columns and "full_name" in md.columns:
        md["player"] = md["full_name"]
    if "full_name" not in md.columns and "player" in md.columns:
        md["full_name"] = md["player"]

    required_md = {"id_player", "player"}
    required_rosters = {"team_id", "team_name", "id_player"}

    if not required_md <= set(md.columns):
        return False, f"md_players.csv must contain at least: {sorted(required_md)}"
    if not required_rosters <= set(rosters.columns):
        return False, f"team_rosters.csv must contain at least: {sorted(required_rosters)}"

    md_public = md.copy()
    roster_public = rosters.copy()

    md_public.to_csv(PUBLIC_LATEST_DIR / "md_players.csv", index=False, encoding="utf-8")
    roster_public.to_csv(PUBLIC_LATEST_DIR / "team_rosters.csv", index=False, encoding="utf-8")
    return True, "md_players.csv and team_rosters.csv published to data/public/latest/"


def compute_from_results() -> Tuple[bool, str]:
    md = read_csv_safe(RAW_MD_PLAYERS)
    rosters = read_csv_safe(RAW_TEAM_ROSTERS)
    results_path = find_latest_results_file()

    if md is None or rosters is None:
        return False, "Missing md_players.csv or team_rosters.csv in data/raw/"
    if results_path is None:
        return False, "No results file found in data/raw/results/"

    results = read_csv_safe(results_path)
    if results is None:
        return False, "Unable to read latest results file."

    md = normalize_columns(md)
    rosters = normalize_columns(rosters)
    results = normalize_columns(results)

    if "player" not in md.columns and "full_name" in md.columns:
        md["player"] = md["full_name"]
    if "full_name" not in md.columns and "player" in md.columns:
        md["full_name"] = md["player"]

    required_md = {"id_player", "player"}
    required_rosters = {"team_id", "team_name", "id_player"}
    required_results = {"date", "winner", "loser"}

    if not required_md <= set(md.columns):
        return False, f"md_players.csv must contain at least: {sorted(required_md)}"
    if not required_rosters <= set(rosters.columns):
        return False, f"team_rosters.csv must contain at least: {sorted(required_rosters)}"
    if not required_results <= set(results.columns):
        return False, f"results file must contain at least: {sorted(required_results)}"

    results["date"] = pd.to_datetime(results["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    results = results[results["date"].notna()].copy()

    md["player_norm"] = md["player"].astype(str).str.strip().str.lower()
    player_map = dict(zip(md["player_norm"], md["id_player"].astype(str)))

    results["winner_norm"] = results["winner"].astype(str).str.strip().str.lower()
    results["loser_norm"] = results["loser"].astype(str).str.strip().str.lower()
    results["winner_id"] = results["winner_norm"].map(player_map)
    results["loser_id"] = results["loser_norm"].map(player_map)

    unmapped_w = results["winner_id"].isna().sum()
    unmapped_l = results["loser_id"].isna().sum()
    if unmapped_w or unmapped_l:
        return False, (
            f"Unmapped players in results. winner unmapped: {int(unmapped_w)}, "
            f"loser unmapped: {int(unmapped_l)}. Check naming consistency with md_players.csv."
        )

    win_points = 10.0
    loss_points = 0.0

    winners = results[["date", "winner_id"]].copy()
    winners["points"] = win_points
    winners = winners.rename(columns={"winner_id": "id_player"})

    losers = results[["date", "loser_id"]].copy()
    losers["points"] = loss_points
    losers = losers.rename(columns={"loser_id": "id_player"})

    player_points = pd.concat([winners, losers], ignore_index=True)
    player_points = (
        player_points
        .groupby(["date", "id_player"], as_index=False)["points"]
        .sum()
        .sort_values(["date", "id_player"])
    )
    player_points["cumulative_points"] = (
        player_points.groupby("id_player")["points"].cumsum()
    )

    roster_map = rosters[["team_id", "team_name", "id_player"]].drop_duplicates().copy()
    team_points = player_points.merge(roster_map, on="id_player", how="left")
    team_points = team_points.dropna(subset=["team_id"]).copy()

    standings = (
        team_points
        .groupby(["date", "team_id", "team_name"], as_index=False)["points"]
        .sum()
        .rename(columns={"points": "day_points"})
        .sort_values(["date", "team_id"])
    )
    standings["total_points"] = standings.groupby("team_id")["day_points"].cumsum()
    standings = standings.sort_values(
        ["date", "total_points", "team_name"],
        ascending=[True, False, True]
    ).copy()
    standings["rank"] = (
        standings.groupby("date")["total_points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    standings = standings[["date", "team_id", "team_name", "rank", "total_points"]]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_LATEST_DIR.mkdir(parents=True, exist_ok=True)

    player_points.to_csv(PROCESSED_PLAYER_POINTS, index=False, encoding="utf-8")
    standings.to_csv(PROCESSED_STANDINGS, index=False, encoding="utf-8")

    team_points_out = (
        team_points.groupby(["date", "team_id", "team_name"], as_index=False)["points"]
        .sum()
        .rename(columns={"points": "points"})
    )
    team_points_out.to_csv(PROCESSED_DIR / "team_points.csv", index=False, encoding="utf-8")

    return True, (
        f"Compute completed from {results_path.name}. "
        f"Generated processed/player_points.csv and processed/standings.csv."
    )


def publish_snapshot() -> Tuple[bool, str]:
    ensure_directories()

    ok, msg = prepare_master_public_files()
    if not ok:
        return False, msg

    files_to_publish = [
        (PROCESSED_STANDINGS, PUBLIC_LATEST_DIR / "standings.csv"),
        (PROCESSED_PLAYER_POINTS, PUBLIC_LATEST_DIR / "player_points.csv"),
        (PROCESSED_DIR / "team_points.csv", PUBLIC_LATEST_DIR / "team_points.csv"),
    ]
    for src, dst in files_to_publish:
        if src.exists():
            shutil.copy2(src, dst)

    snapshot_id = now_ts()
    snapshot_dir = PUBLIC_SNAPSHOTS_DIR / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    published_files = {}
    for p in PUBLIC_LATEST_DIR.glob("*"):
        if p.is_file():
            shutil.copy2(p, snapshot_dir / p.name)
            if p.suffix.lower() == ".csv":
                try:
                    published_files[p.name] = int(len(pd.read_csv(p)))
                except Exception:
                    published_files[p.name] = None

    manifest = {
        "version": snapshot_id,
        "updated_at": datetime.now().isoformat(),
        "files": published_files,
    }
    with open(PUBLIC_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    with open(snapshot_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return True, f"Publish completed. Snapshot created: {snapshot_dir}"


def latest_preview(path: Path, n: int = 20) -> Optional[pd.DataFrame]:
    df = read_csv_safe(path)
    if df is None:
        return None
    return df.head(n)


def render_file_status(label: str, path: Path) -> None:
    exists = path.exists()
    st.write(f"**{label}**")
    st.code(str(path))
    st.write("Status:", "✅ Present" if exists else "❌ Missing")
    if exists:
        st.caption(
            "Last modified: " +
            datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                sep=' ',
                timespec='seconds'
            )
        )


# ============================================================
# APP
# ============================================================
ensure_directories()

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

tab_setup, tab_results, tab_validate, tab_compute, tab_publish, tab_monitor = st.tabs(
    ["Setup", "Results Upload", "Validate", "Compute", "Publish", "Monitoring"]
)

with tab_setup:
    st.subheader("Setup — Master Data")
    st.write("Upload the two bootstrap files required by the backend.")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### md_players.csv")
        up_md = st.file_uploader(
            "Upload md_players.csv",
            type=["csv"],
            key="md_players_uploader"
        )
        if up_md is not None:
            save_uploaded_file(up_md, RAW_MD_PLAYERS)
            st.success(f"Saved to {RAW_MD_PLAYERS}")
        render_file_status("Raw md_players", RAW_MD_PLAYERS)
        df = latest_preview(RAW_MD_PLAYERS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with c2:
        st.markdown("### team_rosters.csv")
        up_rosters = st.file_uploader(
            "Upload team_rosters.csv",
            type=["csv"],
            key="team_rosters_uploader"
        )
        if up_rosters is not None:
            save_uploaded_file(up_rosters, RAW_TEAM_ROSTERS)
            st.success(f"Saved to {RAW_TEAM_ROSTERS}")
        render_file_status("Raw team_rosters", RAW_TEAM_ROSTERS)
        df = latest_preview(RAW_TEAM_ROSTERS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    if st.button("Publish master data to public/latest", type="primary"):
        ok, msg = prepare_master_public_files()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

with tab_results:
    st.subheader("Upload Results")
    st.write(
        "Upload one match-level results CSV. "
        "The latest uploaded file will be used by Compute."
    )
    up_results = st.file_uploader("Upload results CSV", type=["csv"], key="results_uploader")
    if up_results is not None:
        dest = RAW_RESULTS_DIR / f"{now_ts()}_{up_results.name}"
        save_uploaded_file(up_results, dest)
        st.success(f"Saved to {dest}")

    latest_results = find_latest_results_file()
    if latest_results is None:
        st.info("No results file uploaded yet.")
    else:
        render_file_status("Latest results file", latest_results)
        df = latest_preview(latest_results)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

with tab_validate:
    st.subheader("Validate Inputs")
    latest_results = find_latest_results_file()
    md = read_csv_safe(RAW_MD_PLAYERS)
    rosters = read_csv_safe(RAW_TEAM_ROSTERS)
    results = read_csv_safe(latest_results) if latest_results is not None else None

    if st.button("Run validation", type="primary"):
        report = build_validation_report(md, rosters, results)
        if report["status"] == "error":
            st.error("Validation failed.")
        elif report["status"] == "warning":
            st.warning("Validation completed with warnings.")
        else:
            st.success("Validation completed successfully.")
        st.json(report)

    if STAGE_VALIDATION.exists():
        with open(STAGE_VALIDATION, "r", encoding="utf-8") as f:
            st.markdown("### Last validation report")
            st.json(json.load(f))

with tab_compute:
    st.subheader("Compute")
    st.write("This MVP compute uses a simple scoring model: winner = 10, loser = 0.")
    if st.button("Run compute", type="primary"):
        ok, msg = compute_from_results()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    c1, c2 = st.columns(2)
    with c1:
        render_file_status("Processed player_points.csv", PROCESSED_PLAYER_POINTS)
        df = latest_preview(PROCESSED_PLAYER_POINTS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)
    with c2:
        render_file_status("Processed standings.csv", PROCESSED_STANDINGS)
        df = latest_preview(PROCESSED_STANDINGS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

with tab_publish:
    st.subheader("Publish")
    st.write(
        "Publishes master data and, if available, computed outputs into "
        "data/public/latest/ and creates a versioned snapshot."
    )
    if st.button("Publish latest", type="primary"):
        ok, msg = publish_snapshot()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    c1, c2 = st.columns(2)
    with c1:
        render_file_status("Public latest md_players.csv", PUBLIC_LATEST_DIR / "md_players.csv")
        render_file_status("Public latest team_rosters.csv", PUBLIC_LATEST_DIR / "team_rosters.csv")
        render_file_status("Public latest player_points.csv", PUBLIC_LATEST_DIR / "player_points.csv")
        render_file_status("Public latest standings.csv", PUBLIC_LATEST_DIR / "standings.csv")
    with c2:
        render_file_status("Public manifest.json", PUBLIC_MANIFEST)
        if PUBLIC_MANIFEST.exists():
            with open(PUBLIC_MANIFEST, "r", encoding="utf-8") as f:
                st.json(json.load(f))

with tab_monitor:
    st.subheader("Monitoring")
    status_rows = []
    for p in [
        RAW_MD_PLAYERS,
        RAW_TEAM_ROSTERS,
        find_latest_results_file(),
        PROCESSED_PLAYER_POINTS,
        PROCESSED_STANDINGS,
        PUBLIC_LATEST_DIR / "md_players.csv",
        PUBLIC_LATEST_DIR / "team_rosters.csv",
        PUBLIC_LATEST_DIR / "player_points.csv",
        PUBLIC_LATEST_DIR / "standings.csv",
        PUBLIC_MANIFEST,
    ]:
        if p is None:
            continue
        status_rows.append({
            "path": str(p),
            "exists": p.exists(),
            "modified_at": (
                datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=' ', timespec='seconds')
                if p.exists() else ""
            ),
            "size_bytes": int(p.stat().st_size) if p.exists() else 0,
        })

    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    snapshots = sorted(PUBLIC_SNAPSHOTS_DIR.glob("*"), reverse=True)
    st.markdown("### Snapshots")
    if snapshots:
        snap_df = pd.DataFrame({
            "snapshot": [p.name for p in snapshots],
            "path": [str(p) for p in snapshots],
        })
        st.dataframe(snap_df, use_container_width=True, hide_index=True)
    else:
        st.info("No snapshots created yet.")
