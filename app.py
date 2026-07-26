import streamlit as st
import sqlite3
import random
from datetime import datetime
import smtplib
import io
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
    page_title="Audit 5S Hebdo",
    page_icon="📋",
    layout="centered"
)

# --- BASE DE DONNÉES (PERSISTANCE DES PARAMÈTRES & CONFIG) ---
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
    
    # Valeurs par défaut
    c.execute("SELECT COUNT(*) FROM auditeurs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO auditeurs (nom) VALUES (?)", [("BESSEM FEKIH",), ("Jean Dupont",)])
        
    c.execute("SELECT COUNT(*) FROM zones")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO zones (nom) VALUES (?)", [("AUTOMATISME",), ("LIGNE 1",), ("MAINTENANCE",)])

    c.execute("SELECT COUNT(*) FROM emails")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO emails (label, email) VALUES (?, ?)", [("Responsable Atelier", "yosri.fadhly@somfy.com"),])

    # Configuration par défaut
    default_config = {
        "admin_password": "admin",  # Mot de passe pour la page Paramètres
        "smtp_server": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "yosri.fadhly@gmail.com",
        "smtp_password": "rzftdozwqntssiwa"
    }
    for k, v in default_config.items():
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

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

# --- FONCTION DE GÉNÉRATION DU PDF ---
def generate_pdf_report(idp, auditeur, zone, equipe, semaine, annee, reponses, questions_5s, taux, nb_ok, nb_nok, total_q):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#0f172a'), alignment=1)
    header_s_style = ParagraphStyle('HeaderSStyle', parent=styles['Heading3'], fontSize=11, leading=14, textColor=colors.HexColor('#ffffff'), backColor=colors.HexColor('#0f172a'), spaceBefore=8, spaceAfter=4, borderPadding=4)
    text_bold = ParagraphStyle('TextBold', parent=styles['Normal'], fontSize=9, leading=12, fontName='Helvetica-Bold')
    text_normal = ParagraphStyle('TextNormal', parent=styles['Normal'], fontSize=9, leading=12)
    text_comment = ParagraphStyle('TextComment', parent=styles['Italic'], fontSize=8, leading=10, textColor=colors.HexColor('#475569'))
    
    story.append(Paragraph("RAPPORT D'AUDIT 5S HEBDO", title_style))
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
    for cat_index, (category, questions) in enumerate(questions_5s.items(), start=1):
        s_code = f"S{cat_index}"
        story.append(Paragraph(f"<b>{s_code} - {category}</b>", header_s_style))
        
        table_q_data = []
        for q in questions:
            q_counter += 1
            rep = reponses.get(q_counter, {})
            statut_txt = rep.get("statut", "Non répondu")
            comment_txt = rep.get("comment", "")
            photo_file = rep.get("photo", None)
            
            if "Conforme" in statut_txt and "Non" not in statut_txt:
                status_p = Paragraph("<font color='#16a34a'><b>✓ CONFORME</b></font>", text_normal)
            else:
                status_p = Paragraph("<font color='#dc2626'><b>✕ NON CONFORME</b></font>", text_normal)
            
            q_content = [Paragraph(q, text_bold)]
            if comment_txt:
                q_content.append(Paragraph(f"<i>Remarque : {comment_txt}</i>", text_comment))
                
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

