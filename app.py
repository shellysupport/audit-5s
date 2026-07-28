import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
import base64
from io import BytesIO
from weasyprint import HTML

# ==========================================
# 1. CONFIGURATION INITIALE & STYLES
# ==========================================
st.set_page_config(
    page_title="Audit 5S & Auto Maintenance",
    page_icon="📋",
    layout="wide"
)

DB_FILE = "audits_app.db"
UPLOAD_DIR = "uploaded_photos"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ==========================================
# 2. BASE DE DONNÉES (INIT & HELPER FUNCTIONS)
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Table Audits
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_audit TEXT,
            type_audit TEXT,
            zone_machine TEXT,
            auditeur TEXT,
            equipe TEXT,
            semaine INTEGER,
            annee INTEGER,
            total_questions INTEGER,
            total_ok INTEGER,
            total_nok INTEGER,
            score_pourcentage REAL
        )
    ''')
    
    # Table Détails des Audits (Points OK et NOK + Photos + Commentaires)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id INTEGER,
            categorie TEXT,
            question TEXT,
            statut TEXT,
            commentaire TEXT,
            photo_path TEXT,
            FOREIGN KEY(audit_id) REFERENCES audits(id) ON DELETE CASCADE
        )
    ''')

    # Table Checklists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_audit TEXT,
            categorie TEXT,
            question TEXT
        )
    ''')

    # Table Auditeurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auditeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE
        )
    ''')

    # Table Zones (5S)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones_5s (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE
        )
    ''')

    # Table Machines (AM)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS machines_am (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE
        )
    ''')

    # Table Destinataires Email
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_destinataires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE
        )
    ''')

    # Table Configuration (Admin & SMTP)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            cle TEXT PRIMARY KEY,
            valeur TEXT
        )
    ''')

    # Valeurs par défaut
    cursor.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('admin_password', 'admin123')")
    cursor.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('smtp_server', 'smtp.gmail.com')")
    cursor.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('smtp_port', '587')")
    cursor.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('smtp_user', '')")
    cursor.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('smtp_password', '')")

    # Données par défaut si vide
    cursor.execute("SELECT COUNT(*) FROM checklists")
    if cursor.fetchone()[0] == 0:
        default_questions = [
            ("5S", "1. Seiri (Trier)", "Seul le matériel nécessaire est présent sur le poste ?"),
            ("5S", "1. Seiri (Trier)", "Les objets inutiles ou défectueux sont évacués ?"),
            ("5S", "2. Seiton (Ranger)", "Chaque outil a une place définie et identifiée ?"),
            ("5S", "2. Seiton (Ranger)", "Les passages et voies d'accès sont dégagés ?"),
            ("5S", "3. Seiso (Nettoyer)", "Le sol, la machine et le plan de travail sont propres ?"),
            ("5S", "3. Seiso (Nettoyer)", "Les moyens de nettoyage sont accessibles et rangés ?"),
            ("5S", "4. Seiketsu (Standardiser)", "Les standards 5S sont affichés et visibles ?"),
            ("5S", "5. Shitsuke (Respecter)", "Les règles de sécurité et 5S sont respectées ?"),
            ("AM", "Sécurité & Protecteurs", "Les carters de protection et arrêts d'urgence sont fonctionnels ?"),
            ("AM", "Niveaux & Lubrification", "Les niveaux d'huile et de fluide sont conformes ?"),
            ("AM", "Fuites & Anomalies", "Absence de fuites d'air, d'huile ou d'eau ?"),
            ("AM", "Nettoyage Machine", "La zone de travail et la structure machine sont exemptes de copeaux/poussières ?"),
            ("AM", "Bruits & Vibrations", "Aucun bruit anormal ni vibration inhabituelle lors du fonctionnement ?")
        ]
        cursor.executemany("INSERT INTO checklists (type_audit, categorie, question) VALUES (?, ?, ?)", default_questions)

    cursor.execute("SELECT COUNT(*) FROM auditeurs")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO auditeurs (nom) VALUES (?)", [("Jean Dupont",), ("Marie Curie",), ("Pierre Martin",)])

    cursor.execute("SELECT COUNT(*) FROM zones_5s")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO zones_5s (nom) VALUES (?)", [("Zone Assemblage",), ("Zone Usinage",), ("Magasin Stock",)])

    cursor.execute("SELECT COUNT(*) FROM machines_am")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO machines_am (nom) VALUES (?)", [("Presse 01",), ("CNC Haas 02",), ("Ligne Conditionnement 03",)])

    conn.commit()
    conn.close()

