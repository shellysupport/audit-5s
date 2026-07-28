import streamlit as st
if st.query_params.get("secret") == "download":
    st.download_button("Télécharger DB", open("audit_config.db", "rb"), "audit_config.db")

import sqlite3
import random
import json
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
    c.execute('''CREATE TABLE IF NOT EXISTS equipements (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, email TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
    
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
        total_questions INTEGER,
        details_json TEXT
    )''')

    try:
        c.execute("ALTER TABLE historique_audits ADD COLUMN details_json TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        type_audit TEXT NOT NULL, 
        categorie TEXT NOT NULL, 
        intitule TEXT NOT NULL,
        ordre INTEGER DEFAULT 0
    )''')
    
    c.execute("SELECT COUNT(*) FROM auditeurs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO auditeurs (nom) VALUES (?)", [("BESSEM FEKIH",), ("Yosri Fadhly",)])
        
    c.execute("SELECT COUNT(*) FROM zones")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO zones (nom) VALUES (?)", [("AUTOMATISME",), ("LIGNE 1",), ("UPS",)])

    c.execute("SELECT COUNT(*) FROM equipements")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO equipements (nom) VALUES (?)", [("FI506",), ("FI507",), ("Robot de Soudure 02",)])

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
        ("Traçabilité et Enregistrement", "Le tableau de bord AM (SIM, taux de complétion, anomalies...) est mis à jour régulièrement en mode projet."),
        ("Traçabilité et Enregistrement", "Les actions issues des audits AM précédents sont suivis en SIM PROD et clôturées.")
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

def save_audit_in_history(idp, type_audit, auditeur, zone, equipe, semaine, annee, score, nb_ok, nb_nok, total_q, reponses_dict_raw):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM historique_audits WHERE idp = ?", (idp,))
    if c.fetchone() is None:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        serializable_reponses = {}
        for k, v in reponses_dict_raw.items():
            serializable_reponses[str(k)] = {
                "statut": v.get("statut"),
                "comment": v.get("comment", "")
            }
        details_str = json.dumps(serializable_reponses)

        c.execute('''INSERT INTO historique_audits 
                    (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_audit, score_pourcentage, nb_ok, nb_nok, total_questions, details_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_str, score, nb_ok, nb_nok, total_q, details_str))
        conn.commit()
    conn.close()

def get_questions_with_ids(type_audit):
    conn = get_db_connection()
    rows = conn.execute("SELECT id, categorie, intitule FROM questions WHERE type_audit = ? ORDER BY id ASC", (type_audit,)).fetchall()
    conn.close()
    
    questions_dict = {}
    for r in rows:
        cat = r['categorie']
        if cat not in questions_dict:
            questions_dict[cat] = []
        questions_dict[cat].append((r['id'], r['intitule']))
    return questions_dict

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
def generate_pdf_report(audit_title, idp, auditeur, zone, equipe, semaine, annee, reponses, type_code, taux, nb_ok, nb_nok, total_q):
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
    
    label_emplacement = "<b>ÉQUIPEMENT :</b>" if "Auto" in audit_title or "AM" in audit_title else "<b>ZONE / ÎLOT :</b>"
    
    info_data = [
        [Paragraph("<b>IDP :</b>", text_normal), Paragraph(str(idp), text_normal), Paragraph("<b>PÉRIODE :</b>", text_normal), Paragraph(f"Semaine {semaine} / {annee}", text_normal)],
        [Paragraph("<b>AUDITEUR :</b>", text_normal), Paragraph(str(auditeur), text_normal), Paragraph("<b>TAUX CONFORMITÉ :</b>", text_normal), Paragraph(f"<b>{taux}%</b> ({nb_ok} OK / {nb_nok} NOK)", text_normal)],
        [Paragraph(label_emplacement, text_normal), Paragraph(str(zone), text_normal), Paragraph("<b>ÉQUIPE :</b>", text_normal), Paragraph(str(equipe), text_normal)],
    ]
    
    t_info = Table(info_data, colWidths=[1.3*inch, 2.1*inch, 1.4*inch, 2.2*inch])
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
    
    q_items_with_ids = get_questions_with_ids(type_code)
    
    for category, questions in q_items_with_ids.items():
        story.append(Paragraph(f"<b>{category}</b>", header_s_style))
        
        table_q_data = []
        for q_id, q_text in questions:
            # CORRECTION ROBUSTE DE LA RECHERCHE DES RÉPONSES (int ou str)
            rep = reponses.get(q_id, reponses.get(str(q_id), {}))
            if not rep:
                # Recherche par correspondance de texte si l'ID ne matche pas
                for k, v in reponses.items():
                    if str(k) == str(q_id):
                        rep = v
                        break

            statut_txt = str(rep.get("statut", ""))
            comment_txt = rep.get("comment", "")
            
            # Vérification rigoureuse du statut NOK
            if "NOK" in statut_txt.upper() or "NON" in statut_txt.upper():
                status_p = Paragraph("<font color='#dc2626'><b>✕ NOK / NON CONFORME</b></font>", text_normal)
            else:
                status_p = Paragraph("<font color='#16a34a'><b>✓ OK / CONFORME</b></font>", text_normal)
            
            q_content = [Paragraph(q_text, text_bold)]
            if comment_txt:
                q_content.append(Paragraph(f"<i>Observation : {comment_txt}</i>", text_comment))
                
            img_element = ""
            if isinstance(rep.get("photo"), io.BytesIO) or hasattr(rep.get("photo"), "read"):
                try:
                    photo_file = rep.get("photo")
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

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique Audits')
    output.seek(0)
    return output.getvalue()

