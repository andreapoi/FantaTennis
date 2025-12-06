# fantatennis_app.py

import streamlit as st
import pandas as pd

import base64
import io
import json
import requests

# ----------------- CONFIG GITHUB -----------------
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_REPO = st.secrets["github"]["repo"]       # es. "andreapoi/FantaTennis"
GITHUB_BRANCH = st.secrets["github"]["branch"]   # es. "main"

GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}/contents"

PLAYERS_PATH = "data/players.csv"
TEAMS_PATH = "data/teams.json"
RESULTS_PATH = "data/results.csv"


def _github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def load_file_from_github(path: str):
    """
    Ritorna (content_bytes, sha) se il file esiste,
    altrimenti (None, None).
    """
    url = f"{GITHUB_API_BASE}/{path}"
    resp = requests.get(url, headers=_github_headers())
    if resp.status_code == 200:
        data = resp.json()
        # "content" è base64
        content_b64 = data["content"]
        sha = data["sha"]
        content = base64.b64decode(content_b64)
        return content, sha
    elif resp.status_code == 404:
        return None, None
    else:
        st.error(f"Errore GitHub GET {path}: {resp.status_code} - {resp.text}")
        return None, None


def save_file_to_github(path: str, content_bytes: bytes, message: str):
    """
    Crea o aggiorna un file su GitHub nel repo configurato.
    """
    url = f"{GITHUB_API_BASE}/{path}"
    existing_content, existing_sha = load_file_from_github(path)

    payload = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if existing_sha is not None:
        payload["sha"] = existing_sha

    resp = requests.put(url, headers=_github_headers(), data=json.dumps(payload))
    if resp.status_code not in (200, 201):
        st.error(f"Errore GitHub PUT {path}: {resp.status_code} - {resp.text}")
    return resp


# -------- PLAYERS (DataFrame) --------
def load_players_df() -> pd.DataFrame:
    content, _ = load_file_from_github(PLAYERS_PATH)
    if content is None:
        return pd.DataFrame(columns=["Giocatore", "Squadra", "Prezzo"])
    csv_str = content.decode("utf-8")
    return pd.read_csv(io.StringIO(csv_str))


def save_players_df(df: pd.DataFrame):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    save_file_to_github(PLAYERS_PATH, csv_bytes, "Update players.csv from app")


# -------- TEAMS (lista di dict) --------
def load_teams_list():
    content, _ = load_file_from_github(TEAMS_PATH)
    if content is None:
        return []
    json_str = content.decode("utf-8")
    return json.loads(json_str)


def save_teams_list(teams: list):
    json_bytes = json.dumps(teams, ensure_ascii=False, indent=2).encode("utf-8")
    save_file_to_github(TEAMS_PATH, json_bytes, "Update teams.json from app")


# -------- RESULTS / STANDINGS --------
def load_results_df():
    content, _ = load_file_from_github(RESULTS_PATH)
    if content is None:
        return pd.DataFrame()
    csv_str = content.decode("utf-8")
    return pd.read_csv(io.StringIO(csv_str))


def save_results_df(df: pd.DataFrame):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    save_file_to_github(RESULTS_PATH, csv_bytes, "Update results.csv from app")


# -------- INIZIALIZZAZIONE SESSION_STATE DA GITHUB --------
if "players_df" not in st.session_state:
    st.session_state.players_df = load_players_df()

if "teams" not in st.session_state:
    st.session_state.teams = load_teams_list()

if "results_df" not in st.session_state:
    st.session_state.results_df = load_results_df()

if "tournament_df" not in st.session_state:
    st.session_state.tournament_df = None

if "last_results_df" not in st.session_state:
    st.session_state.last_results_df = None

# ------------------------------------------------------
# CONFIGURAZIONE APP
# ------------------------------------------------------
st.set_page_config(
    page_title="Fantatennis Manager",
    page_icon="🎾",
    layout="wide",
)

# ------------------------------------------------------
# COSTANTI PUNTEGGI
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

ALL_TOURNAMENT_TYPES = ["Slam", "1000"]
ALL_ROUNDS = [
    "Winner", "Final", "SF", "QF", "R16", "R32", "R64", "R128"
]


