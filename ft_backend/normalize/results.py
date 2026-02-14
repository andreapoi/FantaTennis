from __future__ import annotations

import pandas as pd

def normalize_results_upload(df_upload: pd.DataFrame, upload_season: int, upload_tournament: str, upload_type: str) -> pd.DataFrame:
    """
    Supporta 2 formati:
    A) Formato 'classico' app (Season, Tournament, Tournament Type, Giocatore, Round Reached, Matches Won, Matches Lost, ...)
    B) Formato 'stats' stile diretta.it (match_id, match_date, tournament_id, event_type, round, player_name, result, aces, double_faults)
       -> viene convertito nel formato classico, aggiungendo anche Aces e Double Faults.

    Ritorna SEMPRE un df nel formato classico (minimo richiesto da compute_points_with_multipliers).
    """

    df = df_upload.copy()
    cols = {c.strip().lower(): c for c in df.columns}

    # --- Detect formato stats ---
    stats_required_lower = {"match_id", "match_date", "event_type", "round", "player_name", "result", "aces", "double_faults"}
    if stats_required_lower.issubset(set(cols.keys())):
        # Mappo colonne reali (case-insensitive)
        c_match_id = cols["match_id"]
        c_match_date = cols["match_date"]
        c_event_type = cols["event_type"]
        c_round = cols["round"]
        c_player = cols["player_name"]
        c_result = cols["result"]
        c_aces = cols["aces"]
        c_dfs = cols["double_faults"]

        # Tournament id può arrivare come tournament_id oppure lo imposto dai widget
        if "tournament_id" in cols:
            c_tourn = cols["tournament_id"]
            tournament_val = None
        else:
            c_tourn = None
            tournament_val = upload_tournament

        # Converto event_type (slam/1000) -> Tournament Type (Slam/1000)
        def _map_ttype(x: str) -> str:
            x = str(x).strip().lower()
            if x == "slam":
                return "Slam"
            if x == "1000":
                return "1000"
            # fallback: prova a normalizzare già in formato app
            return str(x).strip().title()

        # Converto result (W/L) -> Matches Won/Lost
        def _won(x: str) -> int:
            return 1 if str(x).strip().upper() == "W" else 0

        def _lost(x: str) -> int:
            return 1 if str(x).strip().upper() == "L" else 0

        out = pd.DataFrame({
            "Season": upload_season if "season" not in cols else df[cols["season"]],
            "Tournament": (df[c_tourn] if c_tourn else tournament_val),
            "Tournament Type": df[c_event_type].map(_map_ttype),
            "Giocatore": df[c_player].astype(str).str.strip(),
            "Round Reached": df[c_round].astype(str).str.strip(),
            "Matches Won": df[c_result].map(_won),
            "Matches Lost": df[c_result].map(_lost),

            # Extra utili (non obbligatorie, ma ottime per audit/dedup)
            "match_id": df[c_match_id],
            "match_date": df[c_match_date],

            # Statistiche per scoring automatico
            "Aces": pd.to_numeric(df[c_aces], errors="coerce").fillna(0),
            "Double Faults": pd.to_numeric(df[c_dfs], errors="coerce").fillna(0),
        })

        return out

    # --- Formato classico: mi limito a garantire Season/Tournament/Tournament Type ---
    if "Season" not in df.columns:
        df["Season"] = upload_season
    if "Tournament" not in df.columns:
        df["Tournament"] = upload_tournament
    if "Tournament Type" not in df.columns:
        df["Tournament Type"] = upload_type

    # Se non ci sono colonne stats, inizializzo comunque (così compute_points_with_multipliers non esplode)
    if "Aces" not in df.columns:
        df["Aces"] = 0
    if "Double Faults" not in df.columns:
        df["Double Faults"] = 0

    return df
