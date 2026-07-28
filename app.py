import io
import os
import random
import sqlite3
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import pandas as pd
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Gestion des Audits 5S & Auto Maintenance",
    page_icon="📋",
    layout="wide"
)

DB_NAME = "audits_database.db"

# ==============================================================================
# PARTIE 1 : BACK-END & BASE DE DONNÉES (SQLITE) & UTILITAIRES
# ==============================================================================

def get_db_connection():
    """Crée et retourne une connexion à la base de données SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise les tables de la base de données et insère les paramètres par défaut."""
    conn = get_db_connection()
    c = conn.cursor()

    # Table Historique des Audits
    c.execute("""
        CREATE TABLE IF NOT EXISTS historique_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idp TEXT,
            type_audit TEXT,
            auditeur TEXT,
            zone TEXT,
            equipe TEXT,
            semaine INTEGER,
            annee INTEGER,
            date_audit TEXT,
            score_pourcentage REAL,
            nb_ok INTEGER,
            nb_nok INTEGER,
            total_questions INTEGER
        )
    """)

    # Table Questions / Checklists
    c.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_audit TEXT,
            categorie TEXT,
            intitule TEXT
        )
    """)

    # Table Auditeurs
    c.execute("""
        CREATE TABLE IF NOT EXISTS auditeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT
        )
    """)

    # Table Zones / Îlots (5S)
    c.execute("""
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT
        )
    """)

    # Table Équipements / Machines (AM)
    c.execute("""
        CREATE TABLE IF NOT EXISTS equipements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT
        )
    """)

    # Table Emails Destinataires
    c.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            email TEXT
        )
    """)

    # Table Configuration (Mot de passe Admin, SMTP, etc.)
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            cle TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)

    conn.commit()

    # Initialisation des paramètres par défaut s'ils n'existent pas
    c.execute("SELECT COUNT(*) FROM config WHERE cle = 'admin_password'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO config (cle, valeur) VALUES ('admin_password', 'admin123')")
        c.execute("INSERT INTO config (cle, valeur) VALUES ('smtp_server', 'smtp.gmail.com')")
        c.execute("INSERT INTO config (cle, valeur) VALUES ('smtp_port', '587')")
        c.execute("INSERT INTO config (cle, valeur) VALUES ('smtp_user', '')")
        c.execute("INSERT INTO config (cle, valeur) VALUES ('smtp_password', '')")
        conn.commit()

    # Seeding initial des données si les tables sont vides
    c.execute("SELECT COUNT(*) FROM auditeurs")
    if c.fetchone()[0] == 0:
        auditeurs_defaut = ["Jean Dupont", "Marie Curie", "Pierre Martin", "Sophie Bernard"]
        for a in auditeurs_defaut:
            c.execute("INSERT INTO auditeurs (nom) VALUES (?)", (a,))

    c.execute("SELECT COUNT(*) FROM zones")
    if c.fetchone()[0] == 0:
        zones_defaut = ["Zone Assemblage A", "Zone Conditionnement", "Atelier Usinage", "Magasin Stock"]
        for z in zones_defaut:
            c.execute("INSERT INTO zones (nom) VALUES (?)", (z,))

    c.execute("SELECT COUNT(*) FROM equipements")
    if c.fetchone()[0] == 0:
        eq_defaut = ["Presse Hydraulique P01", "Ligne de Robotique R02", "Convoyeur Principal C03", "Machine CNC M04"]
        for eq in eq_defaut:
            c.execute("INSERT INTO equipements (nom) VALUES (?)", (eq,))

    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        seed_default_questions(c)

    conn.commit()
    conn.close()

def seed_default_questions(cursor):
    """Popule la base de données avec la checklist 5S et Auto Maintenance standard."""
    qs_5s = [
        ("S1 – DÉBARRASSER", "Absence d'outils, pièces ou objets inutiles dans la zone."),
        ("S1 – DÉBARRASSER", "Seul le matériel strictement nécessaire au poste est présent."),
        ("S2 – RANGER", "Chaque outil a une place définie et identifiée (marquage/ombre)."),
        ("S2 – RANGER", "Les voies de circulation et passages sont dégagés et matérialisés."),
        ("S3 – TENIR PROPRE", "Le sol, les tables de travail et les machines sont propres."),
        ("S3 – TENIR PROPRE", "Les poubelles et bacs de recyclage sont vidés régulièrement."),
        ("S4 – STANDARDISER", "Les règles de rangement et consignes visuelles sont affichées et lisibles."),
        ("S5 – MAINTENIR", "L'audit précédent a donné lieu à des actions correctives réalisées.")
    ]
    for cat, q in qs_5s:
        cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES ('5S', ?, ?)", (cat, q))

    qs_am = [
        ("État du poste de travail", "L'équipement est exempt de fuites d'huile, d'eau ou d'air."),
        ("Kit AM et EPI", "Les équipements de protection individuelle (EPI) sont disponibles et portés."),
        ("Standard d'AM", "Les points de graissage et niveaux de fluide sont conformes aux repères."),
        ("Réalisation des Tâches", "Les opérations de nettoyage et d'inspection de premier niveau sont effectuées."),
        ("Traçabilité et Enregistrement", "La fiche de suivi de maintenance autonome est renseignée à jour.")
    ]
    for cat, q in qs_am:
        cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES ('AM', ?, ?)", (cat, q))

