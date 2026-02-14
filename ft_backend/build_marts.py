
from __future__ import annotations

from typing import List, Dict, Any, Tuple
import pandas as pd

from .multipliers import build_multiplier_dicts
from .scoring import compute_points_with_multipliers


def add_fantapoints(results_norm: pd.DataFrame, multipliers_df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge colonne RawPoints/BonusPoints/MalusPoints/*Multiplier/Fantapoints."""
    df = results_norm.copy()
    bonus_dict, malus_dict = build_multiplier_dicts(multipliers_df)

    def _row_to_dict(row: pd.Series) -> dict:
        return row.to_dict()

    out_cols = []
    raws=[]
    bonus=[]
    malus=[]
    bmul=[]
    mmul=[]
    fpts=[]
    # vectorization is possible, but keep simple & robust
    for _, r in df.iterrows():
        pos_adj, neg_adj, breakdown = compute_points_with_multipliers(_row_to_dict(r), bonus_dict, malus_dict)
        raw = breakdown["total_before_mult"]
        raws.append(raw)
        bonus.append(max(raw, 0.0))
        malus.append(min(raw, 0.0))
        bmul.append(breakdown["bonus_mult"])
        mmul.append(breakdown["malus_mult"])
        fpts.append(breakdown["pos_after_mult"] + breakdown["neg_after_mult"])

    df["RawPoints"] = raws
    df["BonusPoints"] = bonus
    df["MalusPoints"] = malus
    df["BonusMultiplier"] = bmul
    df["MalusMultiplier"] = mmul
    df["Fantapoints"] = fpts
    return df


def player_standings_season(df_with_points: pd.DataFrame) -> pd.DataFrame:
    if df_with_points.empty:
        return pd.DataFrame(columns=["Giocatore","Totale Fantapoints"])
    return (
        df_with_points.groupby("Giocatore", as_index=False)["Fantapoints"]
        .sum()
        .rename(columns={"Fantapoints": "Totale Fantapoints"})
        .sort_values("Totale Fantapoints", ascending=False)
        .reset_index(drop=True)
    )


def team_standings_season(df_with_points: pd.DataFrame, teams: List[Dict[str, Any]]) -> pd.DataFrame:
    """Replica la logica titolari: Slam=8, 1000=6 (primi N in lista)."""
    if df_with_points.empty:
        return pd.DataFrame(columns=["Team","Manager","Totale punti stagione (solo titolari)"])
    rows=[]
    for team in teams or []:
        team_players = team.get("players", []) or []
        starters_slam = team_players[:8]
        starters_1000 = team_players[:6]

        df_team = df_with_points[df_with_points["Giocatore"].isin(team_players)].copy()
        if df_team.empty:
            total_points = 0.0
        else:
            def _is_starter(row):
                tt = row.get("Tournament Type","")
                if tt == "Slam":
                    return row.get("Giocatore") in starters_slam
                if tt == "1000":
                    return row.get("Giocatore") in starters_1000
                return False
            df_team["IsStarter"] = df_team.apply(_is_starter, axis=1)
            total_points = float(df_team.loc[df_team["IsStarter"], "Fantapoints"].sum())

        rows.append({
            "Team": team.get("name",""),
            "Manager": team.get("manager",""),
            "Totale punti stagione (solo titolari)": int(total_points),
        })
    return pd.DataFrame(rows).sort_values("Totale punti stagione (solo titolari)", ascending=False).reset_index(drop=True)
