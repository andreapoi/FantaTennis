# fantatennis_app.py

import streamlit as st
import pandas as pd

# ------------------------------------------------------
# CONFIGURAZIONE APP
# ------------------------------------------------------
st.set_page_config(
    page_title="Fantatennis Manager",
    page_icon="🎾",
    layout="wide",
)

# Un po' di stile
CUSTOM_CSS = """
<style>
main.block-container {
    max-width: 1200px;
}
h1, h2, h3 {
    font-family: "Segoe UI", sans-serif;
}
div[data-testid="stSidebar"] {
    background-color: #0f172a;
    color: white;
}
div[data-testid="stSidebar"] h1, 
div[data-testid="stSidebar"] h2, 
div[data-testid="stSidebar"] h3 {
    color: white;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------
# INIZIALIZZAZIONE DELLO STATO
# ------------------------------------------------------
if "players_df" not in st.session_state:
    st.session_state.players_df = pd.DataFrame(
        columns=["Player", "Category", "Price"]
    )

if "teams" not in st.session_state:
    # ciascuna squadra: {"name": str, "manager": str, "budget": int, "players": [names]}
    st.session_state.teams = []

if "tournament_df" not in st.session_state:
    st.session_state.tournament_df = None

# ------------------------------------------------------
# COSTANTI: SISTEMA PUNTEGGI
# ------------------------------------------------------
# Solo due classi: Slam e 1000
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
    wins = wins or 0
    losses = losses or 0
    return wins * 6 + losses * 1


def compute_round_bonus(t_type: str, round_reached: str) -> int:
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
    ["🏠 Home & Regole", "👤 Giocatori", "👥 Squadre", "🏆 Torneo & Punteggi"],
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
            ### Come funziona l'app
            1. **Crea / carica i giocatori** nella sezione *Giocatori*  
            2. **Crea le squadre (10 giocatori fissi)** nella sezione *Squadre*  
            3. **Inserisci i risultati del torneo** nella sezione *Torneo & Punteggi*  
            4. L'app calcola:
               - Punti per ogni giocatore
               - Classifica del torneo
               - Classifica squadre in base a titolari (8/2 per Slam, 6/2 per 1000)
            """
        )
    with col2:
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
elif page == "👤 Giocatori":
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
            df = pd.read_csv(uploaded, sep=';')
            expected_cols = ["Giocatore", "Squadra", "Prezzo"]
            if all(col in df.columns for col in expected_cols):
                st.session_state.players_df = df[expected_cols].copy()
                st.success("Giocatori caricati correttamente.")
            else:
                st.error("Il CSV deve contenere le colonne: Giocatore, Squadra, Prezzo")
        except Exception as e:
            st.error(f"Errore nel caricamento: {e}")

    st.subheader("Modifica la lista giocatori")
    edited_df = st.data_editor(
        st.session_state.players_df,
        num_rows="dynamic",
        use_container_width=True,
        key="players_editor",
        column_config={
            "Giocatore": st.column_config.TextColumn("Giocatore"),
            "Squadra": st.column_config.SelectboxColumn(
                "Squadra",
                options=["XtremeTeam", "TheGang"],
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
elif page == "👥 Squadre":
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

        with st.form("crea_squadra_form"):
            col1, col2 = st.columns(2)
            with col1:
                team_name = st.text_input("Nome squadra")
                manager_name = st.text_input("Allenatore / Manager")
            with col2:
                default_budget = 200
                budget = st.number_input(
                    "Budget (crediti)",
                    min_value=0,
                    value=default_budget,
                    step=10,
                )

            players_list = st.multiselect(
                "Giocatori in rosa (devono essere esattamente 10)",
                options=list(st.session_state.players_df["Giocatore"]),
            )

            submitted = st.form_submit_button("💾 Crea / Aggiorna squadra")

        if submitted:
            # Calcolo costo rosa
            df = st.session_state.players_df
            mask = df["Giocatore"].isin(players_list)
            total_cost = df.loc[mask, "Prezzo"].sum()

            if not team_name:
                st.error("Inserisci un nome squadra.")
            elif len(players_list) != 10:
                st.error(
                    f"La rosa deve contenere esattamente 10 giocatori. "
                    f"Al momento ne hai selezionati {len(players_list)}."
                )
            elif total_cost > budget:
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
                    f"Squadra '{team_name}' salvata (costo rosa: {total_cost} crediti)."
                )

        st.subheader("Squadre create")
        if not st.session_state.teams:
            st.info("Nessuna squadra ancora definita.")
        else:
            # Costruiamo una tabella riassuntiva
            rows = []
            df_players = st.session_state.players_df
            for team in st.session_state.teams:
                mask = df_players["Player"].isin(team["players"])
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

# ------------------------------------------------------
# PAGINA 4: TORNEO & PUNTEGGI
# ------------------------------------------------------
elif page == "🏆 Torneo & Punteggi":
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
            base_df = base_df[["Player"]].copy()
            base_df["Tournament Type"] = tournament_type
            base_df["Round Reached"] = "R32"
            base_df["Matches Won"] = 0
            base_df["Matches Lost"] = 0
            st.session_state.tournament_df = base_df

        # Editor risultati
        edited_tournament_df = st.data_editor(
            st.session_state.tournament_df,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Player": st.column_config.TextColumn("Player", disabled=True),
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
                        # ultimi 2 fuori lista

                    mask_starters = df_sorted["Player"].isin(starters)
                    team_points = df_sorted.loc[mask_starters, "Fantapoints"].sum()

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
