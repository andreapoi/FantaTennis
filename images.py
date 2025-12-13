# image_audit.py
import streamlit as st
import pandas as pd
from pathlib import Path

# =========================
# CONFIG
# =========================
IMG_DIR = Path("andreapoi/FantaTennis/images")
PLACEHOLDER = IMG_DIR / "placeholder.png"

# Se il tuo CSV è già nel repo, mettilo qui (opzionale)
DEFAULT_PLAYERS_CSV = Path("andreapoi/FantaTennis/data/md_players.csv")  # cambia in "players.csv" se lo hai in root

# Nome colonna ID (se nel tuo CSV si chiama diversamente, cambia qui)
PLAYER_ID_COL = "id_player"
# Nome colonna nome (opzionale)
PLAYER_NAME_COL = "player"

SUPPORTED_EXTS = [".png", ".jpg", ".jpeg", ".webp"]


# =========================
# HELPERS
# =========================
def resolve_image_path(player_id: str) -> Path:
    pid = str(player_id).strip()
    for ext in SUPPORTED_EXTS:
        p = IMG_DIR / f"{pid}{ext}"
        if p.exists():
            return p
    return PLACEHOLDER


def get_status(img_path: Path) -> str:
    return "OK" if img_path.exists() and img_path != PLACEHOLDER else "MISSING"


def load_players_df_from_repo() -> pd.DataFrame | None:
    if DEFAULT_PLAYERS_CSV.exists():
        try:
            return pd.read_csv(DEFAULT_PLAYERS_CSV)
        except Exception:
            return None
    return None


# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="FantaTennis • Image Audit", layout="wide")
st.title("🖼️ FantaTennis • Verifica immagini giocatori")

st.caption(
    "Controllo rapido: per ogni player_id verifica se esiste un file immagine in assets/players/ "
    "con estensione png/jpg/jpeg/webp. Se manca, viene usato placeholder.png."
)

with st.expander("Debug percorsi (apri se hai problemi su Streamlit Cloud)", expanded=False):
    st.write("IMG_DIR:", str(IMG_DIR), "exists:", IMG_DIR.exists())
    st.write("PLACEHOLDER:", str(PLACEHOLDER), "exists:", PLACEHOLDER.exists())
    if IMG_DIR.exists():
        st.write("Esempio file in IMG_DIR (max 30):", [p.name for p in IMG_DIR.glob("*")][:30])

st.divider()

# Sorgente dati: file nel repo o upload
left, right = st.columns([2, 1])

with right:
    st.subheader("Sorgente anagrafica")
    mode = st.radio("Caricamento", ["Upload CSV", "Usa CSV nel repo (se presente)"], index=0)
    st.caption("Il CSV deve contenere almeno la colonna player_id.")

df = None

if mode == "Usa CSV nel repo (se presente)":
    df = load_players_df_from_repo()
    if df is None:
        st.warning(f"Non ho trovato/letto correttamente: {DEFAULT_PLAYERS_CSV}. Passa a 'Upload CSV'.")
else:
    f = st.file_uploader("Carica anagrafica giocatori (CSV)", type=["csv"])
    if f:
        df = pd.read_csv(f)

if df is None:
    st.info("Carica un CSV oppure metti un CSV nel repo e seleziona la modalità 'Usa CSV nel repo'.")
    st.stop()

# Normalizza colonne
df = df.copy()
df.columns = [c.strip() for c in df.columns]

if PLAYER_ID_COL not in df.columns:
    st.error(f"Nel CSV manca la colonna '{PLAYER_ID_COL}'. Colonne trovate: {list(df.columns)}")
    st.stop()

if PLAYER_NAME_COL not in df.columns:
    df[PLAYER_NAME_COL] = ""

# Crea audit
df[PLAYER_ID_COL] = df[PLAYER_ID_COL].astype(str).str.strip()
df["image_path"] = df[PLAYER_ID_COL].apply(lambda x: str(resolve_image_path(x)))
df["status"] = df["image_path"].apply(lambda p: get_status(Path(p)))

ok = int((df["status"] == "OK").sum())
missing = int((df["status"] == "MISSING").sum())

m1, m2, m3 = st.columns(3)
m1.metric("Totale giocatori", len(df))
m2.metric("Immagini OK", ok)
m3.metric("Immagini mancanti", missing)

st.divider()

# Filtri
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    query = st.text_input("Cerca (player_id o nome)", "")
with c2:
    only_missing = st.checkbox("Solo mancanti", value=False)
with c3:
    preview_n = st.number_input("Anteprime", min_value=4, max_value=80, value=24, step=4)

view = df
if query.strip():
    q = query.lower().strip()
    view = view[
        view[PLAYER_ID_COL].astype(str).str.lower().str.contains(q)
        | view[PLAYER_NAME_COL].astype(str).str.lower().str.contains(q)
    ]
if only_missing:
    view = view[view["status"] == "MISSING"]

# Tabella
st.subheader("Tabella audit")
st.data_editor(
    view[[PLAYER_ID_COL, PLAYER_NAME_COL, "status", "image_path"]],
    hide_index=True,
    disabled=True,
    column_config={
        PLAYER_ID_COL: st.column_config.TextColumn("player_id"),
        PLAYER_NAME_COL: st.column_config.TextColumn("Nome"),
        "status": st.column_config.TextColumn("Status"),
        "image_path": st.column_config.TextColumn("Path"),
    },
)

# Anteprime
st.subheader("Anteprima immagini")
cols = st.columns(4)
head = view.head(int(preview_n))

for i, (_, r) in enumerate(head.iterrows()):
    with cols[i % 4]:
        st.image(r["image_path"], use_container_width=True)
        label = f"{r[PLAYER_ID_COL]}"
        if str(r[PLAYER_NAME_COL]).strip():
            label += f" • {r[PLAYER_NAME_COL]}"
        label += f" • {r['status']}"
        st.caption(label)

st.divider()

st.subheader("Note")
st.markdown(
    """
- Le immagini devono essere nel repo (es. `assets/players/`), altrimenti su Streamlit Cloud non le trova.
- Git non versiona cartelle vuote: assicurati che `assets/players/placeholder.png` sia committato.
- Se vuoi cambiare dove stanno le immagini, modifica solo `IMG_DIR`.
"""
)
