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

# --- BASE DE DONNÉES ---
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

    c.execute("SELECT COUNT(*) FROM equipements")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO equipements (nom) VALUES (?)", [("Presse 01",), ("Ligne Assemblage A",), ("Robot de Soudure 02",)])

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
            
            if statut_txt and statut_txt.startswith("✓"):
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

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique Audits')
    output.seek(0)
    return output.getvalue()

# --- STYLES CSS PERSONNALISÉS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    div.stButton > button { border-radius: 8px; font-weight: 700; }
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

        # --- SECTION REGENÉRATION ET TÉLÉCHARGEMENT PDF ---
        st.markdown("---")
        st.subheader("📄 Régénérer un Rapport PDF de l'Historique")
        
        audit_options = {
            row['id']: f"ID #{row['id']} | [{row['type_audit']}] {row['zone']} - Semaine {row['semaine']}/{row['annee']} ({row['auditeur']})"
            for _, row in filtered_df.iterrows()
        }
        
        selected_hist_id = st.selectbox(
            "Sélectionnez un audit à imprimer/télécharger en PDF :", 
            options=list(audit_options.keys()), 
            format_func=lambda x: audit_options[x]
        )

        if selected_hist_id:
            selected_row = filtered_df[filtered_df['id'] == selected_hist_id].iloc[0]
            type_code = selected_row['type_audit']
            audit_title_pdf = f"Audit {type_code} Hebdo" if type_code == "5S" else "Audit Auto Maintenance"
            
            q_dict = get_questions_dict(type_code)
            
            # Reconstruction des réponses fictives basées sur les ratios OK/NOK enregistrés
            total_q = int(selected_row['total_questions'])
            nb_ok = int(selected_row['nb_ok'])
            
            reponses_regen = {}
            idx = 1
            for cat, questions in q_dict.items():
                for _ in questions:
                    statut = "✓ OK / Conforme" if idx <= nb_ok else "✕ NOK / Non conforme"
                    reponses_regen[idx] = {"statut": statut, "comment": ""}
                    idx += 1

            pdf_regen_bytes = generate_pdf_report(
                audit_title_pdf,
                selected_row['idp'],
                selected_row['auditeur'],
                selected_row['zone'],
                selected_row['equipe'],
                selected_row['semaine'],
                selected_row['annee'],
                reponses_regen,
                q_dict,
                selected_row['score_pourcentage'],
                selected_row['nb_ok'],
                selected_row['nb_nok'],
                total_q
            )

            st.download_button(
                label=f"📥 Télécharger le Rapport PDF pour l'Audit #{selected_row['idp']}",
                data=pdf_regen_bytes,
                file_name=f"Rapport_{type_code}_{selected_row['zone']}_S{selected_row['semaine']}.pdf",
                mime="application/pdf",
                type="primary"
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

        with tab1:
            st.subheader("🛠️ Gérer / Modifier l'Historique des Audits")
            conn = get_db_connection()
            df_audits = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
            
            if df_audits.empty:
                st.info("Aucun audit à modifier ou supprimer.")
                conn.close()
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

        with tab6:
            st.subheader("Destinataires des E-mails")
            for em in get_items("emails"):
                c1, c2 = st.columns([4, 1])
                c1.write(f"• **{em['label']}** ({em['email']})")
                if c2.button("❌", key=f"del_em_{em['id']}"):
                    delete_item("emails", em['id'])
                    st.rerun()
            st.markdown("---")
            em_label = st.text_input("Libellé / Rôle", key="input_em_label")
            em_val = st.text_input("Adresse E-mail", key="input_em_val")
            if st.button("Ajouter le destinataire"):
                if em_label.strip() and em_val.strip():
                    add_item("emails", ["label", "email"], [em_label.strip(), em_val.strip()])
                    st.rerun()

        with tab7:
            st.subheader("Paramètres de Sécurité & Serveur SMTP")
            with st.form("form_config"):
                cfg_pwd = st.text_input("Mot de passe Administrateur", value=get_config_val("admin_password"), type="password")
                cfg_server = st.text_input("Serveur SMTP", value=get_config_val("smtp_server"))
                cfg_port = st.text_input("Port SMTP", value=get_config_val("smtp_port"))
                cfg_user = st.text_input("Utilisateur SMTP", value=get_config_val("smtp_user"))
                cfg_pass = st.text_input("Mot de passe SMTP", value=get_config_val("smtp_password"), type="password")
                
                if st.form_submit_button("Enregistrer les configurations"):
                    set_config_val("admin_password", cfg_pwd)
                    set_config_val("smtp_server", cfg_server)
                    set_config_val("smtp_port", cfg_port)
                    set_config_val("smtp_user", cfg_user)
                    set_config_val("smtp_password", cfg_pass)
                    st.success("Configurations enregistrées !")
