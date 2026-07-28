import streamlit as st
if st.query_params.get("secret") == "download":
    st.download_button("Télécharger DB", open("audit_config.db", "rb"), "audit_config.db")

import sqlite3
import random
from datetime import datetime
import smtplib
import io
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# --- REPORTLAB IMPORTS POUR LE PDF ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Audits d'Atelier",
    page_icon="📋",
    layout="wide"
)

# --- BASE DE DONNÉES (PERSISTANCE DES PARAMÈTRES & HISTORIQUE) ---
def get_db_connection():
    conn = sqlite3.connect('audit_config.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS auditeurs (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS zones (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, email TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
    
    # Table Historique des Audits
    c.execute('''CREATE TABLE IF NOT EXISTS historique_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idp TEXT,
        type_audit TEXT NOT NULL,
        auditeur TEXT NOT NULL,
        zone TEXT NOT NULL,
        equipe TEXT,
        semaine INTEGER,
        annee INTEGER,
        date_audit TEXT,
        score_pourcentage REAL,
        nb_ok INTEGER,
        nb_nok INTEGER,
        total_questions INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        type_audit TEXT NOT NULL, 
        categorie TEXT NOT NULL, 
        intitule TEXT NOT NULL,
        ordre INTEGER DEFAULT 0
    )''')
    
    c.execute("SELECT COUNT(*) FROM auditeurs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO auditeurs (nom) VALUES (?)", [("BESSEM FEKIH",), ("Jean Dupont",)])
        
    c.execute("SELECT COUNT(*) FROM zones")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO zones (nom) VALUES (?)", [("AUTOMATISME",), ("LIGNE 1",), ("MAINTENANCE",)])

    c.execute("SELECT COUNT(*) FROM emails")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO emails (label, email) VALUES (?, ?)", [("Responsable Atelier", "yosri.fadhly@somfy.com"),])

    default_config = {
        "admin_password": "admin",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "yosri.fadhly@gmail.com",
        "smtp_password": "rzftdozwqntssiwa"
    }
    for k, v in default_config.items():
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))

    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        seed_default_questions(c)

    conn.commit()
    conn.close()

def seed_default_questions(cursor):
    q_5s = [
        ("S1 – DÉBARRASSER", "Est-ce qu'il y a du matériel / fournitures / machines / équipement Inutiles ?"),
        ("S1 – DÉBARRASSER", "Est-ce qu'il y a du matériel / fourniture / machines / équipement Endommagé ?"),
        ("S2 – RANGER", "Est-ce que chaque matériel a un emplacement défini ?"),
        ("S2 – RANGER", "Est-ce que chaque matériel est à son emplacement (zoning + affectation) ?"),
        ("S2 – RANGER", "Est-ce que rien ne traîne en dehors des emplacements ?"),
        ("S3 – TENIR PROPRE", "Est-ce que le poste et ses abords sont propres ?"),
        ("S3 – TENIR PROPRE", "Est-ce qu'il n'y a pas des fuites et/ou de salissures ?"),
        ("S4 – STANDARDISER", "Est-ce que le standard 5S est disponible ?"),
        ("S4 – STANDARDISER", "Est-ce que le point propreté standard est mis en place ?"),
        ("S5 – MAINTENIR", "Est-ce que la fiche d'audit quotidien est renseignée et les actions traitées ?"),
        ("S5 – MAINTENIR", "Quelles sont les dernières actions réalisées par le GAP ?")
    ]
    for cat, q in q_5s:
        cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES (?, ?, ?)", ("5S", cat, q))

    q_am = [
        ("État du poste de travail", "Le management visuel est présent et en place."),
        ("État du poste de travail", "Le poste est propre et organisé conformément aux standards."),
        ("État du poste de travail", "Aucun élément dangereux ou non conforme (fuite, câble dénudé, pièce au sol...)."),
        ("Kit AM et EPI", "Le kit AM est complet, conforme à la liste standardisée et identifié (numéro de ligne/poste)."),
        ("Kit AM et EPI", "Les EPI nécessaires sont disponibles, conformes et en bon état."),
        ("Kit AM et EPI", "Le kit est facilement accessible et ne gêne pas le flux de production."),
        ("Standard d'AM", "Un unique standard AM est affiché et accessible à proximité du poste."),
        ("Standard d'AM", "Les instructions correspondent bien à l'état actuel du poste (FI à jour)."),
        ("Réalisation des Tâches", "Les opérateurs réalisent les tâches selon le standard et dans l'ordre défini."),
        ("Réalisation des Tâches", "La fréquence de réalisation (quotidienne / hebdo / mensuelle) est respectée."),
        ("Réalisation des Tâches", "Les outils et EPI utilisés sont adaptés à chaque action d'AM et sont bien ceux prévus dans le standard."),
        ("Réalisation des Tâches", "Les opérateurs signalent les écarts observés (défauts, bruit, jeu, fuite...)."),
        ("Traçabilité et Enregistrement", "Les anomalies détectées sont enregistrées dans le QRCI."),
        ("Traçabilité et Enregistrement", "Les bons de travail sont émis lorsque nécessaire et transmis à la maintenance."),
        ("Traçabilité et Enregistrement", "Le tableau de bord AM (SIM, taux de complétion, anomalies...) est mis à jour regularly en mode projet."),
        ("Traçabilité et Enregistrement", "Les actions issues des audits AM précédents sont suivies en SIM PROD et clôturées.")
    ]
    for cat, q in q_am:
        cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES (?, ?, ?)", ("AM", cat, q))

