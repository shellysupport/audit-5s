import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import json
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# CONFIGURATION ET BASE DE DONNÉES
# ==============================================================================
st.set_page_config(page_title="Audit 5S & Auto Maintenance", page_icon="📋", layout="wide")

DB_NAME = "audits_database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
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
            total_questions INTEGER,
            nb_ok INTEGER,
            nb_nok INTEGER,
            score_pourcentage REAL,
            details_reponses TEXT
        )
    """)
    
    c.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, type_audit TEXT, categorie TEXT, intitule TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS auditeurs (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS zones (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS equipements (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, email TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS config (cle TEXT PRIMARY KEY, valeur TEXT)")

    configs_defaut = [
        ("admin_password", "admin123"),
        ("smtp_server", "smtp.gmail.com"),
        ("smtp_port", "587"),
        ("smtp_user", ""),
        ("smtp_password", "")
    ]
    for cle, val in configs_defaut:
        c.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES (?, ?)", (cle, val))

    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        seed_default_questions(c)

    c.execute("SELECT COUNT(*) FROM auditeurs")
    if c.fetchone()[0] == 0:
        for aud in ["Yosri", "Auditeur 1", "Auditeur 2"]:
            c.execute("INSERT INTO auditeurs (nom) VALUES (?)", (aud,))

    c.execute("SELECT COUNT(*) FROM zones")
    if c.fetchone()[0] == 0:
        for z in ["Zone Assemblage", "Zone Usinage", "Magasin", "Zone EXP"]:
            c.execute("INSERT INTO zones (nom) VALUES (?)", (z,))

    c.execute("SELECT COUNT(*) FROM equipements")
    if c.fetchone()[0] == 0:
        for eq in ["FI506", "FI507", "Machine A1", "Ligne B2"]:
            c.execute("INSERT INTO equipements (nom) VALUES (?)", (eq,))

    conn.commit()
    conn.close()

def seed_default_questions(cursor):
    q_5s = {
        "S1 – DÉBARRASSER": [
            "Seuls les outils, pièces et documents utiles sont présents sur le poste.",
            "Les objets inutiles / obsolètes sont identifiés, étiquetés et évacués vers la zone rouge."
        ],
        "S2 – RANGER": [
            "Chaque outil/équipement a un emplacement défini et matérialisé (ombre, étiquette, marquage au sol).",
            "Les pièces et matières sont rangées selon le FIFO et clairement identifiées."
        ],
        "S3 – TENIR PROPRE": [
            "Le poste de travail, le sol et les équipements sont propres et exempts de poussière/huile.",
            "Les moyens de nettoyage sont disponibles, propres et rangés à leur place."
        ],
        "S4 – STANDARDISER": [
            "Les standards 5S (photos / règles) sont affichés et visibles à proximité du poste.",
            "Les anomalies constatées lors du nettoyage quotidien sont signalées et tracées."
        ],
        "S5 – MAINTENIR": [
            "L'auto-évaluation 5S est réalisée régulièrement par l'équipe.",
            "Les actions correctives des précédents audits 5S sont clôturées dans les délais."
        ]
    }
    for cat, qs in q_5s.items():
        for q in qs:
            cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES ('5S', ?, ?)", (cat, q))

    q_am = {
        "État du poste de travail": [
            "Le management visuel est présent et en place.",
            "Le poste est propre et organisé conformément aux standards.",
            "Aucun élément dangereux ou non conforme (fuite, câble dénudé, pièce au sol...)."
        ],
        "Kit AM et EPI": [
            "Le kit AM est complet, conforme à la liste standardisée et identifié (numéro de ligne/poste).",
            "Les EPI nécessaires sont disponibles, conformes et en bon état.",
            "Le kit est facilement accessible et ne gêne pas le flux de production."
        ],
        "Standard d'AM": [
            "Un unique standard AM est affiché et accessible à proximité du poste.",
            "Les instructions correspondent bien à l'état actuel du poste (FI à jour)."
        ],
        "Réalisation des Tâches": [
            "Les opérateurs réalisent les tâches selon le standard et dans l'ordre défini.",
            "La fréquence de réalisation (quotidienne / hebdo / mensuelle) est respectée.",
            "Les outils et EPI utilisés sont adaptés à chaque action d'AM et sont bien ceux prévus dans le standard.",
            "Les opérateurs signalent les écarts observés (défauts, bruit, jeu, fuite...)."
        ],
        "Traçabilité et Enregistrement": [
            "Les anomalies détectées sont enregistrées dans le QRCI.",
            "Les bons de travail sont émis lorsque nécessaire et transmis à la maintenance.",
            "Le tableau de bord AM (SIM, taux de complétion, anomalies...) est mis à jour regularly en mode projet.",
            "Les actions issues des audits AM précédents sont suivies en SIM PROD et clôturées."
        ]
    }
    for cat, qs in q_am.items():
        for q in qs:
            cursor.execute("INSERT INTO questions (type_audit, categorie, intitule) VALUES ('AM', ?, ?)", (cat, q))

init_db()

# --- FONCTIONS UTILITAIRES BDD ---
def get_config_val(cle):
    conn = get_db_connection()
    res = conn.execute("SELECT valeur FROM config WHERE cle = ?", (cle,)).fetchone()
    conn.close()
    return res['valeur'] if res else ""

def set_config_val(cle, valeur):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)", (cle, valeur))
    conn.commit()
    conn.close()

def get_items(table):
    conn = get_db_connection()
    res = conn.execute(f"SELECT * FROM {table} ORDER BY id ASC").fetchall()
    conn.close()
    return res

def add_item(table, cols, vals):
    conn = get_db_connection()
    placeholders = ", ".join(["?"] * len(vals))
    cols_str = ", ".join(cols)
    conn.execute(f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})", vals)
    conn.commit()
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
    q_dict = {}
    for r in rows:
        cat = r['categorie']
        if cat not in q_dict:
            q_dict[cat] = []
        q_dict[cat].append(r['intitule'])
    return q_dict

# --- GENERATION PDF ---
def generate_pdf_report(audit_title, idp, auditeur, zone, equipe, semaine, annee, reponses, q_dict, score_pct, nb_ok, nb_nok, total_q):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12)
    cat_style = ParagraphStyle('CatStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#1E3A8A"))
    q_style = ParagraphStyle('QStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
    ok_style = ParagraphStyle('OKStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#166534"))
    nok_style = ParagraphStyle('NOKStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor("#991B1B"))

    elements = []

    header_data = [
        [
            Paragraph(f"<b>IDP :</b><br/>{idp}", header_style),
            Paragraph(f"<b>AUDITEUR :</b><br/>{auditeur}", header_style),
            Paragraph(f"<b>ZONE / ÉQUIPEMENT :</b><br/>{zone}", header_style)
        ],
        [
            Paragraph(f"<b>PÉRIODE :</b><br/>Semaine {semaine}/{annee}", header_style),
            Paragraph(f"<b>TAUX CONFORMITÉ :</b><br/><font color='#1E3A8A'><b>{score_pct}%</b></font> ({nb_ok} OK / {nb_nok} NOK)", header_style),
            Paragraph(f"<b>ÉQUIPE :</b><br/>{equipe}", header_style)
        ]
    ]

    t_header = Table(header_data, colWidths=[180, 200, 175])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F3F4F6")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#D1D5DB")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 10))

    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=colors.HexColor("#1E3A8A"), alignment=1)
    elements.append(Paragraph(f"RAPPORT D'AUDIT - {audit_title.upper()}", title_style))
    elements.append(Spacer(1, 10))

    table_data = [[Paragraph("<b>Critères d'Audit / Questions</b>", header_style), Paragraph("<b>Statut</b>", header_style), Paragraph("<b>Remarques / Remarques</b>", header_style)]]

    q_idx = 1
    for cat, questions in q_dict.items():
        table_data.append([Paragraph(cat, cat_style), "", ""])
        for q in questions:
            rep_data = reponses.get(q_idx, {"statut": "✓ OK / Conforme", "comment": ""})
            st_text = rep_data["statut"]
            st_p = Paragraph(st_text, ok_style if "OK" in st_text else nok_style)
            comm_p = Paragraph(rep_data.get("comment", ""), q_style)
            
            table_data.append([Paragraph(q, q_style), st_p, comm_p])
            q_idx += 1

    t_questions = Table(table_data, colWidths=[320, 100, 135])
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E5E7EB")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]

    r_idx = 1
    for cat, questions in q_dict.items():
        t_style.append(('SPAN', (0, r_idx), (2, r_idx)))
        t_style.append(('BACKGROUND', (0, r_idx), (2, r_idx), colors.HexColor("#EFF6FF")))
        r_idx += len(questions) + 1

    t_questions.setStyle(TableStyle(t_style))
    elements.append(t_questions)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Audits')
    return output.getvalue()

# ==============================================================================
# SESSION STATE & INITIALISATION
# ==============================================================================
if 'admin_authenticated' not in st.session_state:
    st.session_state.admin_authenticated = False

# ==============================================================================
# NAVIGATION BAR (SIDEBAR)
# ==============================================================================
st.sidebar.title("📌 Menu Principal")
page = st.sidebar.radio("Navigation", ["📝 Réaliser un Audit", "📊 Historique des Audits", "⚙️ Paramètres / Admin"])

# ==============================================================================
# PAGE : RÉALISER UN AUDIT
# ==============================================================================
if page == "📝 Réaliser un Audit":
    st.title("📝 Saisie d'un Nouvel Audit")

    audit_type = st.radio("Sélectionnez le type d'audit :", ["5S", "AM"], format_func=lambda x: "Audit 5S Hebdo" if x == "5S" else "Audit Auto Maintenance (AM)", horizontal=True)

    auditeurs_list = [a['nom'] for a in get_items("auditeurs")]
    zones_list = [z['nom'] for z in get_items("zones")]
    equipements_list = [e['nom'] for e in get_items("equipements")]

    st.markdown("### 📋 Informations Générales")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        auditeur_selected = st.selectbox("Auditeur :", options=auditeurs_list if auditeurs_list else ["Inconnu"])
        zone_selected = st.selectbox("Zone / Îlot :" if audit_type == "5S" else "Équipement / Machine :", options=zones_list if audit_type == "5S" else equipements_list if equipements_list else ["N/A"])
    
    with c2:
        equipe_selected = st.selectbox("Équipe :", ["Équipe 1", "Équipe 2", "Équipe 3", "Journée"])
        semaine_actuelle = int(datetime.now().strftime("%V"))
        semaine_selected = st.number_input("Semaine :", min_value=1, max_value=53, value=semaine_actuelle)

    with c3:
        annee_actuelle = datetime.now().year
        annee_selected = st.number_input("Année :", min_value=2020, max_value=2035, value=annee_actuelle)
        idp_input = st.text_input("IDP / Référence Audit :", value=f"02{annee_selected}{semaine_selected:02d}{int(datetime.now().timestamp())%10000:04d}")

    st.markdown("---")
    st.markdown("### 📑 Grille d'Évaluation")

    q_dict = get_questions_dict(audit_type)
    reponses = {}
    q_index = 1

    if not q_dict:
        st.error("Aucune question trouvée. Allez dans Paramètres pour réinitialiser les questions.")
    else:
        for cat, questions in q_dict.items():
            st.subheader(f"📌 {cat}")
            for q in questions:
                col_q, col_s, col_c = st.columns([5, 2, 3])
                col_q.write(f"**{q_index}.** {q}")
                statut = col_s.radio(f"Statut Q{q_index}", ["✓ OK / Conforme", "✕ NOK / Non conforme"], key=f"q_{q_index}", label_visibility="collapsed")
                comment = col_c.text_input(f"Remarque Q{q_index}", key=f"c_{q_index}", placeholder="Commentaire si NOK...", label_visibility="collapsed")
                reponses[q_index] = {"statut": statut, "comment": comment}
                q_index += 1

        total_questions = q_index - 1
        nb_ok = sum(1 for r in reponses.values() if "OK" in r["statut"])
        nb_nok = total_questions - nb_ok
        score_pct = round((nb_ok / total_questions * 100), 1) if total_questions > 0 else 0.0

        st.markdown("---")
        st.markdown(f"### 📊 Résultat : **{score_pct}%** ({nb_ok} OK / {nb_nok} NOK sur {total_questions} questions)")

        if st.button("💾 Valider et Enregistrer l'Audit", type="primary", use_container_width=True):
            conn = get_db_connection()
            c = conn.cursor()
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            details_json = json.dumps(reponses)

            c.execute("""
                INSERT INTO historique_audits 
                (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_audit, total_questions, nb_ok, nb_nok, score_pourcentage, details_reponses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (idp_input, audit_type, auditeur_selected, zone_selected, equipe_selected, semaine_selected, annee_selected, date_str, total_questions, nb_ok, nb_nok, score_pct, details_json))
            
            conn.commit()
            conn.close()

            st.success("✅ Audit enregistré avec succès !")

            audit_title_pdf = "Audit 5S Hebdo" if audit_type == "5S" else "Audit Auto Maintenance"
            pdf_bytes = generate_pdf_report(audit_title_pdf, idp_input, auditeur_selected, zone_selected, equipe_selected, semaine_selected, annee_selected, reponses, q_dict, score_pct, nb_ok, nb_nok, total_questions)

            st.download_button(
                label="📥 Télécharger le Rapport PDF Instantané",
                data=pdf_bytes,
                file_name=f"Rapport_{audit_type}_{zone_selected}_S{semaine_selected}.pdf",
                mime="application/pdf"
            )