def compute_match_points(wins: int, losses: int) -> int:
    """
    Punteggio base:
    - Vittoria: +6
    - Sconfitta: +1
    """
    return wins * 6 + losses * 1


def compute_round_bonus(t_type: str, round_reached: str) -> int:
    """
    Bonus extra in base al tipo di torneo e al turno raggiunto.
    """
    if t_type not in ROUND_BONUS:
        return 0
    return ROUND_BONUS[t_type].get(round_reached, 0)


def compute_fantapoints(row) -> int:
    base = compute_match_points(
        wins=row.get("Matches Won", 0),
        losses=row.get("Matches Lost", 0),
    )
    bonus = compute_round_bonus(
        t_type=row.get("Tournament Type", ""),
        round_reached=row.get("Round Reached", ""),
    )
    return base + bonus

# ------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------
st.sidebar.title("🎾 Fantatennis Manager")
page = st.sidebar.radio(
    "Naviga",
    ["🏠 Home & Regole", "👤 Giocatori", "👥 Squadre", "🏆 Torneo & Punteggi", "📈 Stagione & Classifica"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Made with Streamlit + Fantatennis rules 😉")

# ------------------------------------------------------
# PAGINA 1: HOME & REGOLE
# ------------------------------------------------------
if page == "🏠 Home & Regole":
    st.title("🎾 Fantatennis Manager")
    st.subheader("Gestione completa del tuo fantatennis stile fantacalcio")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            Questa app ti aiuta a:
            - Definire un **listone di giocatori** con prezzo
            - Creare **squadre da 10 giocatori**
            - Calcolare i punti di un **singolo torneo**
            - (Nuovo) Simulare la **stagione intera** dalla pagina *Stagione & Classifica*
            """
        )
    with col2:
        st.info(
            """
            ✅ Dati salvati su GitHub  
            ✅ Pensata per slam e 1000  
            ✅ Gestione titolari/riserve automatica in base all'ordine in rosa
            """
        )

    st.markdown("---")
    st.markdown(
        """
        ### Sistema di punteggio (base)
        - Vittoria: **+6 punti**  
        - Sconfitta: **+1 punto**

        ### Bonus turno (Slam)
        - Winner: +40  
        - Final: +25  
        - SF: +18  
        - QF: +12  
        - R16: +7  
        - R32: +4  
        - R64: +2  

        ### Bonus turno (1000)
        - Winner: +30  
        - Final: +18  
        - SF: +12  
        - QF: +8  
        - R16: +4  
        - R32: +2  
        - R64: 0  
        """
    )

    st.markdown("---")
    st.markdown(
        """
        💡 *Regola rosa e formazione*:  
        - Ogni squadra ha **10 giocatori fissi**  
        - Per uno **Slam**: i **primi 8** in rosa = titolari, gli **ultimi 2** = riserve  
        - Per un **1000**: i **primi 6** = titolari, i successivi **2** = riserve, gli ultimi 2 fuori  
        Se vuoi cambiare chi è titolare, cambia l'**ordine** dei giocatori nella rosa.
        """
    )

# ------------------------------------------------------
# PAGINA 2: GIOCATORI
# ------------------------------------------------------
if page == "👤 Giocatori":
    st.title("👤 Gestione Giocatori Fantatennis")

    st.markdown(
        """
        Qui gestisci l'**anagrafica dei giocatori**: nome, categoria e prezzo.
        Puoi:
        - Aggiungere / modificare direttamente nella tabella
        - Scaricare / caricare il CSV per riutilizzarlo
        """
    )

    # Upload CSV
st.subheader("Carica giocatori da CSV")
uploaded = st.file_uploader("Carica file CSV", type=["csv"])
if uploaded is not None:
    try:
        # 1️⃣ Primo tentativo: separatore di default (",")
        df_new = pd.read_csv(uploaded)

        # 2️⃣ Se vedo una sola colonna con dentro i ";" → è un CSV con separatore ";"
        if len(df_new.columns) == 1 and ";" in df_new.columns[0]:
            uploaded.seek(0)  # riporta il puntatore all'inizio del file
            df_new = pd.read_csv(uploaded, sep=";")

        # 3️⃣ Normalizzo i nomi delle colonne (spazi, BOM, ecc.)
        df_new.columns = (
            df_new.columns
            .str.strip()
            .str.replace("\ufeff", "", regex=False)  # rimuove BOM UTF-8
        )

        expected_cols = {"Giocatore", "Squadra", "Prezzo"}

        if not expected_cols.issubset(df_new.columns):
            st.error(
                f"Il CSV deve contenere almeno le colonne: {expected_cols} "
                f"Colonne trovate: {list(df_new.columns)}"
            )
        else:
            st.session_state.players_df = df_new[list(expected_cols)]
            st.success("Giocatori caricati correttamente dal CSV.")

    except Exception as e:
        st.error(f"Errore nel leggere il CSV: {e}")


    st.markdown("---")
    st.subheader("Lista giocatori (modifica direttamente qui)")

    edited_df = st.data_editor(
        st.session_state.players_df,
        use_container_width=True,
        key="players_editor",
        column_config={
            "Giocatore": st.column_config.TextColumn("Giocatore"),
            "Squadra": st.column_config.SelectboxColumn(
                "Squadra",
                options=["XtremeTeam", "TheGang","Milan"],
                required=False,
            ),
            "Prezzo": st.column_config.NumberColumn("Prezzo", min_value=0),
        },
    )

    # Aggiorna lo stato
    st.session_state.players_df = edited_df

    st.download_button(
        "⬇️ Scarica giocatori in CSV",
        data=st.session_state.players_df.to_csv(index=False).encode("utf-8"),
        file_name="fantatennis_players.csv",
        mime="text/csv",
    )

# ------------------------------------------------------
# PAGINA 3: SQUADRE
# ------------------------------------------------------
if page == "👥 Squadre":
    st.title("👥 Gestione Squadre Fantatennis")

    if st.session_state.players_df.empty:
        st.warning("Prima devi definire qualche giocatore nella sezione **Giocatori**.")
    else:
        st.markdown(
            """
            Crea le squadre scegliendo:
            - Nome squadra
            - Nome allenatore / manager
            - Budget
            - **Esattamente 10 giocatori** in rosa
            """
        )

        with st.form("create_team_form"):
            col1, col2 = st.columns(2)
            with col1:
                team_name = st.text_input("Nome squadra")
                manager_name = st.text_input("Allenatore / Manager")
            with col2:
                budget = st.number_input("Budget", min_value=0, value=100, step=1)

            players_list = st.multiselect(
                "Scegli i 10 giocatori per la rosa (ordine = priorità titolari)",
                options=st.session_state.players_df["Giocatore"].tolist(),
            )

            submitted = st.form_submit_button("💾 Salva / Aggiorna squadra")

        if submitted:
            if len(players_list) != 10:
                st.error("Devi selezionare esattamente **10 giocatori**.")
            else:
                # Calcolo costo totale
                df_players = st.session_state.players_df
                mask = df_players["Giocatore"].isin(players_list)
                total_cost = df_players.loc[mask, "Prezzo"].sum()

                if total_cost > budget:
                    st.error(
                        f"Rosa troppo costosa! Costo totale: {total_cost}, Budget: {budget}"
                    )
                else:
                    # Aggiorna se esiste già, altrimenti aggiungi
                    updated = False
                    for team in st.session_state.teams:
                        if team["name"] == team_name:
                            team["manager"] = manager_name
                            team["budget"] = budget
                            team["players"] = players_list
                            updated = True
                            break
                    if not updated:
                        st.session_state.teams.append(
                            {
                                "name": team_name,
                                "manager": manager_name,
                                "budget": budget,
                                "players": players_list,
                            }
                        )
                    st.success(
                        f"Squadra '{team_name}' salvata con successo! (Costo totale: {total_cost})"
                    )

        st.markdown("---")
        st.subheader("Squadre esistenti")

        if not st.session_state.teams:
            st.info("Nessuna squadra ancora definita.")
        else:
            # Costruiamo una tabella riassuntiva
            rows = []
            df_players = st.session_state.players_df
            for team in st.session_state.teams:
                mask = df_players["Giocatore"].isin(team["players"])
                total_cost = df_players.loc[mask, "Prezzo"].sum()
                rows.append(
                    {
                        "Team": team["name"],
                        "Manager": team["manager"],
                        "Budget": team["budget"],
                        "Cost": total_cost,
                        "N. Giocatori": len(team["players"]),
                        "Players (ordine = priorità titolari)": ", ".join(team["players"]),
                    }
                )
            teams_df = pd.DataFrame(rows)
            st.dataframe(teams_df, use_container_width=True)

if st.checkbox("Test connessione GitHub (admin)"):
    try:
        st.write("Players_df attuale:", st.session_state.players_df.head())
        save_players_df(st.session_state.players_df)
        st.success("Scrittura su GitHub OK ✅ (controlla il repo: data/players.csv)")
    except Exception as e:
        st.error(f"Errore GitHub API: {e}")


# ------------------------------------------------------
# PAGINA 4: TORNEO & PUNTEGGI
# ------------------------------------------------------
if page == "🏆 Torneo & Punteggi":
    st.title("🏆 Torneo & Calcolo Punteggi")

    if st.session_state.players_df.empty:
        st.warning("Prima devi definire i giocatori nella sezione **Giocatori**.")
    else:
        st.markdown(
            """
            Qui inserisci i risultati di un **singolo torneo**  
            per tutti (o alcuni) giocatori, e calcoliamo:
            - Punti per giocatore
            - Classifica torneo
            - Punti per squadra considerando:
              - **Slam** → 8 titolari (prime 8 posizioni in rosa)  
              - **1000** → 6 titolari (prime 6 posizioni in rosa)  
            Le riserve non sommano punti di default.
            """
        )

        st.subheader("Impostazioni Torneo")
        col1, col2 = st.columns(2)
        with col1:
            tournament_name = st.text_input("Nome torneo", value="Torneo Fantatennis")
        with col2:
            default_type = "Slam"
            tournament_type = st.selectbox(
                "Tipo torneo",
                options=ALL_TOURNAMENT_TYPES,
                index=ALL_TOURNAMENT_TYPES.index(default_type),
            )

        st.markdown("### Risultati per giocatore")

        # Se non esiste ancora un df per il torneo, inizializziamo
        if st.session_state.tournament_df is None:
            base_df = st.session_state.players_df.copy()
            base_df = base_df[["Giocatore"]].copy()
            base_df["Tournament Type"] = tournament_type
            base_df["Round Reached"] = "R32"
            base_df["Matches Won"] = 0
            base_df["Matches Lost"] = 0
            st.session_state.tournament_df = base_df

        edited_tournament_df = st.data_editor(
            st.session_state.tournament_df,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Giocatore": st.column_config.TextColumn("Giocatore", disabled=True),
                "Tournament Type": st.column_config.SelectboxColumn(
                    "Tournament Type",
                    options=ALL_TOURNAMENT_TYPES,
                ),
                "Round Reached": st.column_config.SelectboxColumn(
                    "Round Reached",
                    options=ALL_ROUNDS,
                ),
                "Matches Won": st.column_config.NumberColumn(
                    "Matches Won", min_value=0
                ),
                "Matches Lost": st.column_config.NumberColumn(
                    "Matches Lost", min_value=0
                ),
            },
            key="tournament_editor",
        )

        st.session_state.tournament_df = edited_tournament_df

        if st.button("📊 Calcola punteggi torneo"):
            df = st.session_state.tournament_df.copy()
            df["Fantapoints"] = df.apply(compute_fantapoints, axis=1)
            df_sorted = df.sort_values("Fantapoints", ascending=False)

            st.subheader(f"Classifica giocatori — {tournament_name}")
            st.dataframe(df_sorted, use_container_width=True)

            # Salviamo il df calcolato in sessione
            st.session_state.last_results_df = df_sorted

            # Se ci sono squadre, calcoliamo punteggio per squadra
            if st.session_state.teams:
                rows = []
                for team in st.session_state.teams:
                    team_players = team["players"]

                    if tournament_type == "Slam":
                        starters = team_players[:8]
                        reserves = team_players[8:10]  # non conteggiate
                    else:  # "1000"
                        starters = team_players[:6]
                        reserves = team_players[6:8]  # non conteggiate

                    # Filtra df per i soli giocatori di questa squadra
                    df_team = df_sorted[df_sorted["Giocatore"].isin(team_players)]

                    # Somma solo i titolari
                    team_points = df_team[df_team["Giocatore"].isin(starters)][
                        "Fantapoints"
                    ].sum()

                    rows.append(
                        {
                            "Team": team["name"],
                            "Manager": team["manager"],
                            "Tournament Type": tournament_type,
                            "Starters": ", ".join(starters),
                            "Reserves": ", ".join(reserves),
                            "Points (solo titolari)": team_points,
                        }
                    )

                teams_points_df = pd.DataFrame(rows).sort_values(
                    "Points (solo titolari)", ascending=False
                )

                st.subheader("Classifica squadre (torneo)")
                st.dataframe(teams_points_df, use_container_width=True)
            else:
                st.info(
                    "Nessuna squadra definita: vai nella sezione **Squadre** per creare le leghe."
                )

            # Download risultati
            csv_players = df_sorted.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Scarica punteggi giocatori (CSV)",
                data=csv_players,
                file_name=f"{tournament_name.replace(' ', '_')}_players_scores.csv",
                mime="text/csv",
            )

            if st.session_state.teams:
                csv_teams = teams_points_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Scarica punteggi squadre (CSV)",
                    data=csv_teams,
                    file_name=f"{tournament_name.replace(' ', '_')}_teams_scores.csv",
                    mime="text/csv",
                )

# ------------------------------------------------------
# PAGINA 5: STAGIONE & CLASSIFICA GLOBALE
# ------------------------------------------------------
if page == "📈 Stagione & Classifica":
    st.title("📈 Classifica Stagionale Fantatennis")

    st.markdown(
        '''
        Qui puoi simulare una **stagione completa** caricando i risultati reali
        dei tornei (Slam e 1000) e calcolando:
        - Punti totali per giocatore sulla stagione
        - Classifica finale delle squadre, usando le rose già definite nella pagina **Squadre**

        Ogni riga del dataset deve rappresentare la prestazione di un singolo **giocatore**
        in un singolo **torneo**.
        '''
    )

    REQUIRED_COLUMNS = [
        "Season",          # es. 2024
        "Tournament",      # es. Australian Open
        "Tournament Type", # Slam / 1000
        "Giocatore",       # nome del giocatore (deve combaciare con pagina Giocatori / Squadre)
        "Round Reached",   # Winner / Final / SF / QF / R16 / R32 / R64 / R128
    ]

    st.markdown("### 1️⃣ Carica risultati da CSV (opzionale)")

    uploaded_results = st.file_uploader(
        "Carica file CSV con i risultati di stagione",
        type=["csv"],
        key="results_uploader",
        help="Il file deve contenere almeno le colonne: " + ", ".join(REQUIRED_COLUMNS),
    )

    if uploaded_results is not None:
        try:
            df_upload = pd.read_csv(uploaded_results)

            missing = [c for c in REQUIRED_COLUMNS if c not in df_upload.columns]
            if missing:
                st.error(f"Mancano colonne obbligatorie nel file caricato: {missing}")
            else:
                st.info(f"File caricato con {len(df_upload)} righe.")
                if st.button("Usa questo file come risultati stagione (sostituisci tutto)"):
                    st.session_state.results_df = df_upload
                    st.success("Risultati stagione aggiornati dalla sorgente CSV.")
        except Exception as e:
            st.error(f"Errore nella lettura del CSV: {e}")

    st.markdown("---")
    st.markdown("### 2️⃣ Modifica / inserisci risultati manualmente")

    # Inizializza struttura di base se vuota
    if st.session_state.results_df is None or st.session_state.results_df.empty:
        base_cols = REQUIRED_COLUMNS + ["Matches Won", "Matches Lost"]
        st.session_state.results_df = pd.DataFrame(columns=base_cols)

    results_df = st.session_state.results_df

    st.caption(
        "Suggerimento: puoi usare questa tabella per aggiungere o correggere i risultati "
        "senza dover ricaricare ogni volta un CSV."
    )

    edited_results = st.data_editor(
        results_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Season": st.column_config.NumberColumn("Season", min_value=2000, max_value=2100),
            "Tournament": st.column_config.TextColumn("Tournament"),
            "Tournament Type": st.column_config.SelectboxColumn(
                "Tournament Type",
                options=ALL_TOURNAMENT_TYPES,
            ),
            "Giocatore": st.column_config.TextColumn("Giocatore"),
            "Round Reached": st.column_config.SelectboxColumn(
                "Round Reached",
                options=ALL_ROUNDS,
            ),
            "Matches Won": st.column_config.NumberColumn("Matches Won", min_value=0),
            "Matches Lost": st.column_config.NumberColumn("Matches Lost", min_value=0),
        },
        key="season_results_editor",
    )

    st.session_state.results_df = edited_results

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "⬇️ Scarica risultati (CSV)",
            data=st.session_state.results_df.to_csv(index=False).encode("utf-8"),
            file_name="fantatennis_results_season.csv",
            mime="text/csv",
        )
    with col_dl2:
        if st.button("💾 Salva risultati su GitHub (data/results.csv)"):
            try:
                save_results_df(st.session_state.results_df)
                st.success("Risultati salvati su GitHub ✅")
            except Exception as e:
                st.error(f"Errore nel salvataggio su GitHub: {e}")

    st.markdown("---")
    st.markdown("### 3️⃣ Calcola classifica stagione")

    df_res = st.session_state.results_df.copy()
    if df_res.empty:
        st.info("Nessun risultato disponibile: carica o inserisci qualche riga per iniziare.")
    else:
        # Normalizziamo il tipo torneo (es. 'SLAM' -> 'Slam')
        df_res["Tournament Type"] = df_res["Tournament Type"].astype(str).str.strip().str.title()

        # Filtro per stagione se la colonna esiste
        if "Season" in df_res.columns:
            seasons = sorted(df_res["Season"].dropna().unique())
            selected_seasons = st.multiselect(
                "Seleziona le stagioni da includere",
                options=seasons,
                default=seasons,
            )
            if selected_seasons:
                df_res = df_res[df_res["Season"].isin(selected_seasons)]

        # Calcolo fantapunti riga per riga
        if "Matches Won" not in df_res.columns:
            df_res["Matches Won"] = 0
        if "Matches Lost" not in df_res.columns:
            df_res["Matches Lost"] = 0

        df_res["Matches Won"] = df_res["Matches Won"].fillna(0).astype(int)
        df_res["Matches Lost"] = df_res["Matches Lost"].fillna(0).astype(int)
        df_res["Fantapoints"] = df_res.apply(compute_fantapoints, axis=1)

        st.subheader("Classifica giocatori (stagionale)")
        players_season = (
            df_res.groupby("Giocatore", as_index=False)["Fantapoints"]
            .sum()
            .rename(columns={"Fantapoints": "Totale Fantapoints"})
            .sort_values("Totale Fantapoints", ascending=False)
        )
        st.dataframe(players_season, use_container_width=True)

        # Calcolo punti per squadra se sono definite
        if not st.session_state.teams:
            st.info("Nessuna squadra definita: vai nella pagina **Squadre** per crearle.")
        else:
            rows = []
            for team in st.session_state.teams:
                team_players = team.get("players", [])
                # Titolarità per tipo torneo
                starters_slam = team_players[:8]
                starters_1000 = team_players[:6]

                # Filtriamo i risultati solo per i giocatori in rosa
                df_team = df_res[df_res["Giocatore"].isin(team_players)].copy()
                if df_team.empty:
                    total_points = 0
                else:
                    # Applichiamo logica titolari per ogni riga
                    def _is_starter(row):
                        if row["Tournament Type"] == "Slam":
                            return row["Giocatore"] in starters_slam
                        elif row["Tournament Type"] == "1000":
                            return row["Giocatore"] in starters_1000
                        return False

                    df_team["IsStarter"] = df_team.apply(_is_starter, axis=1)
                    total_points = df_team.loc[df_team["IsStarter"], "Fantapoints"].sum()

                rows.append(
                    {
                        "Team": team["name"],
                        "Manager": team["manager"],
                        "Totale punti stagione (solo titolari)": int(total_points),
                    }
                )

            teams_season = pd.DataFrame(rows).sort_values(
                "Totale punti stagione (solo titolari)", ascending=False
            )

            st.subheader("Classifica squadre (stagionale)")
            st.dataframe(teams_season, use_container_width=True)
