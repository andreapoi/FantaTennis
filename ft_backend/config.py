
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class RepoPaths:
    # original app "core" paths
    players_csv: str = "data/players.csv"
    teams_json: str = "data/teams.json"
    results_csv: str = "data/results.csv"
    multipliers_csv: str = "data/ranking_multipliers.csv"

    # pipeline paths (App1 backend)
    raw_results_dir: str = "data/raw/results"
    stage_results_dir: str = "data/stage/results_norm"
    stage_reports_dir: str = "data/stage/reports"

    processed_facts_dir: str = "data/processed/facts"
    processed_marts_dir: str = "data/processed/marts"

    public_latest_dir: str = "data/public/latest"
    public_snapshots_dir: str = "data/public/snapshots"
    public_latest_json: str = "data/public/latest.json"
