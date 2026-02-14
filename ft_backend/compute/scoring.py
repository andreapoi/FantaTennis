
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Any

# ------------------------------------------------------
# COSTANTI PUNTEGGI (copiate dalla tua app)
# ------------------------------------------------------
ROUND_BONUS = {
    "Slam": {
        "Winner": 40,
        "Final": 25,
        "SF": 18,
        "QF": 12,
        "R16": 7,
        "R32": 4,
        "R64": 2,
        "R128": 0,
    },
    "1000": {
        "Winner": 30,
        "Final": 18,
        "SF": 12,
        "QF": 8,
        "R16": 4,
        "R32": 2,
        "R64": 0,
        "R128": 0,
    },
}

BONUS_FLAGS = {
    "beat_top10": 3,
    "beat_top5": 5,
    "beat_num1": 8,
    "win_straight_sets": 2,
    "win_few_games": 3,
    "aces_15_plus": 2,
    "first_serve_80_plus": 2,
    "comeback_0_2_slam": 5,
    "comeback_0_1_1000": 3,
    "win_in_fifth_slam": 3,
}

MALUS_FLAGS = {
    "df_10_plus": -2,
    "return_pts_lt_30": -1,
    "second_serve_lt_40": -2,
    "blew_match_point": -3,
    "lost_from_2_0_slam": -6,
}

ACE_POINT = 0.5
DF_POINT = 0.5

MATCH_BOOL_COLUMNS = list(BONUS_FLAGS.keys()) + list(MALUS_FLAGS.keys())


def compute_match_points(wins: int, losses: int) -> int:
    """Punteggio base: Vittoria +6, Sconfitta +1."""
    return int(wins) * 6 + int(losses) * 1


def compute_round_bonus(t_type: str, round_reached: str) -> int:
    """Bonus extra in base a tipo torneo e turno raggiunto."""
    return int(ROUND_BONUS.get(str(t_type), {}).get(str(round_reached), 0))


def compute_points_with_multipliers(
    row: dict,
    bonus_mult_dict: Dict[str, float],
    malus_mult_dict: Dict[str, float],
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Calcola:
    - punti_pos (>=0) con moltiplicatore bonus giocatore
    - punti_neg (<=0) con moltiplicatore malus giocatore
    Ritorna anche breakdown.
    """
    wins = row.get("Matches Won", 0) or 0
    losses = row.get("Matches Lost", 0) or 0
    base_points = compute_match_points(wins, losses)

    t_type = row.get("Tournament Type", "")
    round_reached = row.get("Round Reached", "")
    round_bonus = compute_round_bonus(t_type, round_reached)

    # extra stats
    aces = float(row.get("Aces", 0) or 0)
    dfs = float(row.get("Double Faults", 0) or 0)

    # punti stats (se nel tuo modello contano come bonus/malus continui)
    ace_pts = aces * ACE_POINT
    df_pts = -(dfs * DF_POINT)

    # flags (0/1)
    flag_pts = 0.0
    flag_detail = {}
    for k, v in BONUS_FLAGS.items():
        val = float(row.get(k, 0) or 0)
        if val == 1:
            flag_pts += v
            flag_detail[k] = v
    for k, v in MALUS_FLAGS.items():
        val = float(row.get(k, 0) or 0)
        if val == 1:
            flag_pts += v
            flag_detail[k] = v

    total = float(base_points + round_bonus) + float(ace_pts + df_pts) + float(flag_pts)

    # split pos/neg
    pos = max(total, 0.0)
    neg = min(total, 0.0)

    player = str(row.get("Giocatore", "") or "").strip().lower()
    bmult = float(bonus_mult_dict.get(player, 1.0))
    mmult = float(malus_mult_dict.get(player, 1.0))

    pos_adj = pos * bmult
    neg_adj = neg * mmult  # neg is negative; mmult>=1 amplifica il malus

    breakdown = {
        "base": float(base_points),
        "round_bonus": float(round_bonus),
        "ace_pts": float(ace_pts),
        "df_pts": float(df_pts),
        "flags": flag_detail,
        "flags_total": float(flag_pts),
        "total_before_mult": float(total),
        "bonus_mult": bmult,
        "malus_mult": mmult,
        "pos_after_mult": float(pos_adj),
        "neg_after_mult": float(neg_adj),
    }
    return pos_adj, neg_adj, breakdown
