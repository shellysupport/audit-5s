import io
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen::canvas import Canvas  # ou reportlab.pdfgen import canvas

# --- INITIALISATION DE LA BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect("audit_config.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audits_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            zone TEXT,
            auditeur TEXT,
            score REAL,
            non_conformities TEXT
        )
    """
    )
    conn.commit()
    conn.close()

init_db()

# --- FONCTION DE GÉNÉRATION PDF AVEC REPORTLAB ---
def generate_pdf_report(audit_data):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    p.drawString(50, 750, "Rapport d'Audit 5S")
    p.drawString(50, 730, f"Date : {audit_data['date']}")
    p.drawString(50, 710, f"Zone : {audit_data['zone']}")
    p.drawString(50, 690, f"Auditeur : {audit_data['auditeur']}")
    p.drawString(50, 670, f"Score global : {audit_data['score']}%")
    
    p.drawString(50, 630, "Points non conformes enregistrés :")
    y = 610
    
    nc_list = audit_data['non_conformities'].split("\n") if audit_data['non_conformities'] else ["Aucune non-conformité."]
    for nc in nc_list:
        p.drawString(70, y, f"- {nc}")
        y -= 20
        if y < 50:
            p.showPage()
            y = 750
            
    p.save()
    buffer.seek(0)
    return buffer

# --- INTERFACE STREAMLIT ---
st.title("Gestion des Audits 5S")

menu = ["Nouvel Audit", "Historique & Régénération"]
choice = st.sidebar.selectbox("Navigation", menu)

if choice == "Nouvel Audit":
    st.header("Formulaire de Saisie d'Audit")
    zone = st.text_input("Zone auditée")
    auditeur = st.text_input("Nom de l'auditeur")
    
    st.subheader("Relevé des non-conformités")
    nc_input = st.text_area("Entrez les points non conformes (un par ligne)")
    score = st.slider("Score global (%)", 0, 100, 80)
    
    if st.button("Enregistrer et Générer le PDF"):
        if zone and auditeur:
            conn = sqlite3.connect("audit_config.db")
            cursor = conn.cursor()
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            cursor.execute(
                "INSERT INTO audits_history (date, zone, auditeur, score, non_conformities) VALUES (?, ?, ?, ?, ?)",
                (date_str, zone, auditeur, score, nc_input)
            )
            conn.commit()
            conn.close()
            
            st.success("Audit enregistré avec succès !")
            
            audit_record = {
                "date": date_str,
                "zone": zone,
                "auditeur": auditeur,
                "score": score,
                "non_conformities": nc_input
            }
            pdf_file = generate_pdf_report(audit_record)
            st.download_button(
                label="Télécharger le rapport PDF",
                data=pdf_file,
                file_name=f"audit_{zone}_{date_str.split()[0]}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Veuillez remplir les champs obligatoires (Zone et Auditeur).")

elif choice == "Historique & Régénération":
    st.header("Historique des Audits")
    
    conn = sqlite3.connect("audit_config.db")
    df_history = pd.read_sql("SELECT * FROM audits_history ORDER BY id DESC", conn)
    conn.close()
    
    if not df_history.empty:
        st.write("Cliquez ou sélectionnez un audit pour le consulter ou régénérer son PDF :")
        
        event = st.dataframe(
            df_history,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True
        )
        
        selected_rows = event.selection.get("rows", [])
        if selected_rows:
            row_index = selected_rows[0]
            selected_audit = df_history.iloc[row_index]
            
            st.divider()
            st.subheader(f"Détails de l'audit sélectionné (ID : {selected_audit['id']})")
            st.write(f"**Date :** {selected_audit['date']}")
            st.write(f"**Zone :** {selected_audit['zone']}")
            st.write(f"**Auditeur :** {selected_audit['auditeur']}")
            st.write(f"**Score :** {selected_audit['score']}%")
            st.write(f"**Non-conformités :**\n{selected_audit['non_conformities']}")
            
            audit_record = {
                "date": selected_audit['date'],
                "zone": selected_audit['zone'],
                "auditeur": selected_audit['auditeur'],
                "score": selected_audit['score'],
                "non_conformities": selected_audit['non_conformities']
            }
            pdf_file = generate_pdf_report(audit_record)
            
            st.download_button(
                label="📥 Régénérer et Télécharger le PDF",
                data=pdf_file,
                file_name=f"audit_{selected_audit['zone']}_{selected_audit['date'].split()[0]}.pdf",
                mime="application/pdf"
            )
    else:
        st.info("Aucun historique d'audit disponible pour le moment.")
