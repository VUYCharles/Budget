import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime
import io
import math
from PIL import Image
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas

# --- CONFIGURATION ET DOSSIERS ---
st.set_page_config(page_title="Budget Pro Local", layout="wide")

DATA_FILE = "depenses_v3.csv"
CONFIG_FILE = "config_tags_v2.csv"
UPLOAD_DIR = "factures"

if not os.path.exists(UPLOAD_DIR): 
    os.makedirs(UPLOAD_DIR)

# --- CHARGEMENT DES DONNEES ---
def load_data():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["Date", "Description", "Montant", "Tag", "Facture"]).to_csv(DATA_FILE, index=False)
    if not os.path.exists(CONFIG_FILE):
        pd.DataFrame([["Besoins", "Pourcentage", 50], ["Loisirs", "Pourcentage", 30]], 
                     columns=["Tag", "Type", "Valeur"]).to_csv(CONFIG_FILE, index=False)
    return pd.read_csv(DATA_FILE), pd.read_csv(CONFIG_FILE)

df_depenses, df_config = load_data()

# --- FONCTIONS TECHNIQUES (PDF ET FILIGRANE HAUT CONTRASTE) ---

def create_adaptive_watermark(text, page_width, page_height):
    """Cree un filigrane visible partout via une technique de double trace (halo)."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    font_name = "Helvetica-Bold"
    font_size = 18 
    can.setFont(font_name, font_size)
    
    text_width = can.stringWidth(text, font_name, font_size)
    
    # Espacement securise pour eviter les superpositions
    step_x = int(text_width + 120) 
    step_y = 160
    
    # Zone de couverture basee sur la diagonale
    diagonal = int(math.sqrt(page_width**2 + page_height**2))
    
    can.saveState()
    can.translate(page_width / 2, page_height / 2)
    can.rotate(35)
    
    for i, x in enumerate(range(-diagonal, diagonal, step_x)):
        for j, y in enumerate(range(-diagonal, diagonal, step_y)):
            # Halo Blanc (lisibilite sur fond sombre)
            can.setFillAlpha(0.25)
            can.setFillColorRGB(1, 1, 1)
            can.drawCentredString(x + 1, y - 1, text) 
            
            # Texte Noir (lisibilite sur fond clair)
            can.setFillAlpha(0.30)
            can.setFillColorRGB(0, 0, 0)
            can.drawCentredString(x, y, text)
            
    can.restoreState()
    can.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]

def compile_to_pdf(files_list, watermark_text=None):
    merger = PdfWriter()
    temp_merged = io.BytesIO()
    
    files_count = 0
    for file_path in files_list:
        if not os.path.exists(file_path): continue
        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.pdf':
                merger.append(file_path)
            elif ext in ['.png', '.jpg', '.jpeg']:
                img = Image.open(file_path).convert('RGB')
                img_pdf = io.BytesIO()
                img.save(img_pdf, format='PDF')
                img_pdf.seek(0)
                merger.append(img_pdf)
            files_count += 1
        except: continue
                
    if files_count == 0: return None
    
    merger.write(temp_merged)
    merger.close()
    temp_merged.seek(0)

    if watermark_text and watermark_text.strip():
        reader = PdfReader(temp_merged)
        writer = PdfWriter()
        for page in reader.pages:
            try:
                w = float(page.mediabox.width)
                h = float(page.mediabox.height)
                wm_page = create_adaptive_watermark(watermark_text, w, h)
                page.merge_page(wm_page)
                writer.add_page(page)
            except:
                writer.add_page(page)
        
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()
    
    return temp_merged.getvalue()

# --- 1. BARRE LATERALE (PARAMETRES) ---
st.sidebar.title("Configuration")
rev_mensuel = st.sidebar.number_input("Revenu mensuel (EUR)", min_value=0.0, value=1441.0, step=10.0)

with st.sidebar.expander("Gerer les etiquettes"):
    t_name = st.text_input("Nom de l'etiquette")
    t_type = st.selectbox("Type", ["Pourcentage", "Montant Fixe"])
    t_val = st.number_input("Valeur", min_value=0.0)
    if st.button("Ajouter l'etiquette"):
        if t_name:
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

# --- 2. FORMULAIRE DE DEPENSE ---
st.header("Nouvelle Depense")
with st.form("form_depense", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    desc = c1.text_input("Description")
    montant = c2.number_input("Montant (EUR)", min_value=0.0)
    tag_choisi = c3.selectbox("Etiquette", df_config["Tag"].values if not df_config.empty else ["Aucune"])
    facture_file = st.file_uploader("Facture (PDF, PNG, JPG)", type=['pdf', 'png', 'jpg', 'jpeg'])
    
    if st.form_submit_button("Enregistrer"):
        if desc and montant > 0:
            f_path = ""
            if facture_file:
                safe_name = "".join(c for c in facture_file.name if c.isalnum() or c in ('-','_','.'))
                f_path = os.path.join(UPLOAD_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}")
                with open(f_path, "wb") as f: f.write(facture_file.getbuffer())
            new_line = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), desc, montant, tag_choisi, f_path]], 
                                    columns=["Date", "Description", "Montant", "Tag", "Facture"])
            new_line.to_csv(DATA_FILE, mode='a', header=False, index=False)
            st.rerun()

# --- 3. CALCULS ET RESUME ---
budget_list = []
for _, row in df_config.iterrows():
    alloue = rev_mensuel * (row['Valeur'] / 100) if row['Type'] == "Pourcentage" else row['Valeur']
    depense = df_depenses[df_depenses["Tag"] == row['Tag']]["Montant"].sum()
    budget_list.append({"Tag": row['Tag'], "Alloue": alloue, "Depense": depense, "Reste": alloue - depense})

df_res = pd.DataFrame(budget_list)
total_depense = df_depenses["Montant"].sum()
solde_global = rev_mensuel - total_depense

st.divider()
col_s1, col_s2 = st.columns(2)
col_s1.metric("Solde Global Restant", f"{solde_global:.2f} EUR", delta=f"-{total_depense:.2f} EUR", delta_color="inverse")

# COULEURS ET LISIBILITE DES GRAPHIQUES
unique_tags = df_config["Tag"].unique()
tag_color_map = {tag: px.colors.qualitative.Pastel[i % 10] for i, tag in enumerate(unique_tags)}

def clean_pie(fig):
    # Changement de la couleur du texte en noir pour la lisibilite sur fond pastel
    fig.update_traces(
        textposition='outside', 
        textinfo='label+percent', 
        marker=dict(line=dict(color='#262730', width=2)),
        textfont=dict(color='black', size=14)
    )
    fig.update_layout(
        showlegend=False, 
        margin=dict(t=30, b=30, l=10, r=10),
        font=dict(color='black')
    )
    return fig

st.subheader("Analyse des enveloppes")
c_l, c_r = st.columns(2)
with c_l:
    if not df_res.empty:
        f1 = px.pie(df_res, values='Alloue', names='Tag', hole=0.5, color='Tag', color_discrete_map=tag_color_map, title="Objectifs")
        st.plotly_chart(clean_pie(f1), use_container_width=True)
with c_r:
    if not df_depenses.empty:
        f2 = px.pie(df_depenses, values='Montant', names='Tag', hole=0.5, color='Tag', color_discrete_map=tag_color_map, title="Reel")
        st.plotly_chart(clean_pie(f2), use_container_width=True)

if not df_res.empty:
    st.subheader("Suivi par enveloppe")
    m_cols = st.columns(len(df_res))
    for i, row in df_res.iterrows():
        with m_cols[i]:
            st.metric(row['Tag'], f"{row['Reste']:.2f} EUR", delta=f"Max: {row['Alloue']:.0f}EUR")
            st.progress(min(max(row['Depense'] / row['Alloue'], 0.0), 1.0) if row['Alloue'] > 0 else 0)

# --- 4. HISTORIQUE ET PDF ---
st.divider()
st.subheader("Historique des depenses")
selected_filter = st.selectbox("Filtrer par etiquette :", ["Toutes"] + list(df_config["Tag"].values))
view_df = df_depenses[df_depenses["Tag"] == selected_filter] if selected_filter != "Toutes" else df_depenses
st.dataframe(view_df.sort_values(by="Date", ascending=False), use_container_width=True)

if selected_filter != "Toutes":
    df_files = view_df[view_df["Facture"].notna() & (view_df["Facture"] != "")]
    if not df_files.empty:
        st.write("---")
        st.markdown(f"Compilation securisee : {selected_filter}")
        c_o1, c_o2 = st.columns([1, 2])
        use_watermark = c_o1.toggle("Appliquer filigrane contraste", value=True)
        w_text = c_o2.text_input("Texte libre :", value="Document exclusivement reserve a AIP") if use_watermark else None
        
        if st.button("Compiler le dossier PDF"):
            with st.spinner("Generation du PDF securise..."):
                pdf_bytes = compile_to_pdf(df_files["Facture"].tolist(), w_text)
                if pdf_bytes:
                    st.success("Dossier genere avec succes")
                    st.download_button("Telecharger le fichier", data=pdf_bytes, file_name=f"{selected_filter}_justificatifs.pdf")
    else:
        st.info("Aucun justificatif pour cette etiquette.")

st.divider()
st.markdown('<div style="text-align: center; color: gray;">Developpe par @vuycharles | Licence CC BY-NC-SA 4.0</div>', unsafe_allow_html=True)
