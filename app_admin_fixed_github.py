import json
import shutil
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
import requests
import streamlit as st

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
PROCESSED_TEAM_POINTS = PROCESSED_DIR / "team_points.csv"
PUBLIC_MANIFEST = PUBLIC_LATEST_DIR / "manifest.json"

APP_TITLE = "FantaTennis — Admin"
APP_SUBTITLE = "Setup • Upload • Validate • Compute • Publish"

st.set_page_config(page_title=APP_TITLE, layout="wide")


def get_github_config() -> Tuple[bool, dict, str]:
    try:
        gh = st.secrets["github"]
        token = gh.get("token", "").strip()
        repo = gh.get("repo", "").strip()
        branch = gh.get("branch", "main").strip()
        if not token or not repo:
            return False, {}, "Missing github.token or github.repo in st.secrets"
        return True, {"token": token, "repo": repo, "branch": branch}, ""
    except Exception as e:
        return False, {}, f"GitHub secrets not available: {e}"


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_get_file_sha(repo: str, path_in_repo: str, token: str, branch: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"
    resp = requests.get(url, headers=github_headers(token), params={"ref": branch}, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("sha")
    if resp.status_code == 404:
        return None
    raise RuntimeError(f"GitHub GET failed for {path_in_repo}: {resp.status_code} - {resp.text[:300]}")


def github_upload_file(local_path: Path, repo_path: str, commit_message: str) -> Tuple[bool, str]:
    ok, cfg, err = get_github_config()
    if not ok:
        return False, err
    token = cfg["token"]
    repo = cfg["repo"]
    branch = cfg["branch"]

    if not local_path.exists():
        return False, f"Local file not found: {local_path}"

    try:
        content_b64 = base64.b64encode(local_path.read_bytes()).decode("utf-8")
        sha = github_get_file_sha(repo, repo_path, token, branch)
        payload = {"message": commit_message, "content": content_b64, "branch": branch}
        if sha:
            payload["sha"] = sha

        url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
        resp = requests.put(url, headers=github_headers(token), json=payload, timeout=60)
        if resp.status_code in (200, 201):
            action = "updated" if sha else "created"
            return True, f"{action.upper()} GitHub file: {repo_path}"
        return False, f"GitHub PUT failed for {repo_path}: {resp.status_code} - {resp.text[:500]}"
    except Exception as e:
        return False, f"GitHub upload error for {repo_path}: {e}"


def github_upload_many(files_map: List[Tuple[Path, str]], prefix: str) -> Tuple[bool, List[str]]:
    messages = []
    all_ok = True
    for local_path, repo_path in files_map:
        ok, msg = github_upload_file(local_path, repo_path, f"{prefix}: {repo_path}")
        messages.append(msg)
        if not ok:
            all_ok = False
    return all_ok, messages


def ensure_directories() -> None:
    for d in [RAW_DIR, RAW_RESULTS_DIR, STAGE_DIR, PROCESSED_DIR, PUBLIC_DIR, PUBLIC_LATEST_DIR, PUBLIC_SNAPSHOTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


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
    out.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in out.columns]
    return out


def file_rowcount(path: Path) -> Optional[int]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return None
    try:
        return int(len(pd.read_csv(path)))
    except Exception:
        return None


def build_manifest_dict(version: str) -> dict:
    files = {}
    for p in sorted(PUBLIC_LATEST_DIR.glob("*")):
        if p.is_file():
            files[p.name] = file_rowcount(p)
    return {
        "version": version,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


def write_manifest(version: str, snapshot_dir: Optional[Path] = None) -> None:
    manifest = build_manifest_dict(version)
    with open(PUBLIC_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    if snapshot_dir is not None:
        with open(snapshot_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)


def build_validation_report(md: Optional[pd.DataFrame], rosters: Optional[pd.DataFrame], results: Optional[pd.DataFrame]) -> dict:
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "status": "ok", "errors": [], "warnings": [], "counts": {}}
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
                report["errors"].append(f"{len(missing_ids)} roster player ids are not present in md_players. Sample: {missing_ids[:20]}")

    if results is not None:
        results = normalize_columns(results)
        required_results = {"date", "winner", "loser"}
        missing = sorted(required_results - set(results.columns))
        if missing:
            report["warnings"].append(f"results file missing recommended columns for compute: {missing}")
        report["counts"]["results_rows"] = int(len(results))

    if report["errors"]:
        report["status"] = "error"
    elif report["warnings"]:
        report["status"] = "warning"

    with open(STAGE_VALIDATION, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


def find_latest_results_file() -> Optional[Path]:
    files = sorted(RAW_RESULTS_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
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

    md.to_csv(PUBLIC_LATEST_DIR / "md_players.csv", index=False, encoding="utf-8")
    rosters.to_csv(PUBLIC_LATEST_DIR / "team_rosters.csv", index=False, encoding="utf-8")
    return True, "Master data written to data/public/latest/"


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

    if "winner_name" in results.columns and "winner" not in results.columns:
        results["winner"] = results["winner_name"]
    if "loser_name" in results.columns and "loser" not in results.columns:
        results["loser"] = results["loser_name"]

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
        return False, f"Unmapped players in results. winner unmapped: {int(unmapped_w)}, loser unmapped: {int(unmapped_l)}."

    winners = results[["date", "winner_id"]].copy()
    winners["points"] = 10.0
    winners = winners.rename(columns={"winner_id": "id_player"})

    losers = results[["date", "loser_id"]].copy()
    losers["points"] = 0.0
    losers = losers.rename(columns={"loser_id": "id_player"})

    player_points = pd.concat([winners, losers], ignore_index=True)
    player_points = player_points.groupby(["date", "id_player"], as_index=False)["points"].sum()
    player_points = player_points.sort_values(["date", "id_player"]).copy()
    player_points["cumulative_points"] = player_points.groupby("id_player")["points"].cumsum()

    roster_map = rosters[["team_id", "team_name", "id_player"]].drop_duplicates().copy()
    team_points = player_points.merge(roster_map, on="id_player", how="left")
    team_points = team_points.dropna(subset=["team_id"]).copy()

    standings = team_points.groupby(["date", "team_id", "team_name"], as_index=False)["points"].sum()
    standings["total_points"] = standings.groupby("team_id")["points"].cumsum()
    standings = standings.sort_values(["date", "total_points", "team_name"], ascending=[True, False, True]).copy()
    standings["rank"] = standings.groupby("date")["total_points"].rank(method="dense", ascending=False).astype(int)
    standings = standings[["date", "team_id", "team_name", "rank", "total_points"]]

    player_points.to_csv(PROCESSED_PLAYER_POINTS, index=False, encoding="utf-8")
    standings.to_csv(PROCESSED_STANDINGS, index=False, encoding="utf-8")
    team_points.groupby(["date", "team_id", "team_name"], as_index=False)["points"].sum().to_csv(PROCESSED_TEAM_POINTS, index=False, encoding="utf-8")
    return True, f"Compute completed from {results_path.name}"


def publish_snapshot(upload_to_github: bool = False) -> Tuple[bool, str, List[str]]:
    ensure_directories()
    ok, msg = prepare_master_public_files()
    if not ok:
        return False, msg, []

    for src, dst in [
        (PROCESSED_STANDINGS, PUBLIC_LATEST_DIR / "standings.csv"),
        (PROCESSED_PLAYER_POINTS, PUBLIC_LATEST_DIR / "player_points.csv"),
        (PROCESSED_TEAM_POINTS, PUBLIC_LATEST_DIR / "team_points.csv"),
    ]:
        if src.exists():
            shutil.copy2(src, dst)

    version = now_ts()
    snapshot_dir = PUBLIC_SNAPSHOTS_DIR / version
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for p in PUBLIC_LATEST_DIR.glob("*"):
        if p.is_file():
            shutil.copy2(p, snapshot_dir / p.name)

    write_manifest(version=version, snapshot_dir=snapshot_dir)

    github_msgs: List[str] = []
    if upload_to_github:
        repo_files: List[Tuple[Path, str]] = []
        for p in sorted(PUBLIC_LATEST_DIR.glob("*")):
            if p.is_file():
                repo_files.append((p, f"data/public/latest/{p.name}"))
        for p in sorted(snapshot_dir.glob("*")):
            if p.is_file():
                repo_files.append((p, f"data/public/snapshots/{version}/{p.name}"))

        all_ok, github_msgs = github_upload_many(repo_files, prefix=f"Publish snapshot {version}")
        if not all_ok:
            return False, "Publish completed locally, but GitHub upload failed.", github_msgs

    return True, f"Publish completed. Version: {version}", github_msgs


def latest_preview(path: Path, n: int = 20) -> Optional[pd.DataFrame]:
    df = read_csv_safe(path)
    return None if df is None else df.head(n)


def render_file_status(label: str, path: Path) -> None:
    exists = path.exists()
    st.write(f"**{label}**")
    st.code(str(path))
    st.write("Status:", "✅ Present" if exists else "❌ Missing")
    if exists:
        st.caption("Last modified: " + datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" ", timespec="seconds"))
        if path.suffix.lower() == ".csv":
            st.caption(f"Rows: {file_rowcount(path)}")


ensure_directories()

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

tab_setup, tab_results, tab_validate, tab_compute, tab_publish, tab_monitor = st.tabs(["Setup", "Results Upload", "Validate", "Compute", "Publish", "Monitoring"])

with tab_setup:
    st.subheader("Setup — Master Data")
    gh_ok, gh_cfg, gh_err = get_github_config()
    st.caption(f"GitHub: {'configured' if gh_ok else 'not configured'}" + (f" — repo {gh_cfg['repo']} / branch {gh_cfg['branch']}" if gh_ok else f" — {gh_err}"))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### md_players.csv")
        up_md = st.file_uploader("Upload md_players.csv", type=["csv"], key="md_players_uploader")
        if up_md is not None:
            save_uploaded_file(up_md, RAW_MD_PLAYERS)
            st.success(f"Saved to {RAW_MD_PLAYERS}")
        render_file_status("Raw md_players", RAW_MD_PLAYERS)
        df = latest_preview(RAW_MD_PLAYERS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with c2:
        st.markdown("### team_rosters.csv")
        up_rosters = st.file_uploader("Upload team_rosters.csv", type=["csv"], key="team_rosters_uploader")
        if up_rosters is not None:
            save_uploaded_file(up_rosters, RAW_TEAM_ROSTERS)
            st.success(f"Saved to {RAW_TEAM_ROSTERS}")
        render_file_status("Raw team_rosters", RAW_TEAM_ROSTERS)
        df = latest_preview(RAW_TEAM_ROSTERS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

    push_master = st.checkbox("Also upload public master data to GitHub", value=True, key="push_master")
    if st.button("Publish master data to public/latest", type="primary"):
        ok, msg = prepare_master_public_files()
        if ok:
            st.success(msg)
            github_msgs = []
            if push_master:
                all_ok, github_msgs = github_upload_many([
                    (PUBLIC_LATEST_DIR / "md_players.csv", "data/public/latest/md_players.csv"),
                    (PUBLIC_LATEST_DIR / "team_rosters.csv", "data/public/latest/team_rosters.csv"),
                ], prefix=f"Publish master data {now_ts()}")
                if not all_ok:
                    st.error("Local write ok, GitHub upload failed.")
                else:
                    st.success("GitHub master data upload completed.")
            if github_msgs:
                with st.expander("GitHub upload log", expanded=True):
                    for m in github_msgs:
                        st.write("-", m)
        else:
            st.error(msg)

with tab_results:
    st.subheader("Upload Results")
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
    st.write("MVP model: winner = 10, loser = 0.")
    if st.button("Run compute", type="primary"):
        ok, msg = compute_from_results()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    c1, c2, c3 = st.columns(3)
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
    with c3:
        render_file_status("Processed team_points.csv", PROCESSED_TEAM_POINTS)
        df = latest_preview(PROCESSED_TEAM_POINTS)
        if df is not None:
            st.dataframe(df, use_container_width=True, hide_index=True)

with tab_publish:
    st.subheader("Publish")
    push_publish = st.checkbox("Also upload published files and snapshots to GitHub", value=True, key="push_publish")
    if st.button("Publish latest", type="primary"):
        ok, msg, github_msgs = publish_snapshot(upload_to_github=push_publish)
        if ok:
            st.success(msg)
        else:
            st.error(msg)
        if github_msgs:
            with st.expander("GitHub upload log", expanded=True):
                for m in github_msgs:
                    st.write("-", m)

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
    rows = []
    for p in [RAW_MD_PLAYERS, RAW_TEAM_ROSTERS, find_latest_results_file(), PROCESSED_PLAYER_POINTS, PROCESSED_STANDINGS, PROCESSED_TEAM_POINTS, PUBLIC_LATEST_DIR / "md_players.csv", PUBLIC_LATEST_DIR / "team_rosters.csv", PUBLIC_LATEST_DIR / "player_points.csv", PUBLIC_LATEST_DIR / "standings.csv", PUBLIC_MANIFEST]:
        if p is None:
            continue
        rows.append({
            "path": str(p),
            "exists": p.exists(),
            "modified_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(sep=" ", timespec="seconds") if p.exists() else "",
            "rows": file_rowcount(p),
            "size_bytes": int(p.stat().st_size) if p.exists() else 0,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    snapshots = sorted(PUBLIC_SNAPSHOTS_DIR.glob("*"), reverse=True)
    if snapshots:
        st.markdown("### Snapshots")
        st.dataframe(pd.DataFrame({"snapshot": [p.name for p in snapshots], "path": [str(p) for p in snapshots]}), use_container_width=True, hide_index=True)