# ==============================================================================
# PAGE : HISTORIQUE DES AUDITS
# ==============================================================================
elif page == "📊 Historique des Audits":
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
        ].reset_index(drop=True)

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

        st.caption("👇 **Cliquez sur une ligne du tableau** pour générer et télécharger le rapport PDF correspondant.")

        # Affichage du tableau interactif avec option de sélection de ligne
        event = st.dataframe(
            df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone / Équipement', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK']],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        selected_rows = event.selection.rows if event else []

        # BLOC RAJOUTÉ : Régénération du PDF en cas de clic sur une ligne
        if selected_rows:
            row_idx = selected_rows[0]
            selected_row = filtered_df.iloc[row_idx]
            
            type_code = selected_row['type_audit']
            audit_title_pdf = f"Audit {type_code} Hebdo" if type_code == "5S" else "Audit Auto Maintenance"
            q_dict = get_questions_dict(type_code)
            
            total_q = int(selected_row['total_questions'])
            nb_ok = int(selected_row['nb_ok'])
            
            reponses_regen = {}
            if 'details_reponses' in selected_row and pd.notnull(selected_row['details_reponses']):
                try:
                    reponses_raw = json.loads(selected_row['details_reponses'])
                    reponses_regen = {int(k): v for k, v in reponses_raw.items()}
                except Exception:
                    reponses_regen = {}

            if not reponses_regen:
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

            st.success(f"📌 Audit sélectionné : **#{selected_row['idp']}** ({selected_row['type_audit']} - {selected_row['zone']} - S{selected_row['semaine']})")
            
            st.download_button(
                label=f"📄 Télécharger le Rapport PDF de l'audit #{selected_row['idp']}",
                data=pdf_regen_bytes,
                file_name=f"Rapport_{type_code}_{selected_row['zone']}_S{selected_row['semaine']}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
        else:
            st.info("💡 Cliquez sur n'importe quelle ligne dans le tableau ci-dessus pour faire apparaître son bouton de téléchargement PDF.")

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
