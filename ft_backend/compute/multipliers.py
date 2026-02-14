
from __future__ import annotations

from typing import Dict, Tuple
import pandas as pd


def build_multiplier_dicts(multipliers_df: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Input atteso: colonne (case-insensitive):
      - ranking
      - player
      - moltiplicatore bonus
      - moltiplicatore malus
    Output:
      - bonus_mult_dict[player_lower] -> float
      - malus_mult_dict[player_lower] -> float
    """
    if multipliers_df is None or multipliers_df.empty:
        return {}, {}

    df = multipliers_df.copy()
    df.columns = [c.strip().lower().replace("\ufeff", "") for c in df.columns]

    required = {"ranking", "player", "moltiplicatore bonus", "moltiplicatore malus"}
    if not required.issubset(set(df.columns)):
        return {}, {}

    df["key"] = df["player"].astype(str).str.strip().str.lower()
    bonus_dict = dict(zip(df["key"], df["moltiplicatore bonus"].astype(float)))
    malus_dict = dict(zip(df["key"], df["moltiplicatore malus"].astype(float)))
    return bonus_dict, malus_dict