# --- STYLES CSS ---
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
    .alert-info-custom { background-color: #dbeafe; border: 1px solid #bfdbfe; color: #1e40af; border-radius: 8px; padding: 14px; font-weight: 600; margin-top: 15px; }
    div.stButton > button { border-radius: 8px; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("📌 Menu")
page = st.sidebar.radio("Navigation", ["📋 Réaliser un Audit", "⚙️ Paramètres / Admin"])

# Variable de session pour la connexion Admin
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# ==============================================================================
# PAGE : PARAMÈTRES / ADMIN (PROTÉGÉE PAR MOT DE PASSE)
# ==============================================================================
if page == "⚙️ Paramètres / Admin":
    st.title("⚙️ Paramètres de l'application")

    # Si l'utilisateur n'est pas encore identifié en tant qu'admin
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
    
    # Si l'admin est connecté, afficher le panneau d'administration
    else:
        if st.sidebar.button("🚪 Déconnexion Admin"):
            st.session_state.admin_authenticated = False
            st.rerun()

        tab1, tab2, tab3, tab4 = st.tabs(["👤 Auditeurs", "🏭 Zones / Îlots", "📧 Emails Responsables", "🔐 Sécurité & SMTP"])
        
        with tab1:
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

        with tab2:
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

        with tab3:
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

        with tab4:
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
# PAGE : AUDIT 5S (ACCÈS LIBRE)
# ==============================================================================
else:
    db_auditeurs = [a['nom'] for a in get_items("auditeurs")]
    db_zones = [z['nom'] for z in get_items("zones")]
    db_emails = get_items("emails")

    QUESTIONS_5S = {
        "S1 – DÉBARRASSER": [
            "Est-ce qu'il y a du matériel / fournitures / machines / équipement Inutiles ?",
            "Est-ce qu'il y a du matériel / fourniture / machines / équipement Endommagé ?"
        ],
        "S2 – RANGER": [
            "Est-ce que chaque matériel a un emplacement défini ?",
            "Est-ce que chaque matériel est à son emplacement (zoning + affectation) ?",
            "Est-ce que rien ne traîne en dehors des emplacements ?"
        ],
        "S3 – TENIR PROPRE": [
            "Est-ce que le poste et ses abords sont propres ?",
            "Est-ce qu'il n'y a pas des fuites et/ou de salissures ?"
        ],
        "S4 – STANDARDISER": [
            "Est-ce que le standard 5S est disponible ?",
            "Est-ce que le point propreté standard est mis en place ?"
        ],
        "S5 – MAINTENIR": [
            "Est-ce que la fiche d'audit quotidien est renseignée et les actions traitées ?",
            "Quelles sont les dernières actions réalisées par le GAP ?"
        ]
    }
    TOTAL_QUESTIONS = sum(len(q) for q in QUESTIONS_5S.values())

    if "step" not in st.session_state: st.session_state.step = 1
    if "reponses" not in st.session_state: st.session_state.reponses = {}
    if "idp" not in st.session_state: st.session_state.idp = f"022026301{random.randint(10,99)}"

    # ÉCRAN 1 : IDENTIFICATION
    if st.session_state.step == 1:
        st.title("AUDIT 5S HEBDO")
        aud_sel = st.selectbox("AUDITEUR (NOM & PRÉNOM)", options=["— Sélectionner —"] + db_auditeurs)
        if st.button("Continuer →"):
            if aud_sel == "— Sélectionner —":
                st.error("Sélectionnez un auditeur.")
            else:
                st.session_state.auditeur = aud_sel
                st.session_state.step = 2
                st.rerun()

    # ÉCRAN 2 : PARAMÈTRES AUDIT
    elif st.session_state.step == 2:
        if st.button("← Retour"):
            st.session_state.step = 1
            st.rerun()
        st.title("PARAMÈTRES DE L'AUDIT")
        st.session_state.zone = st.selectbox("ZONE / ÎLOT", options=db_zones if db_zones else ["Aucune zone"])
        st.session_state.equipe = st.selectbox("ÉQUIPE", options=["Équipe1", "Équipe2", "Équipe3", "Équipe Nuit"])
        st.session_state.semaine = st.number_input("SEMAINE (ISO)", value=datetime.now().isocalendar()[1])
        st.session_state.annee = st.number_input("ANNÉE", value=datetime.now().year)
        if st.button("Démarrer l'audit →"):
            st.session_state.step = 3
            st.rerun()

    # ÉCRAN 3 : QUESTIONNAIRE
    elif st.session_state.step == 3:
        q_counter = 0
        for cat_index, (category, questions) in enumerate(QUESTIONS_5S.items(), start=1):
            s_code = f"S{cat_index}"
            st.markdown(f'''
                <div class="s-header">
                    <span class="badge-s">{s_code}</span>
                    <span class="s-title-text">{category}</span>
                </div>
            ''', unsafe_allow_html=True)
            
            for q in questions:
                q_counter += 1
                statut = st.radio(q, ["✓ Conforme", "✕ Non conforme"], key=f"q_{q_counter}", index=None)
                photo = st.file_uploader("📷 PRENDRE / JOINDRE UNE PHOTO", key=f"p_{q_counter}", type=["png", "jpg", "jpeg"])
                comment = st.text_input("Commentaire (optionnel)", key=f"c_{q_counter}", placeholder="Commentaire (optionnel)")
                
                if statut:
                    st.session_state.reponses[q_counter] = {
                        "q": q, 
                        "statut": statut, 
                        "photo": photo, 
                        "comment": comment, 
                        "cat": category
                    }
                st.markdown("---")

        nb_rep = len(st.session_state.reponses)
        st.progress(nb_rep / TOTAL_QUESTIONS)
        st.write(f"**{nb_rep} / {TOTAL_QUESTIONS} questions répondues**")

        if st.button("✓ Valider et générer le rapport"):
            if nb_rep < TOTAL_QUESTIONS:
                st.warning(f"⚠️ Veuillez répondre à toutes les questions ({nb_rep}/{TOTAL_QUESTIONS}).")
            else:
                st.session_state.step = 4
                st.rerun()

    # ÉCRAN 4 : RAPPORT + ENVOI MAIL
    elif st.session_state.step == 4:
        if st.button("← Retour"):
            st.session_state.step = 3
            st.rerun()

        st.title("RAPPORT D'AUDIT 5S")

        nb_ok = sum(1 for r in st.session_state.reponses.values() if "Conforme" in r["statut"] and "Non" not in r["statut"])
        nb_nok = TOTAL_QUESTIONS - nb_ok
        taux = int((nb_ok / TOTAL_QUESTIONS) * 100)

        st.markdown(f"""
            <div class="info-grid">
                <div class="info-card"><div class="info-label">IDP</div><div class="info-val">{st.session_state.idp}</div></div>
                <div class="info-card"><div class="info-label">AUDITEUR</div><div class="info-val">{st.session_state.auditeur}</div></div>
                <div class="info-card"><div class="info-label">ZONE / ÎLOT</div><div class="info-val">{st.session_state.zone}</div></div>
                <div class="info-card"><div class="info-label">ÉQUIPE</div><div class="info-val">{st.session_state.equipe}</div></div>
                <div class="info-card"><div class="info-label">PÉRIODE</div><div class="info-val">Semaine {st.session_state.semaine} / {st.session_state.annee}</div></div>
                <div class="info-card"><div class="info-label">POINTS NON CONFORMES</div><div class="info-val-nok">{nb_nok} / {TOTAL_QUESTIONS}</div></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="score-banner">
                <div class="score-percent">{taux}%</div>
                <div class="score-subtitle">TAUX DE CONFORMITÉ 5S</div>
                <div class="score-detail">✓ {nb_ok} conformes &nbsp;&nbsp;•&nbsp;&nbsp; ✕ {nb_nok} non conformes</div>
            </div>
        """, unsafe_allow_html=True)

        pdf_bytes = generate_pdf_report(
            st.session_state.idp,
            st.session_state.auditeur,
            st.session_state.zone,
            st.session_state.equipe,
            st.session_state.semaine,
            st.session_state.annee,
            st.session_state.reponses,
            QUESTIONS_5S,
            taux, nb_ok, nb_nok, TOTAL_QUESTIONS
        )

        q_counter = 0
        for cat_index, (category, questions) in enumerate(QUESTIONS_5S.items(), start=1):
            s_code = f"S{cat_index}"
            st.markdown(f'''
                <div class="s-header">
                    <span class="badge-s">{s_code}</span>
                    <span class="s-title-text">{category}</span>
                </div>
            ''', unsafe_allow_html=True)
            
            for q in questions:
                q_counter += 1
                rep = st.session_state.reponses.get(q_counter, {})
                statut_txt = rep.get("statut", "")
                
                if "Conforme" in statut_txt and "Non" not in statut_txt:
                    st.markdown(f"✅ **{q}**")
                else:
                    st.markdown(f"❌ **{q}**")
                
                if rep.get("comment"):
                    st.caption(f"💬 *Remarque : {rep['comment']}*")
                
                if rep.get("photo"):
                    st.image(rep["photo"], width=240)
                    
            st.markdown("---")

        st.markdown(f"""
            <div class="alert-info-custom">
                ✓ Résultat de l'audit (IDP {st.session_state.idp}) enregistré sur cet appareil.
            </div>
        """, unsafe_allow_html=True)
        st.write("")

        destinataires_opts = {f"{e['label']} ({e['email']})": e['email'] for e in db_emails}
        
        if destinataires_opts:
            selected_dest = st.selectbox("✉️ Choisir le responsable destinataire :", options=list(destinataires_opts.keys()))
            target_email = destinataires_opts[selected_dest]
        else:
            st.warning("⚠️ Aucune adresse mail configurée dans la page Paramètres.")
            target_email = None

        c_btn1, c_btn2 = st.columns([1, 2])
        
        with c_btn1:
            st.download_button(
                label="⬇ Télécharger PDF",
                data=pdf_bytes,
                file_name=f"Rapport_Audit_5S_{st.session_state.zone}_S{st.session_state.semaine}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
                
        with c_btn2:
            if st.button("✉ Envoyer au responsable", use_container_width=True):
                if not target_email:
                    st.error("⚠️ Aucun destinataire sélectionné.")
                else:
                    try:
                        SMTP_SERVER = get_config_val("smtp_server")
                        SMTP_PORT = int(get_config_val("smtp_port"))
                        SMTP_USER = get_config_val("smtp_user")
                        SMTP_PASSWORD = get_config_val("smtp_password")

                        msg = MIMEMultipart()
                        msg['From'] = SMTP_USER
                        msg['To'] = target_email
                        msg['Subject'] = f"Rapport Audit 5S - {st.session_state.zone} (Semaine {st.session_state.semaine})"

                        body_text = f"""Bonjour,

Veuillez trouver ci-joint le rapport d'audit 5S détaillé au format PDF.

Résumé rapide :
- IDP : {st.session_state.idp}
- Auditeur : {st.session_state.auditeur}
- Zone : {st.session_state.zone}
- Taux de conformité : {taux}% ({nb_ok} OK / {nb_nok} NOK)

Cordialement,
Application Audit 5S
"""
                        msg.attach(MIMEText(body_text, 'plain'))

                        pdf_filename = f"Rapport_Audit_5S_{st.session_state.zone}_Semaine_{st.session_state.semaine}.pdf"
                        part = MIMEApplication(pdf_bytes, Name=pdf_filename)
                        part['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                        msg.attach(part)

                        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                            server.starttls()
                            server.login(SMTP_USER, SMTP_PASSWORD)
                            server.sendmail(SMTP_USER, target_email, msg.as_string())

                        st.success(f"✉️ Rapport PDF envoyé avec succès à {target_email} !")

                    except Exception as e:
                        st.error(f"❌ Échec de l'envoi : {e}")