def get_config_val(cle):
    """Récupère une valeur de configuration depuis la BD."""
    conn = get_db_connection()
    row = conn.execute("SELECT valeur FROM config WHERE cle = ?", (cle,)).fetchone()
    conn.close()
    return row['valeur'] if row else ""

def set_config_val(cle, valeur):
    """Met à jour une valeur de configuration dans la BD."""
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)", (cle, valeur))
    conn.commit()
    conn.close()

def get_items(table_name):
    """Récupère la liste complète des enregistrements d'une table."""
    conn = get_db_connection()
    items = conn.execute(f"SELECT * FROM {table_name} ORDER BY id ASC").fetchall()
    conn.close()
    return items

def add_item(table_name, columns, values):
    """Ajoute un enregistrement dans une table."""
    conn = get_db_connection()
    placeholders = ", ".join(["?"] * len(values))
    cols_str = ", ".join(columns)
    conn.execute(f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()

def delete_item(table_name, item_id):
    """Supprime un enregistrement d'une table par son ID."""
    conn = get_db_connection()
    conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_questions_dict(type_audit):
    """Retourne un dictionnaire {categorie: [liste de questions]} pour le type d'audit donné."""
    conn = get_db_connection()
    rows = conn.execute("SELECT categorie, intitule FROM questions WHERE type_audit = ? ORDER BY id ASC", (type_audit,)).fetchall()
    conn.close()
    
    questions_dict = {}
    for r in rows:
        cat, q = r['categorie'], r['intitule']
        if cat not in questions_dict:
            questions_dict[cat] = []
        questions_dict[cat].append(q)
    return questions_dict

def save_audit_in_history(idp, type_audit, auditeur, zone, equipe, semaine, annee, score, ok, nok, total):
    """Enregistre le résultat global d'un audit dans l'historique."""
    conn = get_db_connection()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO historique_audits (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_audit, score_pourcentage, nb_ok, nb_nok, total_questions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (idp, type_audit, auditeur, zone, equipe, semaine, annee, now_str, score, ok, nok, total))
    conn.commit()
    conn.close()

def convert_df_to_excel(df):
    """Convertit un DataFrame Pandas en binaire Excel (.xlsx)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique Audits')
    return output.getvalue()

# --- FERTILISATION & GÉNÉRATION DU PDF RAPPORT ---
def generate_pdf_report(audit_title, idp, auditeur, zone, equipe, semaine, annee, reponses, questions_dict, taux, nb_ok, nb_nok, total_questions):
    """Génère un rapport PDF stylisé et retourne le buffer binaire."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=12,
        alignment=0
    )
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        leading=14
    )
    cat_style = ParagraphStyle(
        'CategoryTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#ffffff'),
        spaceBefore=0,
        spaceAfter=0
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12
    )

    story = []

    # En-tête du document
    story.append(Paragraph(f"<b>RAPPORT D'AUDIT : {audit_title.upper()}</b>", title_style))
    story.append(Spacer(1, 10))

    # Tableau Métadonnées
    meta_data = [
        [
            Paragraph(f"<b>IDP :</b> {idp}", meta_style),
            Paragraph(f"<b>Auditeur :</b> {auditeur}", meta_style)
        ],
        [
            Paragraph(f"<b>Zone / Équipement :</b> {zone}", meta_style),
            Paragraph(f"<b>Équipe :</b> {equipe}", meta_style)
        ],
        [
            Paragraph(f"<b>Période :</b> Semaine {semaine} / {annee}", meta_style),
            Paragraph(f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[270, 270])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    # Banner de Résultat / Score
    score_color = colors.HexColor('#16a34a') if taux >= 80 else colors.HexColor('#dc2626')
    score_data = [[
        Paragraph(f"<font color='white'><b>TAUX DE CONFORMITÉ : {taux}%</b> ({nb_ok} OK / {nb_nok} NOK - Total : {total_questions})</font>", ParagraphStyle('Score', parent=styles['Heading2'], alignment=1))
    ]]
    t_score = Table(score_data, colWidths=[540])
    t_score.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), score_color),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_score)
    story.append(Spacer(1, 15))

    # Tableau détaillé du questionnaire
    q_counter = 0
    for cat, questions in questions_dict.items():
        # Ligne d'en-tête de catégorie
        cat_data = [[Paragraph(f"<b>{cat}</b>", cat_style), ""]]
        t_cat = Table(cat_data, colWidths=[400, 140])
        t_cat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0f172a')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('SPAN', (0, 0), (1, 0))
        ]))
        story.append(t_cat)

        table_rows = [["#", "Critère / Question", "Statut", "Commentaire / Photo"]]
        for q in questions:
            q_counter += 1
            rep = reponses.get(q_counter, {"statut": "Non évalué", "comment": "", "photo": None})
            
            statut_str = rep["statut"] or "Non évalué"
            statut_color = "green" if statut_str.startswith("✓") else ("red" if statut_str.startswith("✕") else "black")
            
            statut_p = Paragraph(f"<font color='{statut_color}'><b>{statut_str}</b></font>", cell_style)
            q_p = Paragraph(q, cell_style)
            c_p = Paragraph(rep["comment"] if rep["comment"] else "-", cell_style)

            # Inclusion de la photo si présente
            img_element = Paragraph("-", cell_style)
            if rep["photo"] is not None:
                try:
                    img_data = rep["photo"].read()
                    rep["photo"].seek(0)
                    img_io = io.BytesIO(img_data)
                    img_element = RLImage(img_io, width=60, height=45)
                except Exception:
                    img_element = Paragraph("[Photo Erreur]", cell_style)

            comment_cell = [c_p]
            if rep["photo"] is not None:
                comment_cell.append(Spacer(1, 4))
                comment_cell.append(img_element)

            table_rows.append([str(q_counter), q_p, statut_p, comment_cell])

        t_q = Table(table_rows, colWidths=[25, 235, 110, 170])
        t_q.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_q)
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- ENVOI D'EMAIL AVEC PIÈCE JOINTE ---
def send_email_with_pdf(pdf_bytes, audit_title, idp, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_questions, recipients):
    """Envoie le rapport PDF généré par email via le serveur SMTP configuré."""
    smtp_server = get_config_val("smtp_server")
    smtp_port = get_config_val("smtp_port")
    smtp_user = get_config_val("smtp_user")
    smtp_password = get_config_val("smtp_password")

    if not smtp_server or not smtp_user or not smtp_password:
        return False, "⚠️ Configuration SMTP incomplète dans les Paramètres Admin."

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"[{audit_title}] {zone} - Semaine {semaine}/{annee} (Résultat : {taux}%)"

    body = f"""Bonjour,

Veuillez trouver ci-joint le rapport détaillé pour l'audit suivant :

• Type d'audit : {audit_title}
• Identifiant (IDP) : {idp}
• Auditeur : {auditeur}
• Zone / Équipement : {zone}
• Équipe : {equipe}
• Période : Semaine {semaine} / {annee}
• Score de conformité : {taux}% ({nb_ok} OK / {nb_nok} NOK sur {total_questions} questions)

Cordialement,
Système de Gestion des Audits
"""
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header('Content-Disposition', 'attachment', filename=f"Rapport_Audit_{type_code_filename(audit_title)}_{zone}_S{semaine}.pdf")
    msg.attach(attachment)

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()
        return True, "✅ Email envoyé avec succès aux destinataires !"
    except Exception as e:
        return False, f"❌ Erreur lors de l'envoi de l'e-mail : {str(e)}"