init_db()

# Session state initialisations
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

# ==========================================
# 3. GÉNÉRATION DE RAPPORT PDF (WEASYPRINT)
# ==========================================
def generate_pdf_report(audit_info, details_list):
    details_html_rows = ""
    for d in details_list:
        status_color = "#2e7d32" if d["statut"] == "OK" else "#c62828"
        bg_color = "#e8f5e9" if d["statut"] == "OK" else "#ffebee"
        
        img_html = ""
        if d.get("photo_path") and os.path.exists(d["photo_path"]):
            try:
                with open(d["photo_path"], "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    img_html = f'<img src="data:image/jpeg;base64,{encoded_string}" style="max-width: 120px; max-height: 90px; border-radius: 4px; border: 1px solid #ccc;"/>'
            except Exception:
                img_html = "<i>Erreur photo</i>"

        comment = d.get("commentaire") or "-"

        details_html_rows += f'''
        <tr>
            <td><b>{d["categorie"]}</b></td>
            <td>{d["question"]}</td>
            <td style="text-align: center; background-color: {bg_color}; color: {status_color}; font-weight: bold;">{d["statut"]}</td>
            <td>{comment}</td>
            <td style="text-align: center;">{img_html}</td>
        </tr>
        '''

    score = audit_info["score_pourcentage"]
    score_color = "#2e7d32" if score >= 80 else ("#f57c00" if score >= 60 else "#c62828")

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 15mm 12mm;
                background-color: #fafafa;
            }}
            *, *::before, *::after {{
                box-sizing: border-box;
            }}
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                color: #333;
            }}
            .header-banner {{
                background-color: #1e293b;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .header-banner h1 {{
                margin: 0 0 5px 0;
                font-size: 20pt;
            }}
            .header-banner p {{
                margin: 0;
                color: #cbd5e1;
                font-size: 11pt;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
                background-color: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .info-table td {{
                padding: 10px 14px;
                font-size: 10pt;
                border-bottom: 1px solid #f1f5f9;
            }}
            .score-box {{
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                margin-bottom: 20px;
                border: 2px solid {score_color};
            }}
            .score-val {{
                font-size: 24pt;
                font-weight: bold;
                color: {score_color};
            }}
            .data-table {{
                width: 100%;
                border-collapse: collapse;
                background-color: white;
                border-radius: 8px;
                overflow: hidden;
            }}
            .data-table th {{
                background-color: #0f172a;
                color: white;
                padding: 10px;
                font-size: 10pt;
                text-align: left;
            }}
            .data-table td {{
                padding: 8px 10px;
                font-size: 9pt;
                border-bottom: 1px solid #e2e8f0;
                vertical-align: middle;
            }}
            .section-title {{
                font-size: 13pt;
                color: #0f172a;
                border-left: 4px solid #2563eb;
                padding-left: 8px;
                margin-top: 15px;
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header-banner">
            <h1>RAPPORT D'AUDIT {audit_info["type_audit"]}</h1>
            <p>Rapport officiel de contrôle - Audit N° #{audit_info["id"]}</p>
        </div>

        <table class="info-table">
            <tr>
                <td><b>Date de contrôle :</b> {audit_info["date_audit"]}</td>
                <td><b>Périmètre / Machine :</b> {audit_info["zone_machine"]}</td>
            </tr>
            <tr>
                <td><b>Auditeur :</b> {audit_info["auditeur"]}</td>
                <td><b>Équipe / Post :</b> {audit_info["equipe"]}</td>
            </tr>
            <tr>
                <td><b>Semaine ISO :</b> Semaine {audit_info["semaine"]} - {audit_info["annee"]}</td>
                <td><b>Conformité :</b> {audit_info["total_ok"]} OK / {audit_info["total_nok"]} NOK ({audit_info["total_questions"]} Total)</td>
            </tr>
        </table>

        <div class="score-box">
            <span style="font-size: 11pt; color: #64748b; font-weight: bold;">TAUX DE CONFORMITÉ GLOBALE</span><br>
            <span class="score-val">{score}%</span>
        </div>

        <div class="section-title">Détail des Évaluations</div>
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width: 20%;">Catégorie</th>
                    <th style="width: 35%;">Question / Critère</th>
                    <th style="width: 10%; text-align: center;">Statut</th>
                    <th style="width: 20%;">Remarques / Actions</th>
                    <th style="width: 15%; text-align: center;">Photo</th>
                </tr>
            </thead>
            <tbody>
                {details_html_rows}
            </tbody>
        </table>
    </body>
    </html>
    '''
    
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes

# ==========================================
# 4. BARRE DE NAVIGATION
# ==========================================
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio(
    "Aller vers :",
    ["📋 Nouvel Audit (5S / AM)", "📜 Historique & Rapports PDF", "⚙️ Paramètres / Administration"]
)

# ==========================================
# PAGE 1 : FORMULAIRE D'AUDIT (5S / AM)
# ==========================================
if page == "📋 Nouvel Audit (5S / AM)":
    st.title("📋 Réalisation d'un Audit (5S / Auto Maintenance)")

    conn = get_db()
    auditeurs_list = [row["nom"] for row in conn.execute("SELECT nom FROM auditeurs ORDER BY nom").fetchall()]
    zones_list = [row["nom"] for row in conn.execute("SELECT nom FROM zones_5s ORDER BY nom").fetchall()]
    machines_list = [row["nom"] for row in conn.execute("SELECT nom FROM machines_am ORDER BY nom").fetchall()]
    conn.close()

    if not auditeurs_list:
        st.warning("⚠️ Aucun auditeur configuré. Veuillez en ajouter dans la page Paramètres.")
        st.stop()

    col_t1, col_t2 = st.columns(2)
    type_audit = col_t1.selectbox("Type d'Audit", ["5S", "AM"])
    
    if type_audit == "5S":
        zone_machine = col_t2.selectbox("Sélectionner la Zone 5S", zones_list if zones_list else ["Zone Défaut"])
    else:
        zone_machine = col_t2.selectbox("Sélectionner l'Équipement / Machine AM", machines_list if machines_list else ["Machine Défaut"])

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    auditeur = col_a1.selectbox("Auditeur", auditeurs_list)
    equipe = col_a2.selectbox("Équipe / Post", ["Matin", "Après-midi", "Nuit", "Journée"])
    today = datetime.date.today()
    semaine_iso = col_a3.number_input("Semaine ISO", min_value=1, max_value=53, value=today.isocalendar()[1])
    annee = col_a4.number_input("Année", min_value=2020, max_value=2030, value=today.year)

    st.divider()
    st.subheader(f"📝 Grille de contrôle {type_audit}")

    # Récupération des questions de la checklist
    conn = get_db()
    questions = conn.execute("SELECT * FROM checklists WHERE type_audit = ? ORDER BY categorie, id", (type_audit,)).fetchall()
    conn.close()

    if not questions:
        st.error(f"Aucune question configurée pour l'audit {type_audit}. Configurez la checklist dans la page Paramètres.")
        st.stop()

    # Formulaire de saisie dynamique
    with st.form("audit_form"):
        responses = {}
        for q in questions:
            st.markdown(f"**[{q['categorie']}]** {q['question']}")
            c1, c2, c3 = st.columns([2, 4, 4])
            
            statut = c1.radio(
                "Statut",
                ["OK", "NOK"],
                key=f"status_{q['id']}",
                horizontal=True,
                label_visibility="collapsed"
            )
            
            commentaire = c2.text_input(
                "Remarque / Action corrective",
                key=f"comm_{q['id']}",
                placeholder="Préciser l'anomalie ou l'action si NOK...",
                label_visibility="collapsed"
            )
            
            photo = c3.file_uploader(
                "Photo d'illustration",
                type=["png", "jpg", "jpeg"],
                key=f"photo_{q['id']}",
                label_visibility="collapsed"
            )
            
            responses[q['id']] = {
                "categorie": q['categorie'],
                "question": q['question'],
                "statut": statut,
                "commentaire": commentaire,
                "photo": photo
            }
            st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed #ddd;'/>", unsafe_allow_html=True)

        submitted = st.form_submit_button("✅ Valider et Enregistrer l'Audit", type="primary", use_container_width=True)

    if submitted:
        total_q = len(responses)
        total_ok = sum(1 for r in responses.values() if r["statut"] == "OK")
        total_nok = total_q - total_ok
        score_pct = round((total_ok / total_q) * 100, 2) if total_q > 0 else 0.0

        conn = get_db()
        cursor = conn.cursor()

        # Enregistrement de l'en-tête de l'audit
        cursor.execute('''
            INSERT INTO audits (date_audit, type_audit, zone_machine, auditeur, equipe, semaine, annee, total_questions, total_ok, total_nok, score_pourcentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (today.strftime("%Y-%m-%d"), type_audit, zone_machine, auditeur, equipe, semaine_iso, annee, total_q, total_ok, total_nok, score_pct))

        audit_id = cursor.lastrowid

        # Enregistrement des détails + Sauvegarde des photos localement
        details_for_pdf = []
        for q_id, r in responses.items():
            photo_path = ""
            if r["photo"] is not None:
                filename = f"audit_{audit_id}_q{q_id}_{int(datetime.datetime.now().timestamp())}.jpg"
                photo_path = os.path.join(UPLOAD_DIR, filename)
                with open(photo_path, "wb") as f:
                    f.write(r["photo"].getbuffer())

            cursor.execute('''
                INSERT INTO audit_details (audit_id, categorie, question, statut, commentaire, photo_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (audit_id, r["categorie"], r["question"], r["statut"], r["commentaire"], photo_path))

            details_for_pdf.append({
                "categorie": r["categorie"],
                "question": r["question"],
                "statut": r["statut"],
                "commentaire": r["commentaire"],
                "photo_path": photo_path
            })

        conn.commit()
        conn.close()

        st.success(f"🎉 Audit enregistré avec succès ! ID Audit : #{audit_id} - Score : {score_pct}%")

        # Génération du PDF
        audit_info = {
            "id": audit_id,
            "date_audit": today.strftime("%Y-%m-%d"),
            "type_audit": type_audit,
            "zone_machine": zone_machine,
            "auditeur": auditeur,
            "equipe": equipe,
            "semaine": semaine_iso,
            "annee": annee,
            "total_questions": total_q,
            "total_ok": total_ok,
            "total_nok": total_nok,
            "score_pourcentage": score_pct
        }

        pdf_data = generate_pdf_report(audit_info, details_for_pdf)

        st.download_button(
            label="📥 Télécharger le Rapport PDF de l'Audit",
            data=pdf_data,
            file_name=f"Rapport_{type_audit}_Audit_{audit_id}.pdf",
            mime="application/pdf",
            type="primary"
        )

# ==========================================
# PAGE 2 : HISTORIQUE & RÉGÉNÉRATION PDF
# ==========================================
elif page == "📜 Historique & Rapports PDF":
    st.title("📜 Historique des Audits & Régénération de PDF")
    st.markdown("Cliquez sur une ligne de l'historique ou sélectionnez son ID pour consulter les points non conformes et **régénérer immédiatement le rapport PDF**.")

    conn = get_db()
    audits_df = pd.read_sql_query('''
        SELECT 
            id AS "ID Audit",
            date_audit AS "Date",
            type_audit AS "Type",
            zone_machine AS "Zone / Machine",
            auditeur AS "Auditeur",
            score_pourcentage AS "Score (%)",
            total_ok AS "OK",
            total_nok AS "NOK"
        FROM audits ORDER BY id DESC
    ''', conn)
    conn.close()

    if audits_df.empty:
        st.info("Aucun audit n'a encore été enregistré.")
    else:
        # Affichage interactif
        event = st.dataframe(
            audits_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        selected_audit_id = None
        if event and event.get("selection") and event["selection"].get("rows"):
            selected_row_idx = event["selection"]["rows"][0]
            selected_audit_id = int(audits_df.iloc[selected_row_idx]["ID Audit"])

        st.divider()

        # Sélecteur d'ID
        all_ids = audits_df["ID Audit"].tolist()
        default_index = all_ids.index(selected_audit_id) if selected_audit_id in all_ids else 0

        chosen_id = st.selectbox(
            "🆔 Choisir l'ID de l'audit à consulter / régénérer :",
            options=all_ids,
            index=default_index
        )

        if chosen_id:
            conn = get_db()
            audit_row = conn.execute("SELECT * FROM audits WHERE id = ?", (chosen_id,)).fetchone()
            details_rows = conn.execute("SELECT * FROM audit_details WHERE audit_id = ? ORDER BY id", (chosen_id,)).fetchall()
            conn.close()

            audit_info = dict(audit_row)
            details_list = [dict(r) for r in details_rows]

            # Affichage de la synthèse
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Date", audit_info["date_audit"])
            col_m2.metric("Périmètre", audit_info["zone_machine"])
            col_m3.metric("Auditeur", audit_info["auditeur"])
            col_m4.metric("Score Conformité", f"{audit_info['score_pourcentage']}%")

            # Points NOK découverts
            nok_items = [d for d in details_list if d["statut"] == "NOK"]
            if nok_items:
                st.warning(f"⚠️ **{len(nok_items)} point(s) non conforme(s) trouvé(s) lors de cet audit :**")
                nok_df = pd.DataFrame(nok_items)[["categorie", "question", "commentaire"]]
                st.dataframe(nok_df, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Aucun point non conforme n'a été relevé lors de cet audit.")

            # Bouton de régénération du PDF
            st.markdown("### 📄 Génération & Téléchargement du Rapport PDF")
            
            pdf_bytes = generate_pdf_report(audit_info, details_list)

            st.download_button(
                label=f"📥 Télécharger le PDF de l'Audit #{chosen_id}",
                data=pdf_bytes,
                file_name=f"Rapport_{audit_info['type_audit']}_Audit_{chosen_id}.pdf",
                mime="application/pdf",
                type="primary"
            )

            # Option d'export de tout l'historique Excel
            st.divider()
            st.markdown("#### 📊 Export global")
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                audits_df.to_excel(writer, index=False, sheet_name='Audits')
            
            st.download_button(
                label="🟢 Exporter tout l'historique sous Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Historique_Audits_Export_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ==========================================
# PAGE 3 : PARAMÈTRES & ADMINISTRATION
# ==========================================
elif page == "⚙️ Paramètres / Administration":
    st.title("⚙️ Paramètres & Administration (Sécurisé)")

    conn = get_db()
    current_pass = conn.execute("SELECT valeur FROM config WHERE cle = 'admin_password'").fetchone()["valeur"]
    conn.close()

    if not st.session_state["admin_authenticated"]:
        input_pass = st.text_input("🔑 Entrez le mot de passe Administrateur :", type="password")
        if st.button("Se Connecter", type="primary"):
            if input_pass == current_pass:
                st.session_state["admin_authenticated"] = True
                st.success("Accès autorisé !")
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
        st.stop()

    if st.sidebar.button("🔒 Déconnexion Admin"):
        st.session_state["admin_authenticated"] = False
        st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "✏️ Édition / Suppression Audits",
        "❓ Checklists & Questions",
        "👤 Auditeurs & Référentiels",
        "📧 Destinataires Email",
        "🔐 Sécurité & Password"
    ])

    # TAB 1 : Édition & Suppression d'Audits
    with tab1:
        st.subheader("Édition ou Suppression d'Audits Passés")
        conn = get_db()
        audits = conn.execute("SELECT id, type_audit, date_audit, zone_machine FROM audits ORDER BY id DESC").fetchall()
        conn.close()

        if audits:
            audit_opts = {f"Audit #{a['id']} - {a['type_audit']} - {a['zone_machine']} ({a['date_audit']})": a['id'] for a in audits}
            selected_str = st.selectbox("Sélectionner un audit à gérer :", list(audit_opts.keys()))
            target_id = audit_opts[selected_str]

            c_del, c_space = st.columns([2, 8])
            if c_del.button("🗑️ Supprimer définitivement cet audit", type="primary"):
                conn = get_db()
                conn.execute("DELETE FROM audits WHERE id = ?", (target_id,))
                conn.execute("DELETE FROM audit_details WHERE audit_id = ?", (target_id,))
                conn.commit()
                conn.close()
                st.success(f"Audit #{target_id} supprimé !")
                st.rerun()

    # TAB 2 : Checklists & Questions
    with tab2:
        st.subheader("Gestion des Checklists 5S & Auto Maintenance")
        
        type_q = st.radio("Sélectionner le type :", ["5S", "AM"], horizontal=True)
        
        conn = get_db()
        questions_df = pd.read_sql_query("SELECT id AS ID, categorie AS Catégorie, question AS Question FROM checklists WHERE type_audit = ?", conn, params=(type_q,))
        conn.close()

        st.dataframe(questions_df, use_container_width=True, hide_index=True)

        st.markdown("#### Ajouter une nouvelle question")
        with st.form("add_question_form"):
            cat_input = st.text_input("Catégorie (ex: 1. Seiri, Sécurité, etc.)")
            q_input = st.text_input("Intitulé de la question")
            if st.form_submit_button("Ajouter la question"):
                if cat_input and q_input:
                    conn = get_db()
                    conn.execute("INSERT INTO checklists (type_audit, categorie, question) VALUES (?, ?, ?)", (type_q, cat_input, q_input))
                    conn.commit()
                    conn.close()
                    st.success("Question ajoutée !")
                    st.rerun()

        st.markdown("#### Supprimer une question")
        if not questions_df.empty:
            q_del_id = st.selectbox("Question à supprimer :", questions_df["ID"].tolist())
            if st.button("🗑️ Supprimer la question"):
                conn = get_db()
                conn.execute("DELETE FROM checklists WHERE id = ?", (q_del_id,))
                conn.commit()
                conn.close()
                st.success("Question supprimée !")
                st.rerun()

    # TAB 3 : Auditeurs & Zones/Machines
    with tab3:
        st.subheader("Gestion des Référentiels")
        col_r1, col_r2, col_r3 = st.columns(3)

        conn = get_db()
        
        # Auditeurs
        with col_r1:
            st.markdown("##### 👤 Auditeurs")
            aud_list = pd.read_sql_query("SELECT id, nom FROM auditeurs", conn)
            st.dataframe(aud_list, hide_index=True)
            new_aud = st.text_input("Nouveau nom :", key="new_aud")
            if st.button("Ajouter Auditeur"):
                if new_aud:
                    conn.execute("INSERT OR IGNORE INTO auditeurs (nom) VALUES (?)", (new_aud,))
                    conn.commit()
                    st.rerun()

        # Zones 5S
        with col_r2:
            st.markdown("##### 🏭 Zones 5S")
            z_list = pd.read_sql_query("SELECT id, nom FROM zones_5s", conn)
            st.dataframe(z_list, hide_index=True)
            new_z = st.text_input("Nouvelle Zone :", key="new_z")
            if st.button("Ajouter Zone"):
                if new_z:
                    conn.execute("INSERT OR IGNORE INTO zones_5s (nom) VALUES (?)", (new_z,))
                    conn.commit()
                    st.rerun()

        # Machines AM
        with col_r3:
            st.markdown("##### ⚙️ Machines AM")
            m_list = pd.read_sql_query("SELECT id, nom FROM machines_am", conn)
            st.dataframe(m_list, hide_index=True)
            new_m = st.text_input("Nouvelle Machine :", key="new_m")
            if st.button("Ajouter Machine"):
                if new_m:
                    conn.execute("INSERT OR IGNORE INTO machines_am (nom) VALUES (?)", (new_m,))
                    conn.commit()
                    st.rerun()

        conn.close()

    # TAB 4 : Email Destinataires
    with tab4:
        st.subheader("Destinataires des rapports automatiques")
        conn = get_db()
        emails_df = pd.read_sql_query("SELECT id, email FROM email_destinataires", conn)
        st.dataframe(emails_df, hide_index=True)

        new_email = st.text_input("Ajouter une adresse e-mail :")
        if st.button("Ajouter E-mail"):
            if new_email:
                conn.execute("INSERT OR IGNORE INTO email_destinataires (email) VALUES (?)", (new_email,))
                conn.commit()
                st.rerun()
        conn.close()

    # TAB 5 : Sécurité
    with tab5:
        st.subheader("Sécurité & Mot de passe Administration")
        new_pass = st.text_input("Nouveau mot de passe Administrateur :", type="password")
        if st.button("Modifier le mot de passe"):
            if new_pass:
                conn = get_db()
                conn.execute("UPDATE config SET valeur = ? WHERE cle = 'admin_password'", (new_pass,))
                conn.commit()
                conn.close()
                st.success("Mot de passe mis à jour !")
