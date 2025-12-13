# players_gallery.py
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="FantaTennis • Players Gallery", layout="wide")

# ===== CONFIG =====
IMG_DIR = Path("andreapoi/FantaTennis/images")
PLACEHOLDER = IMG_DIR / "placeholder.png"

DEFAULT_CSV = Path("andreapoi/FantaTennis/data/md_players.csv")  # cambia in Path("players.csv") se lo hai in root
ID_COL = "id_player"
NAME_COL = "full_name"  # se non ce l'hai, userà player_id

EXTS = [".png", ".jpg", ".jpeg", ".webp"]


def resolve_image(player_id: str) -> Path:
    pid = str(player_id).strip()
    for ext in EXTS:
        p = IMG_DIR / f"{pid}{ext}"
        if p.exists():
            return p
    return PLACEHOLDER


def load_df(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_csv(uploaded)
    if DEFAULT_CSV.exists():
        return pd.read_csv(DEFAULT_CSV)
    return pd.DataFrame()


st.title("🖼️ Players Gallery (preview UI)")
st.caption("Anteprima di come appariranno le immagini dei giocatori su Streamlit (stile card/campioncino).")

with st.sidebar:
    st.header("Dati & Layout")

    uploaded = st.file_uploader("Carica anagrafica (CSV)", type=["csv"])
    st.caption("Se non carichi nulla, prova a leggere `data/players.csv` dal repo.")

    columns = st.slider("Colonne griglia", min_value=2, max_value=8, value=6)
    img_width = st.slider("Larghezza immagine (px)", min_value=60, max_value=220, value=120, step=10)

    only_real_images = st.checkbox("Mostra solo chi ha immagine reale", value=False)
    show_ids = st.checkbox("Mostra player_id", value=True)

    query = st.text_input("Cerca (nome o id)", "")

    st.divider()
    st.subheader("Debug paths")
    st.write("IMG_DIR exists:", IMG_DIR.exists())
    st.write("PLACEHOLDER exists:", PLACEHOLDER.exists())


df = load_df(uploaded)

if df.empty:
    st.info("Carica un CSV oppure metti un file `data/players.csv` nel repo.")
    st.stop()

df = df.copy()
df.columns = [c.strip() for c in df.columns]

if ID_COL not in df.columns:
    st.error(f"Nel CSV manca la colonna '{ID_COL}'. Colonne trovate: {list(df.columns)}")
    st.stop()

if NAME_COL not in df.columns:
    df[NAME_COL] = df[ID_COL].astype(str)

df[ID_COL] = df[ID_COL].astype(str).str.strip()
df[NAME_COL] = df[NAME_COL].astype(str).str.strip()

df["image_path"] = df[ID_COL].apply(lambda x: str(resolve_image(x)))
df["has_image"] = df["image_path"].apply(lambda p: Path(p) != PLACEHOLDER and Path(p).exists())

# filtri
view = df
if query.strip():
    q = query.lower().strip()
    view = view[
        view[ID_COL].str.lower().str.contains(q)
        | view[NAME_COL].str.lower().str.contains(q)
    ]

if only_real_images:
    view = view[view["has_image"]]

# metriche
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
        # "Card" semplice e pulita
        st.image(r["image_path"], width=img_width)
        st.markdown(f"**{r[NAME_COL]}**")
        if show_ids:
            st.caption(r[ID_COL])