def type_code_filename(title):
    return "5S" if "5S" in title else "AM"

# Initialisation systématique de la BD au démarrage
init_db()


# ==============================================================================
# PARTIE 2 : INTERFACE UTILISATEUR & NAVIGATION STREAMLIT
# ==============================================================================

# --- CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    
    .s-header { display: flex; align-items: center; gap: 10px; margin-top: 25px; margin-bottom: 15px; }
    .badge-s { background-color: #0f172a; color: white; font-weight: 800; padding: 4px 10px; border-radius: 6px; font-size: 13px; }
    .s-title-text { font-size: 16px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px; }
    
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
    .info-card { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
    .info-label { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
    .info-val { font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 2px; }
    
    .score-banner { background-color: #0f172a; color: white; border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0; }
    .score-percent { font-size: 56px; font-weight: 900; line-height: 1; margin-bottom: 6px; }
    .score-subtitle { font-size: 12px; font-weight: 800; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; }
    .score-detail { font-size: 14px; font-weight: 600; margin-top: 8px; color: #cbd5e1; }
    
    div.stButton > button { border-radius: 8px; font-weight: 700; }

    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 6px;
    }

    div[data-testid="stRadio"] label {
        background-color: #ffffff;
        border: 2px solid #cbd5e1;
        border-radius: 10px;
        padding: 10px 16px !important;
        font-weight: 700 !important;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    div[data-testid="stRadio"] label:nth-of-type(1):has(input:checked) {
        background-color: #f0fdf4 !important;
        border-color: #16a34a !important;
        color: #15803d !important;
    }

    div[data-testid="stRadio"] label:nth-of-type(2):has(input:checked) {
        background-color: #fef2f2 !important;
        border-color: #dc2626 !important;
        color: #b91c1c !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("📌 Menu")
page = st.sidebar.radio("Navigation", ["📋 Audit 5S Hebdo", "🛠️ Audit Auto Maintenance", "📊 Historique des Audits", "⚙️ Paramètres / Admin"])

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# ==============================================================================
# PAGE : HISTORIQUE DES AUDITS
# ==============================================================================
if page == "📊 Historique des Audits":
    st.title("📊 Historique des Audits Réalisés")

    conn = get_db_connection()
    df_history = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
    conn.close()

    if df_history.empty:
        st.info("Aucun audit n'a encore été enregistré dans l'historique.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            type_filter = st.multiselect("Filtrer par type d'audit :", options=df_history['type_audit'].unique(), default=df_history['type_audit'].unique())
        with col_f2:
            zone_filter = st.multiselect("Filtrer par zone / équipement :", options=df_history['zone'].unique(), default=df_history['zone'].unique())

        filtered_df = df_history[
            (df_history['type_audit'].isin(type_filter)) & 
            (df_history['zone'].isin(zone_filter))
        ]

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Nombre total d'audits", len(filtered_df))
        moyenne_score = filtered_df['score_pourcentage'].mean() if not filtered_df.empty else 0
        kpi2.metric("Moyenne Conformité (%)", f"{moyenne_score:.1f}%")
        kpi3.metric("Dernier audit", filtered_df['date_audit'].iloc[0] if not filtered_df.empty else "N/A")

        st.markdown("---")

        df_display = filtered_df.rename(columns={
            'idp': 'IDP',
            'type_audit': 'Type Audit',
            'auditeur': 'Auditeur',
            'zone': 'Zone / Équipement',
            'equipe': 'Équipe',
            'semaine': 'Semaine',
            'annee': 'Année',
            'date_audit': 'Date & Heure',
            'score_pourcentage': 'Résultat (%)',
            'nb_ok': 'OK',
            'nb_nok': 'NOK',
            'total_questions': 'Total Questions'
        })

        col_tbl, col_exp = st.columns([4, 1])
        with col_exp:
            excel_data = convert_df_to_excel(df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone / Équipement', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK', 'Total Questions']])
            st.download_button(
                label="📥 Exporter vers Excel",
                data=excel_data,
                file_name=f"historique_audits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.dataframe(
            df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone / Équipement', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK']],
            use_container_width=True,
            hide_index=True
        )

# ==============================================================================
# PAGE : PARAMÈTRES / ADMIN
# ==============================================================================
elif page == "⚙️ Paramètres / Admin":
    st.title("⚙️ Paramètres de l'application")

    if not st.session_state.admin_authenticated:
        st.subheader("🔒 Accès Administrateur")
        input_pwd = st.text_input("Saisissez le mot de passe de configuration :", type="password")
        
        if st.button("Se connecter", use_container_width=True):
            if input_pwd == get_config_val("admin_password"):
                st.session_state.admin_authenticated = True
                st.success("Accès autorisé !")
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect.")
    
    else:
        if st.sidebar.button("🚪 Déconnexion Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()

        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "✏️ Édition / Admin Audits", 
            "📝 Checklists / Questions", 
            "👤 Auditeurs", 
            "🏭 Zones / Îlots (5S)", 
            "⚙️ Équipements / Machines (AM)",
            "📧 Emails Responsables", 
            "🔐 Sécurité & SMTP"
        ])

        # --- TAB 1 : ÉDITION ET SUPPRESSION DE L'HISTORIQUE ---
        with tab1:
            st.subheader("🛠️ Gérer / Modifier l'Historique des Audits")
            
            conn = get_db_connection()
            df_audits = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
            conn.close()
            
            if df_audits.empty:
                st.info("Aucun audit à modifier ou supprimer.")
            else:
                subtab_edit, subtab_del = st.tabs(["✏️ Modifier un Audit", "🗑️ Supprimer un Audit"])
                
                liste_options = {
                    row['id']: f"ID #{row['id']} | [{row['type_audit']}] {row['zone']} - Semaine {row['semaine']}/{row['annee']} ({row['auditeur']})"
                    for _, row in df_audits.iterrows()
                }

                with subtab_edit:
                    selected_id = st.selectbox("Sélectionnez l'audit à modifier :", options=list(liste_options.keys()), format_func=lambda x: liste_options[x], key="edit_select_box")
                    row_data = df_audits[df_audits['id'] == selected_id].iloc[0]

                    with st.form(key=f"form_edit_audit_{selected_id}"):
                        c_a, c_b = st.columns(2)
                        with c_a:
                            e_type = st.selectbox("Type d'audit", ["5S", "AM"], index=0 if row_data['type_audit'] == "5S" else 1)
                            e_auditeur = st.text_input("Auditeur", value=str(row_data['auditeur']))
                            e_zone = st.text_input("Zone / Machine", value=str(row_data['zone']))
                            e_equipe = st.text_input("Équipe", value=str(row_data['equipe']))
                        
                        with c_b:
                            e_semaine = st.number_input("Semaine", value=int(row_data['semaine']), min_value=1, max_value=53)
                            e_annee = st.number_input("Année", value=int(row_data['annee']), min_value=2020, max_value=2035)
                            e_ok = st.number_input("Nombre de OK", value=int(row_data['nb_ok']), min_value=0)
                            e_nok = st.number_input("Nombre de NOK", value=int(row_data['nb_nok']), min_value=0)

                        new_total = e_ok + e_nok
                        new_score = round((e_ok / new_total * 100), 1) if new_total > 0 else 0.0

                        st.info(f"📊 **Nouveau Total :** {new_total} questions  |  🎯 **Nouveau Taux :** {new_score}%")

                        if st.form_submit_button("💾 Enregistrer les modifications", use_container_width=True):
                            conn_update = get_db_connection()
                            c_db = conn_update.cursor()
                            c_db.execute("""
                                UPDATE historique_audits 
                                SET type_audit = ?, auditeur = ?, zone = ?, equipe = ?, semaine = ?, annee = ?, nb_ok = ?, nb_nok = ?, total_questions = ?, score_pourcentage = ?
                                WHERE id = ?
                            """, (e_type, e_auditeur, e_zone, e_equipe, e_semaine, e_annee, e_ok, e_nok, new_total, new_score, selected_id))
                            conn_update.commit()
                            conn_update.close()
                            st.success(f"✅ Audit #{selected_id} mis à jour avec succès !")
                            st.rerun()

                with subtab_del:
                    selected_id_del = st.selectbox("Sélectionnez l'audit à supprimer :", options=list(liste_options.keys()), format_func=lambda x: liste_options[x], key="del_select_box")
                    st.warning("⚠️ Attention, la suppression est definitiva.")
                    
                    if st.button("❌ Supprimer définitivement l'audit", type="primary"):
                        conn_del = get_db_connection()
                        c_db = conn_del.cursor()
                        c_db.execute("DELETE FROM historique_audits WHERE id = ?", (selected_id_del,))
                        conn_del.commit()
                        conn_del.close()
                        st.success(f"✅ Audit #{selected_id_del} supprimé !")
                        st.rerun()

        # --- TAB 2 : CHECKLISTS & QUESTIONS ---
        with tab2:
            st.subheader("📝 Modifier les Checklists d'Audit")
            selected_audit_type = st.selectbox("Choisir l'audit à modifier :", ["5S", "AM"], format_func=lambda x: "Audit 5S Hebdo" if x == "5S" else "Audit Auto Maintenance (AM)")
            
            conn = get_db_connection()
            q_items = conn.execute("SELECT * FROM questions WHERE type_audit = ? ORDER BY id ASC", (selected_audit_type,)).fetchall()
            conn.close()

            cats = list(dict.fromkeys([q['categorie'] for q in q_items])) if q_items else []
            
            st.markdown("---")
            st.markdown("#### Questions existantes :")
            if not q_items:
                st.info("Aucune question enregistrée pour cet audit.")
            else:
                for c in cats:
                    st.markdown(f"**📌 {c}**")
                    cat_qs = [q for q in q_items if q['categorie'] == c]
                    for q_row in cat_qs:
                        col1, col2 = st.columns([5, 1])
                        col1.write(f"• {q_row['intitule']}")
                        if col2.button("❌", key=f"del_q_{q_row['id']}"):
                            delete_item("questions", q_row['id'])
                            st.rerun()

            st.markdown("---")
            st.markdown("#### ➕ Ajouter une nouvelle question")
            
            existing_cats = cats if cats else (["S1 – DÉBARRASSER", "S2 – RANGER", "S3 – TENIR PROPRE", "S4 – STANDARDISER", "S5 – MAINTENIR"] if selected_audit_type == "5S" else ["État du poste de travail", "Kit AM et EPI", "Standard d'AM", "Réalisation des Tâches", "Traçabilité et Enregistrement"])
            
            cat_option = st.radio("Catégorie :", ["Catégorie existante", "Créer une nouvelle catégorie"], horizontal=True)
            
            if cat_option == "Catégorie existante":
                cat_val = st.selectbox("Sélectionner la catégorie :", options=existing_cats)
            else:
                cat_val = st.text_input("Nom de la nouvelle catégorie :", key="new_cat_name")

            new_q_text = st.text_area("Intitulé du critère / question d'audit :", key="new_q_text")
            
            if st.button("Ajouter la question", use_container_width=True):
                if cat_val and new_q_text.strip():
                    add_item("questions", ["type_audit", "categorie", "intitule"], [selected_audit_type, cat_val.strip(), new_q_text.strip()])
                    st.rerun()
                else:
                    st.error("Veuillez remplir la catégorie et l'intitulé.")

            st.markdown("---")
            if st.button("🔄 Réinitialiser les questions par défaut (5S & AM)"):
                conn = get_db_connection()
                conn.execute("DELETE FROM questions")
                seed_default_questions(conn.cursor())
                conn.commit()
                conn.close()
                st.success("Checklists réinitialisées aux valeurs d'origine !")
                st.rerun()

        # --- TAB 3 : AUDITEURS ---
        with tab3:
            st.subheader("Liste des Auditeurs")
            for a in get_items("auditeurs"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"• **{a['nom']}**")
                if c2.button("❌", key=f"del_aud_{a['id']}"):
                    delete_item("auditeurs", a['id'])
                    st.rerun()
            st.markdown("---")
            new_aud = st.text_input("Nom & Prénom de l'auditeur", key="input_aud")
            if st.button("Ajouter l'auditeur"):
                if new_aud.strip():
                    add_item("auditeurs", ["nom"], [new_aud.strip()])
                    st.rerun()

        # --- TAB 4 : ZONES ---
        with tab4:
            st.subheader("Liste des Zones / Îlots (Pour Audit 5S)")
            for z in get_items("zones"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"• **{z['nom']}**")
                if c2.button("❌", key=f"del_zone_{z['id']}"):
                    delete_item("zones", z['id'])
                    st.rerun()
            st.markdown("---")
            new_z = st.text_input("Nom de la Zone / Îlot", key="input_zone")
            if st.button("Ajouter la zone"):
                if new_z.strip():
                    add_item("zones", ["nom"], [new_z.strip()])
                    st.rerun()

        # --- TAB 5 : ÉQUIPEMENTS ---
        with tab5:
            st.subheader("Liste des Équipements / Machines (Pour Audit AM)")
            for eq in get_items("equipements"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"• **{eq['nom']}**")
                if c2.button("❌", key=f"del_eq_{eq['id']}"):
                    delete_item("equipements", eq['id'])
                    st.rerun()
            st.markdown("---")
            new_eq = st.text_input("Nom de l'Équipement / Machine", key="input_eq")
            if st.button("Ajouter l'équipement"):
                if new_eq.strip():
                    add_item("equipements", ["nom"], [new_eq.strip()])
                    st.rerun()

        # --- TAB 6 : EMAILS ---
        with tab6:
            st.subheader("Adresses E-mails des Destinataires")
            for e in get_items("emails"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"• **{e['label']}** : `{e['email']}`")
                if c2.button("❌", key=f"del_email_{e['id']}"):
                    delete_item("emails", e['id'])
                    st.rerun()
            st.markdown("---")
            lbl = st.text_input("Libellé / Rôle (ex: Chef d'atelier)", key="input_lbl")
            em = st.text_input("Adresse e-mail", key="input_em")
            if st.button("Ajouter l'adresse e-mail"):
                if lbl.strip() and em.strip():
                    add_item("emails", ["label", "email"], [lbl.strip(), em.strip()])
                    st.rerun()

        # --- TAB 7 : SÉCURITÉ & SMTP ---
        with tab7:
            st.subheader("🔑 Changer le mot de passe d'accès aux Paramètres")
            current_pwd = get_config_val("admin_password")
            new_pwd = st.text_input("Nouveau mot de passe Admin", type="password", value=current_pwd)
            if st.button("Mettre à jour le mot de passe"):
                if new_pwd.strip():
                    set_config_val("admin_password", new_pwd.strip())
                    st.success("✅ Mot de passe mis à jour !")
                else:
                    st.error("Le mot de passe ne peut pas être vide.")

            st.markdown("---")
            st.subheader("⚙️ Configuration SMTP (Envoi d'e-mails)")
            
            cfg_server = st.text_input("Serveur SMTP", value=get_config_val("smtp_server"))
            cfg_port = st.text_input("Port SMTP", value=get_config_val("smtp_port"))
            cfg_user = st.text_input("Utilisateur / E-mail expéditeur", value=get_config_val("smtp_user"))
            cfg_pass = st.text_input("Mot de passe SMTP / Application", type="password", value=get_config_val("smtp_password"))
            
            if st.button("Sauvegarder la configuration SMTP"):
                set_config_val("smtp_server", cfg_server.strip())
                set_config_val("smtp_port", cfg_port.strip())
                set_config_val("smtp_user", cfg_user.strip())
                set_config_val("smtp_password", cfg_pass.strip())
                st.success("✅ Configuration SMTP enregistrée !")

# ==============================================================================
# PAGES : AUDITS (5S & AUTO MAINTENANCE)
# ==============================================================================
else:
    db_auditeurs = [a['nom'] for a in get_items("auditeurs")]
    db_zones = [z['nom'] for z in get_items("zones")]
    db_equipements = [eq['nom'] for eq in get_items("equipements")]
    db_emails = get_items("emails")

    if page == "📋 Audit 5S Hebdo":
        audit_title = "Audit 5S Hebdo"
        type_code = "5S"
        prefix_key = "5s"
        location_label = "ZONE / ÎLOT"
        location_options = db_zones if db_zones else ["Aucune zone"]
    else:
        audit_title = "Audit Auto Maintenance"
        type_code = "AM"
        prefix_key = "am"
        location_label = "ÉQUIPEMENT / MACHINE"
        location_options = db_equipements if db_equipements else ["Aucun équipement"]

    questions_dict = get_questions_dict(type_code)
    total_questions = sum(len(q) for q in questions_dict.values())

    step_key = f"{prefix_key}_step"
    reponses_key = f"{prefix_key}_reponses"
    idp_key = f"{prefix_key}_idp"

    if step_key not in st.session_state: st.session_state[step_key] = 1
    if reponses_key not in st.session_state: st.session_state[reponses_key] = {}
    if idp_key not in st.session_state: st.session_state[idp_key] = f"022026301{random.randint(10,99)}"

    # ÉCRAN 1 : IDENTIFICATION
    if st.session_state[step_key] == 1:
        st.title(f"📋 {audit_title.upper()}")
        aud_sel = st.selectbox("AUDITEUR (NOM & PRÉNOM)", options=["— Sélectionner —"] + db_auditeurs)
        if st.button("Continuer →", use_container_width=True):
            if aud_sel == "— Sélectionner —":
                st.error("Sélectionnez un auditeur.")
            else:
                st.session_state[f"{prefix_key}_auditeur"] = aud_sel
                st.session_state[step_key] = 2
                st.rerun()

    # ÉCRAN 2 : PARAMÈTRES AUDIT
    elif st.session_state[step_key] == 2:
        if st.button("← Retour"):
            st.session_state[step_key] = 1
            st.rerun()
        st.title("PARAMÈTRES DE L'AUDIT")
        st.session_state[f"{prefix_key}_zone"] = st.selectbox(location_label, options=location_options)
        st.session_state[f"{prefix_key}_equipe"] = st.selectbox("ÉQUIPE", options=["Équipe1", "Équipe2", "Équipe3", "Équipe Nuit"])
        st.session_state[f"{prefix_key}_semaine"] = st.number_input("SEMAINE (ISO)", value=datetime.now().isocalendar()[1], min_value=1, max_value=53)
        st.session_state[f"{prefix_key}_annee"] = st.number_input("ANNÉE", value=datetime.now().year, min_value=2020, max_value=2035)
        if st.button("Démarrer l'audit →", use_container_width=True):
            st.session_state[step_key] = 3
            st.rerun()

    # ÉCRAN 3 : QUESTIONNAIRE
    elif st.session_state[step_key] == 3:
        st.title(audit_title)
        
        if total_questions == 0:
            st.warning("⚠️ Aucune question enregistrée pour cet audit. Rendez-vous dans les Paramètres/Admin pour ajouter des questions.")
        else:
            q_counter = 0
            for category, questions in questions_dict.items():
                st.markdown(f'<div class="s-header"><span class="badge-s">📌</span><span class="s-title-text">{category}</span></div>', unsafe_allow_html=True)
                
                for q in questions:
                    q_counter += 1
                    st.markdown(f"**{q_counter}. {q}**")
                    
                    statut = st.radio(
                        f"hidden_label_{q_counter}", 
                        ["✓ OK / Conforme", "✕ NOK / Non conforme"], 
                        key=f"{prefix_key}_q_{q_counter}", 
                        index=None,
                        label_visibility="collapsed"
                    )

                    comment = st.text_input("Commentaire / Action corrective :", key=f"{prefix_key}_c_{q_counter}")
                    photo = st.file_uploader("📷 Prendre une photo / Joindre une image :", type=["jpg", "jpeg", "png"], key=f"{prefix_key}_p_{q_counter}")

                    st.session_state[reponses_key][q_counter] = {
                        "statut": statut,
                        "comment": comment,
                        "photo": photo
                    }
                    st.markdown("---")

            if st.button("✅ Valider et Terminer l'Audit", use_container_width=True):
                reponses = st.session_state[reponses_key]
                non_repondues = [idx for idx, rep in reponses.items() if rep["statut"] is None]

                if non_repondues:
                    st.error(f"⚠️ Veuillez répondre à toutes les questions avant de valider (Questions non renseignées : {non_repondues}).")
                else:
                    st.session_state[step_key] = 4
                    st.rerun()

    # ÉCRAN 4 : RÉSUMÉ & ENVOI PDF
    elif st.session_state[step_key] == 4:
        reponses = st.session_state[reponses_key]
        nb_ok = sum(1 for rep in reponses.values() if rep["statut"] and rep["statut"].startswith("✓"))
        nb_nok = total_questions - nb_ok
        taux = round((nb_ok / total_questions) * 100, 1) if total_questions > 0 else 0

        auditeur = st.session_state.get(f"{prefix_key}_auditeur", "Inconnu")
        zone = st.session_state.get(f"{prefix_key}_zone", "Non définie")
        equipe = st.session_state.get(f"{prefix_key}_equipe", "Non définie")
        semaine = st.session_state.get(f"{prefix_key}_semaine", 1)
        annee = st.session_state.get(f"{prefix_key}_annee", datetime.now().year)
        idp = st.session_state.get(idp_key, "N/A")

        # Sauvegarde automatique dans l'historique de la BD
        save_audit_in_history(idp, type_code, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_questions)

        st.markdown(f"""
            <div class="score-banner">
                <div class="score-percent">{taux}%</div>
                <div class="score-subtitle">Taux de Conformité - {audit_title}</div>
                <div class="score-detail">{nb_ok} OK / {nb_nok} NOK (Total : {total_questions} questions)</div>
            </div>
        """, unsafe_allow_html=True)

        lbl_card = "ÉQUIPEMENT / MACHINE" if type_code == "AM" else "ZONE / ÎLOT"

        st.markdown(f"""
            <div class="info-grid">
                <div class="info-card"><div class="info-label">AUDITEUR</div><div class="info-val">{auditeur}</div></div>
                <div class="info-card"><div class="info-label">{lbl_card}</div><div class="info-val">{zone}</div></div>
                <div class="info-card"><div class="info-label">ÉQUIPE</div><div class="info-val">{equipe}</div></div>
                <div class="info-card"><div class="info-label">PÉRIODE</div><div class="info-val">Semaine {semaine} / {annee}</div></div>
            </div>
        """, unsafe_allow_html=True)

        # Génération du fichier PDF en mémoire
        pdf_bytes = generate_pdf_report(
            audit_title, idp, auditeur, zone, equipe, semaine, annee, 
            reponses, questions_dict, taux, nb_ok, nb_nok, total_questions
        )

        col_pdf, col_email = st.columns(2)
        with col_pdf:
            st.download_button(
                label="📄 Télécharger le Rapport PDF",
                data=pdf_bytes,
                file_name=f"Rapport_{type_code}_{zone}_S{semaine}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with col_email:
            st.subheader("📧 Envoi par e-mail")
            if not db_emails:
                st.warning("Aucune adresse e-mail configurée dans les paramètres.")
            else:
                email_list = [e['email'] for e in db_emails]
                selected_emails = st.multiselect("Sélectionner les destinataires :", options=email_list, default=email_list)
                
                if st.button("📤 Envoyer le rapport par email", use_container_width=True):
                    if not selected_emails:
                        st.error("Veuillez choisir au moins un destinataire.")
                    else:
                        with st.spinner("Envoi de l'e-mail en cours..."):
                            success, msg = send_email_with_pdf(
                                pdf_bytes, audit_title, idp, auditeur, zone, 
                                equipe, semaine, annee, taux, nb_ok, nb_nok, total_questions, selected_emails
                            )
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)

        st.markdown("---")
        if st.button("🔄 Démarrer un nouvel audit", use_container_width=True):
            st.session_state[step_key] = 1
            st.session_state[reponses_key] = {}
            st.session_state[idp_key] = f"022026301{random.randint(10,99)}"
            st.rerun()
