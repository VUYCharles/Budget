import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime

# --- CONFIGURATION ET DOSSIERS ---
st.set_page_config(page_title="Budget Pro Local", layout="wide")

DATA_FILE = "depenses_v3.csv"
CONFIG_FILE = "config_tags_v2.csv"
UPLOAD_DIR = "factures"

if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

def load_data():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["Date", "Description", "Montant", "Tag", "Facture"]).to_csv(DATA_FILE, index=False)
    if not os.path.exists(CONFIG_FILE):
        pd.DataFrame([["Besoins", "Pourcentage", 50], ["Loisirs", "Pourcentage", 30]], 
                     columns=["Tag", "Type", "Valeur"]).to_csv(CONFIG_FILE, index=False)
    return pd.read_csv(DATA_FILE), pd.read_csv(CONFIG_FILE)

# --- 1. GESTION DES ENTRÉES ---
df_depenses, df_config = load_data()

st.sidebar.title("Parametres")
revenu_mensuel = st.sidebar.number_input("Revenu mensuel (€)", min_value=0.0, value=1441.0, step=10.0)

with st.sidebar.expander("Gerer les etiquettes"):
    t_name = st.text_input("Nom de l'etiquette")
    t_type = st.selectbox("Type", ["Pourcentage", "Montant Fixe"])
    t_val = st.number_input("Valeur", min_value=0.0)
    if st.button("Enregistrer l'etiquette"):
        new_row = pd.DataFrame([[t_name, t_type, t_val]], columns=["Tag", "Type", "Valeur"])
        df_config = pd.concat([df_config[df_config['Tag'] != t_name], new_row], ignore_index=True)
        df_config.to_csv(CONFIG_FILE, index=False)
        st.rerun()

if not df_config.empty:
    with st.sidebar.expander("Supprimer une etiquette"):
        to_del = st.selectbox("Selectionner", df_config["Tag"].values)
        if st.button("Supprimer definitivement", type="primary"):
            df_config = df_config[df_config["Tag"] != to_del]
            df_config.to_csv(CONFIG_FILE, index=False)
            st.rerun()

st.header("Nouvelle Depense")
with st.form("form_depense", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    desc = c1.text_input("Description")
    montant = c2.number_input("Montant (€)", min_value=0.0)
    tag_choisi = c3.selectbox("Etiquette", df_config["Tag"].values if not df_config.empty else ["Aucune"])
    facture_file = st.file_uploader("Joindre facture (PDF, JPG)", type=['pdf', 'png', 'jpg'])
    
    if st.form_submit_button("Enregistrer la depense"):
        f_path = ""
        if facture_file:
            f_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{facture_file.name}")
            with open(f_path, "wb") as f: f.write(facture_file.getbuffer())
        
        new_line = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), desc, montant, tag_choisi, f_path]], 
                                columns=["Date", "Description", "Montant", "Tag", "Facture"])
        new_line.to_csv(DATA_FILE, mode='a', header=False, index=False)
        st.rerun()

# --- 2. CALCULS ---
budget_list = []
for _, row in df_config.iterrows():
    alloue = revenu_mensuel * (row['Valeur'] / 100) if row['Type'] == "Pourcentage" else row['Valeur']
    depense = df_depenses[df_depenses["Tag"] == row['Tag']]["Montant"].sum()
    budget_list.append({"Tag": row['Tag'], "Alloue": alloue, "Depense": depense, "Reste": alloue - depense})

df_res = pd.DataFrame(budget_list)
total_depense = df_depenses["Montant"].sum()
solde_global = revenu_mensuel - total_depense

# --- 3. AFFICHAGE ---
st.divider()
col_s1, col_s2 = st.columns(2)
col_s1.metric("Solde Global Restant", f"{solde_global:.2f} €", delta=f"Depense: -{total_depense:.2f} €", delta_color="inverse")

def clean_pie(fig):
    fig.update_traces(textposition='outside', textinfo='label+percent', textfont_size=15, marker=dict(line=dict(color='#262730', width=2)))
    fig.update_layout(showlegend=False, margin=dict(t=40, b=40, l=10, r=10), font=dict(size=14, color="white"))
    return fig

st.subheader("Analyse des enveloppes")
c_left, c_right = st.columns(2)

with c_left:
    st.write("**Repartition visee (Objectifs)**")
    f1 = px.pie(df_res, values='Alloue', names='Tag', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(clean_pie(f1), use_container_width=True)

with c_right:
    st.write("**Repartition reelle (Depenses)**")
    if not df_depenses.empty:
        f2 = px.pie(df_depenses, values='Montant', names='Tag', hole=0.5, color_discrete_sequence=px.colors.qualitative.Bold)
        st.plotly_chart(clean_pie(f2), use_container_width=True)
    else:
        st.info("Aucune depense enregistree.")

st.subheader("Etat par etiquette")
if not df_res.empty:
    m_cols = st.columns(len(df_res))
    for i, row in df_res.iterrows():
        with m_cols[i]:
            st.metric(row['Tag'], f"{row['Reste']:.2f} €", delta=f"Budget: {row['Alloue']}€")
            prog = min(max(row['Depense'] / row['Alloue'], 0.0), 1.0) if row['Alloue'] > 0 else 0
            st.progress(prog)

st.divider()
selected_filter = st.selectbox("Filtrer l'historique :", ["Toutes"] + list(df_config["Tag"].values))
view_df = df_depenses.copy()
if selected_filter != "Toutes":
    view_df = view_df[view_df["Tag"] == selected_filter]
st.dataframe(view_df.sort_values(by="Date", ascending=False), use_container_width=True)

# --- CRÉDITS (Bas de page) ---
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: gray; font-size: 0.8em;">
        Developpe par <a href="https://vuycharles.github.io" target="_blank" style="color: gray; text-decoration: none;">@vuycharles</a>
    </div>
    """, 
    unsafe_allow_html=True
)
