# players_gallery.py
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="FantaTennis • Players Gallery", layout="wide")

# ===== CONFIG =====
IMG_DIR = Path("images")
PLACEHOLDER = IMG_DIR / "placeholder.png"

DEFAULT_CSV = Path("data/md_players.csv")  # file anagrafica nel repo
ID_COL = "id_player"
NAME_COL = "full_name"  # se non c'è, userà ID_COL

EXTS = [".png", ".jpg", ".jpeg", ".webp"]


def resolve_image(player_id: str) -> Path:
    pid = str(player_id).strip()
    for ext in EXTS:
        p = IMG_DIR / f"{pid}{ext}"
        if p.exists():
            return p
    return PLACEHOLDER


def smart_read_csv(file_or_path) -> pd.DataFrame:
    """
    Legge CSV separati da ';' (tipico Excel/Italia) oppure ','.
    In più normalizza spazi nei nomi colonna.
    """
    last_err = None
    for sep in [";", ","]:
        try:
            df = pd.read_csv(file_or_path, sep=sep)
            df.columns = [c.strip() for c in df.columns]
            # Se il sep è sbagliato, spesso viene creata 1 sola colonna con dentro ';'
            if len(df.columns) == 1 and ";" in df.columns[0]:
                raise ValueError("Sembra un CSV separato da ';' letto con sep sbagliato.")
            return df
        except Exception as e:
            last_err = e
    raise last_err


def load_df(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        return smart_read_csv(uploaded)
    if DEFAULT_CSV.exists():
        return smart_read_csv(DEFAULT_CSV)
    return pd.DataFrame()


st.title("🖼️ Players Gallery (preview UI)")
st.caption("Anteprima di come appariranno le immagini dei giocatori su Streamlit (stile card/campioncino).")

with st.sidebar:
    st.header("Dati & Layout")

    uploaded = st.file_uploader("Carica anagrafica (CSV)", type=["csv"])
    st.caption("Se non carichi nulla, prova a leggere `data/md_players.csv` dal repo.")

    columns = st.slider("Colonne griglia", min_value=2, max_value=8, value=6)
    img_width = st.slider("Larghezza immagine (px)", min_value=60, max_value=220, value=120, step=10)

    only_real_images = st.checkbox("Mostra solo chi ha immagine reale", value=False)
    show_ids = st.checkbox("Mostra id_player", value=True)

    query = st.text_input("Cerca (nome o id)", "")

    st.divider()
    st.subheader("Debug paths")
    st.write("IMG_DIR exists:", IMG_DIR.exists())
    st.write("PLACEHOLDER exists:", PLACEHOLDER.exists())

# ===== LOAD DATA =====
try:
    df = load_df(uploaded)
except Exception as e:
    st.error(f"Errore lettura CSV: {e}")
    st.stop()

if df.empty:
    st.info("Carica un CSV oppure metti un file `data/md_players.csv` nel repo.")
    st.stop()

# Normalizza colonne
df = df.copy()
df.columns = [c.strip() for c in df.columns]

# Se il CSV è stato letto male, potresti avere una sola colonna tipo "id_player;player"
if ID_COL not in df.columns:
    st.error(
        f"Nel CSV manca la colonna '{ID_COL}'. "
        f"Colonne trovate: {list(df.columns)}\n\n"
        "Suggerimento: il CSV potrebbe usare ';' come separatore (Excel). "
        "Questo script prova già ';' e ',' automaticamente: controlla che il file abbia header corretti."
    )
    st.stop()

# Nome visualizzato
if NAME_COL not in df.columns:
    # Provo anche 'player' se esiste (spesso il tuo csv ha 'player')
    if "player" in df.columns:
        NAME_COL = "player"
    else:
        df[NAME_COL] = df[ID_COL].astype(str)

df[ID_COL] = df[ID_COL].astype(str).str.strip()
df[NAME_COL] = df[NAME_COL].astype(str).str.strip()

# ===== IMAGES =====
df["image_path"] = df[ID_COL].apply(lambda x: str(resolve_image(x)))
df["has_image"] = df["image_path"].apply(lambda p: Path(p).exists() and Path(p) != PLACEHOLDER)

# ===== FILTERS =====
view = df
if query.strip():
    q = query.lower().strip()
    view = view[
        view[ID_COL].str.lower().str.contains(q)
        | view[NAME_COL].str.lower().str.contains(q)
    ]

if only_real_images:
    view = view[view["has_image"]]

# ===== METRICS =====
c1, c2, c3 = st.columns(3)
c1.metric("Giocatori mostrati", len(view))
c2.metric("Con immagine reale", int(view["has_image"].sum()))
c3.metric("Placeholder", int((~view["has_image"]).sum()))

st.divider()

# ===== GALLERY =====
st.subheader("Preview cards")

grid = st.columns(columns)
for i, (_, r) in enumerate(view.iterrows()):
    with grid[i % columns]:
        st.image(r["image_path"], width=img_width)
        st.markdown(f"**{r[NAME_COL]}**")
        if show_ids:
            st.caption(r[ID_COL])