def send_email_with_pdf(pdf_bytes, audit_title, idp, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_q, recipients):
    smtp_server = get_config_val("smtp_server")
    smtp_port = get_config_val("smtp_port")
    smtp_user = get_config_val("smtp_user")
    smtp_password = get_config_val("smtp_password")

    if not smtp_server or not smtp_user or not smtp_password:
        return False, "Configuration SMTP incomplète dans les paramètres."

    lbl_loc = "Équipement / Machine" if "AM" in audit_title or "Auto" in audit_title else "Zone / Îlot"

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"[{audit_title.upper()}] Rapport d'Audit - {zone} (S{semaine}/{annee}) - Conformité : {taux}%"

    body = f"""Bonjour,

Veuillez trouver ci-joint le rapport PDF concernant l'audit ci-dessous :

• Audit : {audit_title}
• IDP : {idp}
• Auditeur : {auditeur}
• {lbl_loc} : {zone}
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
    .score-banner { background-color: #0f172a; color: white; border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0; }
    .score-percent { font-size: 56px; font-weight: 900; line-height: 1; margin-bottom: 6px; }
    .score-subtitle { font-size: 12px; font-weight: 800; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; }
    .score-detail { font-size: 14px; font-weight: 600; margin-top: 8px; color: #cbd5e1; }
    div.stButton > button { border-radius: 8px; font-weight: 700; }

    div[data-testid="stRadio"] > div[role="radiogroup"] { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
    div[data-testid="stRadio"] label { background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 10px; padding: 10px 16px !important; font-weight: 700 !important; cursor: pointer; transition: all 0.2s ease; }
    div[data-testid="stRadio"] label:nth-of-type(1):has(input:checked) { background-color: #f0fdf4 !important; border-color: #16a34a !important; color: #15803d !important; }
    div[data-testid="stRadio"] label:nth-of-type(2):has(input:checked) { background-color: #fef2f2 !important; border-color: #dc2626 !important; color: #b91c1c !important; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.title("📌 Menu")
page = st.sidebar.radio("Navigation", ["📋 Audit 5S Hebdo", "🛠️ Audit Auto Maintenance", "📊 Historique des Audits", "⚙️ Paramètres / Admin"])

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# ==============================================================================
# PAGE : HISTORIQUE DES AUDITS & RÉGÉNÉRATION PDF
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
        st.subheader("📥 Téléchargement / Régénération des Rapports PDF par Audit")

        for _, row in filtered_df.iterrows():
            audit_label_type = "Audit 5S Hebdo" if row['type_audit'] == "5S" else "Audit Auto Maintenance"
            with st.expander(f"Audit #{row['id']} | IDP : {row['idp']} | [{row['type_audit']}] {row['zone']} - S{row['semaine']}/{row['annee']} ({row['auditeur']} - {row['score_pourcentage']}%)"):
                col_info1, col_info2, col_btn = st.columns([2, 2, 1])
                with col_info1:
                    st.write(f"**Date :** {row['date_audit']}")
                    st.write(f"**Équipe :** {row['equipe']}")
                with col_info2:
                    st.write(f"**Résultat :** {row['nb_ok']} OK / {row['nb_nok']} NOK")
                    st.write(f"**Conformité :** {row['score_pourcentage']}%")
                with col_btn:
                    if row['details_json']:
                        rep_dict = json.loads(row['details_json'])
                        
                        pdf_regen_bytes = generate_pdf_report(
                            audit_label_type, row['idp'], row['auditeur'], row['zone'], 
                            row['equipe'], row['semaine'], row['annee'], rep_dict, 
                            row['type_audit'], row['score_pourcentage'], row['nb_ok'], row['nb_nok'], row['total_questions']
                        )
                        st.download_button(
                            label="📄 Régénérer PDF",
                            data=pdf_regen_bytes,
                            file_name=f"Rapport_{row['type_audit']}_{row['zone']}_S{row['semaine']}.pdf",
                            mime="application/pdf",
                            key=f"regen_pdf_{row['id']}"
                        )
                    else:
                        st.warning("Détails non disponibles pour cet ancien audit.")

        st.markdown("---")
        excel_data = convert_df_to_excel(filtered_df[['idp', 'type_audit', 'auditeur', 'zone', 'equipe', 'semaine', 'annee', 'date_audit', 'score_pourcentage', 'nb_ok', 'nb_nok', 'total_questions']])
        st.download_button(
            label="📥 Exporter tout l'historique vers Excel",
            data=excel_data,
            file_name=f"historique_audits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
            "✏️ Édition / Admin Audits", "📝 Checklists", "👤 Auditeurs", "🏭 Zones", "⚙️ Équipements", "📧 Emails", "🔐 Sécurité & SMTP"
        ])

        with tab1:
            st.subheader("🛠️ Gérer / Modifier l'Historique des Audits")
            conn = get_db_connection()
            df_audits = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
            if df_audits.empty:
                st.info("Aucun audit à modifier.")
                conn.close()
            else:
                selected_id = st.selectbox("Sélectionnez l'audit à modifier :", options=df_audits['id'], format_func=lambda x: f"ID #{x}")
                row_data = df_audits[df_audits['id'] == selected_id].iloc[0]
                with st.form(key=f"form_edit_{selected_id}"):
                    e_type = st.selectbox("Type d'audit", ["5S", "AM"], index=0 if row_data['type_audit'] == "5S" else 1)
                    e_auditeur = st.text_input("Auditeur", value=str(row_data['auditeur']))
                    e_zone = st.text_input("Zone / Machine", value=str(row_data['zone']))
                    e_equipe = st.text_input("Équipe", value=str(row_data['equipe']))
                    e_semaine = st.number_input("Semaine", value=int(row_data['semaine']))
                    e_annee = st.number_input("Année", value=int(row_data['annee']))
                    e_ok = st.number_input("Nombre de OK", value=int(row_data['nb_ok']))
                    e_nok = st.number_input("Nombre de NOK", value=int(row_data['nb_nok']))
                    
                    if st.form_submit_button("💾 Enregistrer"):
                        new_total = e_ok + e_nok
                        new_score = round((e_ok / new_total * 100), 1) if new_total > 0 else 0
                        conn.execute("UPDATE historique_audits SET type_audit=?, auditeur=?, zone=?, equipe=?, semaine=?, annee=?, nb_ok=?, nb_nok=?, total_questions=?, score_pourcentage=? WHERE id=?", 
                                     (e_type, e_auditeur, e_zone, e_equipe, e_semaine, e_annee, e_ok, e_nok, new_total, new_score, selected_id))
                        conn.commit()
                        conn.close()
                        st.success("Modifications enregistrées !")
                        st.rerun()
                if conn: conn.close()

        with tab2:
            st.subheader("📝 Modifier les Checklists")
            selected_audit_type = st.selectbox("Audit :", ["5S", "AM"])
            q_items = get_questions_dict(selected_audit_type)
            for cat, qs in q_items.items():
                st.markdown(f"**{cat}**")
                for q in qs:
                    st.write(f"• {q}")
            
            new_cat = st.text_input("Nouvelle Catégorie")
            new_q = st.text_area("Nouvelle Question")
            if st.button("Ajouter la question"):
                if new_cat and new_q:
                    add_item("questions", ["type_audit", "categorie", "intitule"], [selected_audit_type, new_cat, new_q])
                    st.rerun()

        with tab3:
            for a in get_items("auditeurs"):
                c1, c2 = st.columns([4, 1])
                c1.write(a['nom'])
                if c2.button("❌", key=f"aud_{a['id']}"): delete_item("auditeurs", a['id']); st.rerun()
            new_aud = st.text_input("Nouvel auditeur")
            if st.button("Ajouter auditeur") and new_aud.strip(): add_item("auditeurs", ["nom"], [new_aud.strip()]); st.rerun()

        with tab4:
            for z in get_items("zones"):
                c1, c2 = st.columns([4, 1])
                c1.write(z['nom'])
                if c2.button("❌", key=f"zone_{z['id']}"): delete_item("zones", z['id']); st.rerun()
            new_z = st.text_input("Nouvelle Zone")
            if st.button("Ajouter zone") and new_z.strip(): add_item("zones", ["nom"], [new_z.strip()]); st.rerun()

        with tab5:
            for eq in get_items("equipements"):
                c1, c2 = st.columns([4, 1])
                c1.write(eq['nom'])
                if c2.button("❌", key=f"eq_{eq['id']}"): delete_item("equipements", eq['id']); st.rerun()
            new_eq = st.text_input("Nouvel Équipement")
            if st.button("Ajouter équipement") and new_eq.strip(): add_item("equipements", ["nom"], [new_eq.strip()]); st.rerun()

        with tab6:
            for e in get_items("emails"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"{e['label']} : {e['email']}")
                if c2.button("❌", key=f"em_{e['id']}"): delete_item("emails", e['id']); st.rerun()
            lbl = st.text_input("Libellé")
            em = st.text_input("Email")
            if st.button("Ajouter email") and lbl and em: add_item("emails", ["label", "email"], [lbl, em]); st.rerun()

        with tab7:
            cfg_pass = st.text_input("Nouveau mot de passe Admin", type="password")
            if st.button("Mettre à jour mot de passe"): set_config_val("admin_password", cfg_pass); st.success("Mis à jour !")

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

    q_items_with_ids = get_questions_with_ids(type_code)
    total_questions = sum(len(q_list) for q_list in q_items_with_ids.values())

    step_key = f"{prefix_key}_step"
    reponses_key = f"{prefix_key}_reponses"
    idp_key = f"{prefix_key}_idp"

    if step_key not in st.session_state: st.session_state[step_key] = 1
    if reponses_key not in st.session_state: st.session_state[reponses_key] = {}
    if idp_key not in st.session_state: st.session_state[idp_key] = f"022026301{random.randint(10,99)}"

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

    elif st.session_state[step_key] == 2:
        if st.button("← Retour"): st.session_state[step_key] = 1; st.rerun()
        st.title("PARAMÈTRES DE L'AUDIT")
        st.session_state[f"{prefix_key}_zone"] = st.selectbox(location_label, options=location_options)
        st.session_state[f"{prefix_key}_equipe"] = st.selectbox("ÉQUIPE", options=["Équipe1", "Équipe2", "Équipe3", "Équipe Nuit"])
        st.session_state[f"{prefix_key}_semaine"] = st.number_input("SEMAINE (ISO)", value=datetime.now().isocalendar()[1], min_value=1, max_value=53)
        st.session_state[f"{prefix_key}_annee"] = st.number_input("ANNÉE", value=datetime.now().year, min_value=2020, max_value=2035)
        if st.button("Démarrer l'audit →", use_container_width=True):
            st.session_state[step_key] = 3
            st.rerun()

    elif st.session_state[step_key] == 3:
        st.title(audit_title)
        for category, questions in q_items_with_ids.items():
            st.markdown(f'<div class="s-header"><span class="badge-s">📌</span><span class="s-title-text">{category}</span></div>', unsafe_allow_html=True)
            for q_id, q_text in questions:
                st.markdown(f"**{q_text}**")
                statut = st.radio(f"hidden_{q_id}", ["✓ OK / Conforme", "✕ NOK / Non conforme"], key=f"{prefix_key}_q_{q_id}", index=None, label_visibility="collapsed")
                comment = st.text_input("Commentaire / Action corrective :", key=f"{prefix_key}_c_{q_id}")
                photo = st.file_uploader("📷 Joindre une image :", type=["jpg", "jpeg", "png"], key=f"{prefix_key}_p_{q_id}")
                st.session_state[reponses_key][q_id] = {"statut": statut, "comment": comment, "photo": photo}
                st.markdown("---")

        if st.button("✅ Valider et Terminer l'Audit", use_container_width=True):
            reponses = st.session_state[reponses_key]
            all_q_ids = [q_id for q_list in q_items_with_ids.values() for q_id, _ in q_list]
            if any(q_id not in reponses or reponses[q_id]["statut"] is None for q_id in all_q_ids):
                st.error("⚠️ Veuillez répondre à toutes les questions.")
            else:
                st.session_state[step_key] = 4
                st.rerun()

    elif st.session_state[step_key] == 4:
        reponses = st.session_state[reponses_key]
        
        nb_ok = sum(1 for rep in reponses.values() if rep.get("statut") and "OK" in str(rep.get("statut")))
        nb_nok = sum(1 for rep in reponses.values() if rep.get("statut") and ("NOK" in str(rep.get("statut")) or "NON" in str(rep.get("statut"))))
        
        total_effective = nb_ok + nb_nok
        taux = round((nb_ok / total_effective) * 100, 1) if total_effective > 0 else 0

        auditeur = st.session_state.get(f"{prefix_key}_auditeur", "Inconnu")
        zone = st.session_state.get(f"{prefix_key}_zone", "Non définie")
        equipe = st.session_state.get(f"{prefix_key}_equipe", "Non définie")
        semaine = st.session_state.get(f"{prefix_key}_semaine", 1)
        annee = st.session_state.get(f"{prefix_key}_annee", 2026)
        idp = st.session_state.get(idp_key, "N/A")

        save_audit_in_history(idp, type_code, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_questions, reponses)

        st.markdown(f"""
            <div class="score-banner">
                <div class="score-percent">{taux}%</div>
                <div class="score-subtitle">Taux de Conformité - {audit_title}</div>
                <div class="score-detail">{nb_ok} OK / {nb_nok} NOK (Total : {total_questions} questions)</div>
            </div>
        """, unsafe_allow_html=True)

        pdf_bytes = generate_pdf_report(
            audit_title, idp, auditeur, zone, equipe, semaine, annee, 
            reponses, type_code, taux, nb_ok, nb_nok, total_questions
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
            if db_emails:
                email_list = [e['email']  for e in db_emails]
                selected_emails = st.multiselect("Destinataires :", options=email_list, default=email_list)
                if st.button("📤 Envoyer le rapport", use_container_width=True):
                    success, msg = send_email_with_pdf(pdf_bytes, audit_title, idp, auditeur, zone, equipe, semaine, annee, taux, nb_ok, nb_nok, total_questions, selected_emails)
                    if success: st.success(msg)
                    else: st.error(msg)

        st.markdown("---")
        if st.button("🔄 Démarrer un nouvel audit", use_container_width=True):
            st.session_state[step_key] = 1
            st.session_state[reponses_key] = {}
            st.session_state[idp_key] = f"022026301{random.randint(10,99)}"
            st.rerun()