init_db()

def get_config_val(key):
    conn = get_db_connection()
    res = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return res['value'] if res else ""

def set_config_val(key, value):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_items(table):
    conn = get_db_connection()
    items = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    return items

def add_item(table, columns, values):
    conn = get_db_connection()
    placeholders = ", ".join(["?"] * len(values))
    cols = ", ".join(columns)
    try:
        conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)
        conn.commit()
        st.toast("✅ Ajouté avec succès !")
    except sqlite3.IntegrityError:
        st.error("⚠️ Cet élément existe déjà.")
    finally:
        conn.close()

def delete_item(table, item_id):
    conn = get_db_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def save_audit_in_history(idp, type_audit, auditeur, zone, equipe, semaine, annee, score, nb_ok, nb_nok, total_q):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM historique_audits WHERE idp = ?", (idp,))
    if c.fetchone() is None:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute('''INSERT INTO historique_audits 
                    (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_audit, score_pourcentage, nb_ok, nb_nok, total_questions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_str, score, nb_ok, nb_nok, total_q))
        conn.commit()
    conn.close()

def get_questions_dict(type_audit):
    conn = get_db_connection()
    rows = conn.execute("SELECT categorie, intitule FROM questions WHERE type_audit = ? ORDER BY id ASC", (type_audit,)).fetchall()
    conn.close()
    
    questions_dict = {}
    for r in rows:
        cat = r['categorie']
        if cat not in questions_dict:
            questions_dict[cat] = []
        questions_dict[cat].append(r['intitule'])
    return questions_dict

# --- FONCTION DE GÉNÉRATION DU PDF ---
def generate_pdf_report(audit_title, idp, auditeur, zone, equipe, semaine, annee, reponses, questions_dict, taux, nb_ok, nb_nok, total_q):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#0f172a'), alignment=1)
    header_s_style = ParagraphStyle('HeaderSStyle', parent=styles['Heading3'], fontSize=11, leading=14, textColor=colors.HexColor('#ffffff'), backColor=colors.HexColor('#0f172a'), spaceBefore=8, spaceAfter=4, borderPadding=4)
    text_bold = ParagraphStyle('TextBold', parent=styles['Normal'], fontSize=9, leading=12, fontName='Helvetica-Bold')
    text_normal = ParagraphStyle('TextNormal', parent=styles['Normal'], fontSize=9, leading=12)
    text_comment = ParagraphStyle('TextComment', parent=styles['Italic'], fontSize=8, leading=10, textColor=colors.HexColor('#475569'))
    
    story.append(Paragraph(f"RAPPORT D'AUDIT - {audit_title.upper()}", title_style))
    story.append(Spacer(1, 6))
    
    info_data = [
        [Paragraph("<b>IDP :</b>", text_normal), Paragraph(str(idp), text_normal), Paragraph("<b>PÉRIODE :</b>", text_normal), Paragraph(f"Semaine {semaine} / {annee}", text_normal)],
        [Paragraph("<b>AUDITEUR :</b>", text_normal), Paragraph(str(auditeur), text_normal), Paragraph("<b>TAUX CONFORMITÉ :</b>", text_normal), Paragraph(f"<b>{taux}%</b> ({nb_ok} OK / {nb_nok} NOK)", text_normal)],
        [Paragraph("<b>ZONE / ÎLOT :</b>", text_normal), Paragraph(str(zone), text_normal), Paragraph("<b>ÉQUIPE :</b>", text_normal), Paragraph(str(equipe), text_normal)],
    ]
    
    t_info = Table(info_data, colWidths=[1.1*inch, 2.3*inch, 1.4*inch, 2.2*inch])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 10))
    
    q_counter = 0
    for category, questions in questions_dict.items():
        story.append(Paragraph(f"<b>{category}</b>", header_s_style))
        
        table_q_data = []
        for q in questions:
            q_counter += 1
            rep = reponses.get(q_counter, {})
            statut_txt = rep.get("statut", "Non répondu")
            comment_txt = rep.get("comment", "")
            photo_file = rep.get("photo", None)
            
            if statut_txt.startswith("✓"):
                status_p = Paragraph("<font color='#16a34a'><b>✓ OK / CONFORME</b></font>", text_normal)
            else:
                status_p = Paragraph("<font color='#dc2626'><b>✕ NOK / NON CONFORME</b></font>", text_normal)
            
            q_content = [Paragraph(q, text_bold)]
            if comment_txt:
                q_content.append(Paragraph(f"<i>Observation : {comment_txt}</i>", text_comment))
                
            img_element = ""
            if photo_file is not None:
                try:
                    photo_file.seek(0)
                    img_data = io.BytesIO(photo_file.read())
                    photo_file.seek(0)
                    img_element = RLImage(img_data, width=1.2*inch, height=0.9*inch)
                except Exception:
                    img_element = Paragraph("<i>Image non disponible</i>", text_comment)
            
            table_q_data.append([q_content, status_p, img_element])
            
        t_q = Table(table_q_data, colWidths=[4.2*inch, 1.4*inch, 1.4*inch])
        t_q.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_q)
        story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- FONCTION DE GÉNÉRATION DE L'EXCEL ---
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique Audits')
    output.seek(0)
    return output.getvalue()

# --- ENVOI DE EMAIL DE RAPPORT ---
def send_email_with_pdf(pdf_bytes, audit_title, idp, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_q, recipients):
    smtp_server = get_config_val("smtp_server")
    smtp_port = get_config_val("smtp_port")
    smtp_user = get_config_val("smtp_user")
    smtp_password = get_config_val("smtp_password")

    if not smtp_server or not smtp_user or not smtp_password:
        return False, "Configuration SMTP incomplète dans les paramètres."

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"[{audit_title.upper()}] Rapport d'Audit - {zone} (S{semaine}/{annee}) - Conformité : {taux}%"

    body = f"""Bonjour,

Veuillez trouver ci-joint le rapport PDF concernant l'audit ci-dessous :

• Audit : {audit_title}
• IDP : {idp}
• Auditeur : {auditeur}
• Zone / Îlot : {zone}
• Équipe : {equipe}
• Période : Semaine {semaine} / {annee}
• Taux de Conformité : {taux}% ({nb_ok} OK / {nb_nok} NOK sur {total_q} questions)

Cordialement,
Système d'Audit d'Atelier
"""
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header('Content-Disposition', 'attachment', filename=f"Rapport_{audit_title}_{zone}_S{semaine}.pdf")
    msg.attach(attachment)

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipients, msg.as_string())
        server.quit()
        return True, "E-mail envoyé avec succès !"
    except Exception as e:
        return False, f"Erreur lors de l'envoi de l'e-mail : {str(e)}"

# --- STYLES CSS PERSONNALISÉS ---
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
    .info-val-nok { font-size: 15px; font-weight: 800; color: #dc2626; margin-top: 2px; }
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
    div[data-testid="stRadio"] label:nth-of-type(1):has(input:checked) div[role="radio"] {
        background-color: #16a34a !important;
        border-color: #16a34a !important;
        box-shadow: inset 0 0 0 3px #ffffff !important;
    }

    div[data-testid="stRadio"] label:nth-of-type(2):has(input:checked) {
        background-color: #fef2f2 !important;
        border-color: #dc2626 !important;
        color: #b91c1c !important;
    }
    div[data-testid="stRadio"] label:nth-of-type(2):has(input:checked) div[role="radio"] {
        background-color: #dc2626 !important;
        border-color: #dc2626 !important;
        box-shadow: inset 0 0 0 3px #ffffff !important;
    }

    section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
        border-color: #e2e8f0 !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
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
            zone_filter = st.multiselect("Filtrer par zone :", options=df_history['zone'].unique(), default=df_history['zone'].unique())

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
            'zone': 'Zone',
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
            excel_data = convert_df_to_excel(df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK', 'Total Questions']])
            st.download_button(
                label="📥 Exporter vers Excel",
                data=excel_data,
                file_name=f"historique_audits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.dataframe(
            df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK']],
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

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "✏️ Édition / Admin Audits", 
            "📝 Checklists / Questions", 
            "👤 Auditeurs", 
            "🏭 Zones / Îlots", 
            "📧 Emails Responsables", 
            "🔐 Sécurité & SMTP"
        ])

        # --- ONGLET 1 : ÉDITION ET SUPPRESSION DES AUDITS HISTORIQUES ---
        with tab1:
            st.subheader("🛠️ Gérer / Modifier l'Historique des Audits")
            
            conn = get_db_connection()
            df_audits = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
            
            if df_audits.empty:
                st.info("Aucun audit à modifier ou supprimer.")
                conn.close()
            else:
                subtab_edit, subtab_del = st.tabs(["✏️ Modifier un Audit", "🗑️ Supprimer un Audit"])
                
                # SÉLECTION D'UN AUDIT
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
                            e_zone = st.text_input("Zone / Îlot", value=str(row_data['zone']))
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
                            c_db = conn.cursor()
                            c_db.execute("""
                                UPDATE historique_audits 
                                SET type_audit = ?, auditeur = ?, zone = ?, equipe = ?, semaine = ?, annee = ?, nb_ok = ?, nb_nok = ?, total_questions = ?, score_pourcentage = ?
                                WHERE id = ?
                            """, (e_type, e_auditeur, e_zone, e_equipe, e_semaine, e_annee, e_ok, e_nok, new_total, new_score, selected_id))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Audit #{selected_id} mis à jour avec succès !")
                            st.rerun()

                with subtab_del:
                    selected_id_del = st.selectbox("Sélectionnez l'audit à supprimer :", options=list(liste_options.keys()), format_func=lambda x: liste_options[x], key="del_select_box")
                    st.warning("⚠️ Attention, la suppression est définitive.")
                    
                    if st.button("❌ Supprimer définitivement l'audit", type="primary"):
                        c_db = conn.cursor()
                        c_db.execute("DELETE FROM historique_audits WHERE id = ?", (selected_id_del,))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Audit #{selected_id_del} supprimé !")
                        st.rerun()
                
                if conn: conn.close()

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

        with tab4:
            st.subheader("Liste des Zones")
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

        with tab5:
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

        with tab6:
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
    db_emails = get_items("emails")

    if page == "📋 Audit 5S Hebdo":
        audit_title = "Audit 5S Hebdo"
        type_code = "5S"
        prefix_key = "5s"
    else:
        audit_title = "Audit Auto Maintenance"
        type_code = "AM"
        prefix_key = "am"

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
        st.session_state[f"{prefix_key}_zone"] = st.selectbox("ZONE / ÎLOT", options=db_zones if db_zones else ["Aucune zone"])
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
                # Vérification si toutes les questions ont été répondues
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
        annee = st.session_state.get(f"{prefix_key}_annee", 2026)
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

        st.markdown(f"""
            <div class="info-grid">
                <div class="info-card"><div class="info-label">AUDITEUR</div><div class="info-val">{auditeur}</div></div>
                <div class="info-card"><div class="info-label">ZONE / ÎLOT</div><div class="info-val">{zone}</div></div>
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
