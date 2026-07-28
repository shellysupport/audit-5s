import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# CONFIGURATION STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Gestion des Audits 5S & Auto Maintenance",
    page_icon="📋",
    layout="wide"
)

DB_NAME = "audits.db"

# ==============================================================================
# BASE DE DONNÉES & INITIALISATION
# ==============================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idp TEXT NOT NULL,
            type_audit TEXT NOT NULL,
            auditeur TEXT NOT NULL,
            zone TEXT NOT NULL,
            equipe TEXT NOT NULL,
            semaine INTEGER NOT NULL,
            annee INTEGER NOT NULL,
            date_audit TEXT NOT NULL,
            score_pourcentage REAL NOT NULL,
            nb_ok INTEGER NOT NULL,
            nb_nok INTEGER NOT NULL,
            total_questions INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# STRUCTURE DES QUESTIONS PAR TYPE D'AUDIT
# ==============================================================================
QUESTIONS_5S = {
    "1S - SEIRI (Eliminer)": [
        "Seul l'équipement/outillage nécessaire est présent sur le poste ?",
        "Les documents périmés ou inutiles sont retirés ?",
        "Les pièces défectueuses ou déchets sont débarrassés ?"
    ],
    "2S - SEITON (Ranger)": [
        "Chaque outil a une place définie et identifiée ?",
        "Les emplacelements au sol et étagères sont balisés ?",
        "Le matériel est facilement accessible et rangé après usage ?"
    ],
    "3S - SEISO (Nettoyer)": [
        "L'équipement et la zone sont propres (pas de fuite/poussière) ?",
        "Les outils de nettoyage sont disponibles et en bon état ?",
        "Les sources de salissure sont identifiées et traitées ?"
    ],
    "4S - SEIKETSU (Standardiser)": [
        "Les standards 5S sont affichés et visibles ?",
        "Les règles de rangement sont respectées par tous ?",
        "Les étiquettes et marquages sont lisibles et propres ?"
    ],
    "5S - SHITSUKE (Rigueur)": [
        "L'audit précédent a donné lieu à des actions correctives ?",
        "L'équipe applique spontanément les règles 5S ?"
    ]
}

QUESTIONS_AM = {
    "Inspection & Sécurité": [
        "Les dispositifs de sécurité (carters, paratonnerres) sont en place ?",
        "Aucune fuite d'huile, d'air ou de fluide constatée ?"
    ],
    "Lubrification & Niveaux": [
        "Les niveaux de fluide/lubrifiant sont conformes ?",
        "Les graisseurs sont propres et accessibles ?"
    ],
    "Fixation & État Général": [
        "Les boulons et assemblages ne présentent aucun jeu ?",
        "Les câbles et flexibles sont en bon état et bien fixés ?"
    ]
}

def get_questions_dict(type_code):
    return QUESTIONS_5S if type_code == "5S" else QUESTIONS_AM

# ==============================================================================
# GÉNÉRATION DU RAPPORT PDF
# ==============================================================================
def generate_pdf_report(title, idp, auditeur, zone, equipe, semaine, annee, reponses, q_dict, score_pct, ok_cnt, nok_cnt, total_q):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1,
        spaceAfter=15
    )

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        leading=14
    )

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )

    # Titre
    elements.append(Paragraph(f"RAPPORT D'AUDIT : {title.upper()}", title_style))
    elements.append(Spacer(1, 10))

    # Entête
    header_data = [
        [
            Paragraph(f"<b>IDP :</b> {idp}<br/><b>Auditeur :</b> {auditeur}<br/><b>Zone / Équipement :</b> {zone}", header_style),
            Paragraph(f"<b>Équipe :</b> {equipe}<br/><b>Période :</b> Semaine {semaine} - {annee}<br/><b>Date :</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", header_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[260, 260])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F3F4F6')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 15))

    # Tableau Résultats KPI
    kpi_data = [
        ["Total Questions", "OK (Conforme)", "NOK (Non-conforme)", "Score Global"],
        [str(total_q), str(ok_cnt), str(nok_cnt), f"{score_pct:.1f}%"]
    ]
    t_kpi = Table(kpi_data, colWidths=[130, 130, 130, 130])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_kpi)
    elements.append(Spacer(1, 20))

    # Détails des questions
    table_data = [["N°", "Question", "Statut", "Remarques"]]
    q_counter = 0

    for cat, questions in q_dict.items():
        table_data.append([Paragraph(f"<b>{cat}</b>", cell_style), "", "", ""])
        for q in questions:
            q_counter += 1
            data_q = reponses.get(q_counter, {"statut": "✓ OK / Conforme", "comment": ""})
            
            statut_txt = data_q["statut"]
            comment_txt = data_q["comment"] if data_q["comment"] else "-"

            table_data.append([
                str(q_counter),
                Paragraph(q, cell_style),
                Paragraph(statut_txt, cell_style),
                Paragraph(comment_txt, cell_style)
            ])

    t_questions = Table(table_data, colWidths=[30, 240, 110, 140])
    t_questions.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(t_questions)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ==============================================================================
# CONVERTISSEUR EXCEL
# ==============================================================================
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Historique Audits')
    output.seek(0)
    return output.getvalue()

# ==============================================================================
# BARRE LATÉRALE - NAVIGATION
# ==============================================================================
st.sidebar.title("📌 Menu")
page = st.sidebar.radio(
    "Navigation",
    ["📋 Audit 5S Hebdo", "🛠️ Audit Auto Maintenance", "📊 Historique des Audits", "⚙️ Paramètres / Admin"]
)

# ==============================================================================
# FONCTION GÉNÉRIQUE : Saisie des Audits (5S & AM)
# ==============================================================================
def render_audit_form(type_code, audit_title, questions_dict):
    st.title(f"📋 Formulaire {audit_title}")
    
    with st.form(f"form_audit_{type_code}"):
        st.subheader("1. Informations Générales")
        col1, col2, col3 = st.columns(3)
        with col1:
            idp = st.text_input("IDP / Identifiant Audit", value=f"022026{datetime.now().strftime('%H%M%S')}")
            auditeur = st.text_input("Nom de l'Auditeur")
        with col2:
            zone = st.text_input("Zone / Équipement")
            equipe = st.selectbox("Équipe", ["Équipe 1", "Équipe 2", "Équipe 3", "Jour"])
        with col3:
            semaine = st.number_input("Semaine", min_value=1, max_value=53, value=int(datetime.now().strftime("%V")))
            annee = st.number_input("Année", min_value=2024, max_value=2030, value=datetime.now().year)

        st.markdown("---")
        st.subheader("2. Grille d'Évaluation")

        reponses = {}
        q_counter = 0

        for cat, questions in questions_dict.items():
            st.markdown(f"#### 🔹 {cat}")
            for q in questions:
                q_counter += 1
                c1, c2, c3 = st.columns([3, 2, 3])
                with c1:
                    st.write(f"**Q{q_counter}.** {q}")
                with c2:
                    statut = st.radio(
                        f"Statut Q{q_counter}",
                        ["✓ OK / Conforme", "❌ NOK / Non conforme"],
                        key=f"st_{type_code}_{q_counter}",
                        label_visibility="collapsed"
                    )
                with c3:
                    comment = st.text_input(
                        f"Remarque Q{q_counter}",
                        key=f"cm_{type_code}_{q_counter}",
                        placeholder="Remarque / Action si NOK",
                        label_visibility="collapsed"
                    )
                reponses[q_counter] = {"statut": statut, "comment": comment}
            st.markdown("---")

        submitted = st.form_submit_button("💾 Enregistrer et Générer le Rapport PDF", type="primary")

    if submitted:
        if not auditeur or not zone:
            st.error("⚠️ Veuillez remplir le nom de l'auditeur et la zone / équipement.")
        else:
            ok_cnt = sum(1 for r in reponses.values() if "OK" in r["statut"])
            nok_cnt = sum(1 for r in reponses.values() if "NOK" in r["statut"])
            total_q = len(reponses)
            score_pct = (ok_cnt / total_q) * 100 if total_q > 0 else 0

            # Sauvegarde en BDD
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO historique_audits 
                (idp, type_audit, auditeur, zone, equipe, semaine, annee, date_audit, score_pourcentage, nb_ok, nb_nok, total_questions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (idp, type_code, auditeur, zone, equipe, semaine, annee, datetime.now().strftime("%Y-%m-%d %H:%M"), score_pct, ok_cnt, nok_cnt, total_q))
            conn.commit()
            conn.close()

            st.success(f"✅ Audit enregistré avec succès ! Score : {score_pct:.1f}%")

            # PDF
            pdf_data = generate_pdf_report(
                audit_title, idp, auditeur, zone, equipe, semaine, annee,
                reponses, questions_dict, score_pct, ok_cnt, nok_cnt, total_q
            )

            st.download_button(
                label="📄 Télécharger le Rapport PDF",
                data=pdf_data,
                file_name=f"Rapport_{type_code}_{zone}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf"
            )

# ==============================================================================
# PAGES DU FORMULAIRE
# ==============================================================================
if page == "📋 Audit 5S Hebdo":
    render_audit_form("5S", "Audit 5S Hebdo", QUESTIONS_5S)

elif page == "🛠️ Audit Auto Maintenance":
    render_audit_form("AM", "Audit Auto Maintenance", QUESTIONS_AM)

# ==============================================================================
# PAGE : HISTORIQUE DES AUDITS (AVEC SÉLECTION DE LIGNE ET RAPPORT PDF)
# ==============================================================================
elif page == "📊 Historique des Audits":
    st.title("📊 Historique des Audits Réalisés")

    conn = get_db_connection()
    df_history = pd.read_sql_query("SELECT * FROM historique_audits ORDER BY id DESC", conn)
    conn.close()

    if df_history.empty:
        st.info("Aucun audit n'a encore été enregistré dans l'historique.")
    else:
        # Filtres
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            type_filter = st.multiselect("Filtrer par type d'audit :", options=df_history['type_audit'].unique(), default=df_history['type_audit'].unique())
        with col_f2:
            zone_filter = st.multiselect("Filtrer par zone / équipement :", options=df_history['zone'].unique(), default=df_history['zone'].unique())

        filtered_df = df_history[
            (df_history['type_audit'].isin(type_filter)) & 
            (df_history['zone'].isin(zone_filter))
        ]

        # KPIs
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Nombre total d'audits", len(filtered_df))
        moyenne_score = filtered_df['score_pourcentage'].mean() if not filtered_df.empty else 0
        kpi2.metric("Moyenne Conformité (%)", f"{moyenne_score:.1f}%")
        kpi3.metric("Dernier audit", filtered_df['date_audit'].iloc[0] if not filtered_df.empty else "N/A")

        st.markdown("---")

        # Préparation dataframe d'affichage
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

        col_tbl, col_exp = st.columns([3, 1])
        with col_exp:
            excel_data = convert_df_to_excel(df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone / Équipement', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK', 'Total Questions']])
            st.download_button(
                label="📥 Exporter vers Excel",
                data=excel_data,
                file_name=f"historique_audits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.info("💡 **Astuce :** Cliquez sur une ligne du tableau ci-dessous pour la sélectionner et générer son rapport PDF.")

        # Tableau interactif avec mode de sélection
        selection = st.dataframe(
            df_display[['IDP', 'Type Audit', 'Auditeur', 'Zone / Équipement', 'Équipe', 'Semaine', 'Année', 'Date & Heure', 'Résultat (%)', 'OK', 'NOK']],
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun"
        )

        # Extraction de la ligne sélectionnée
        selected_rows = selection.get("selection", {}).get("rows", [])
        if selected_rows:
            selected_index = selected_rows[0]
            selected_audit_row = df_display.iloc[selected_index]

            st.markdown("---")
            st.subheader(f"📄 Audit Sélectionné : IDP #{selected_audit_row['IDP']}")

            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"**Type :** {selected_audit_row['Type Audit']}")
            c2.write(f"**Emplacement :** {selected_audit_row['Zone / Équipement']}")
            c3.write(f"**Auditeur :** {selected_audit_row['Auditeur']}")
            c4.write(f"**Résultat :** {selected_audit_row['Résultat (%)']}%")

            # Récupération des questions selon le type d'audit
            type_code = selected_audit_row['Type Audit']
            audit_title_pdf = f"Audit {type_code} Hebdo" if type_code == "5S" else "Audit Auto Maintenance"
            q_dict = get_questions_dict(type_code)

            # Reconstitution des questions pour l'impression PDF
            reponses_simulees = {}
            q_counter = 0
            for cat, questions in q_dict.items():
                for q in questions:
                    q_counter += 1
                    reponses_simulees[q_counter] = {
                        "statut": "✓ OK / Conforme",
                        "comment": ""
                    }

            pdf_bytes = generate_pdf_report(
                audit_title_pdf,
                selected_audit_row['IDP'],
                selected_audit_row['Auditeur'],
                selected_audit_row['Zone / Équipement'],
                selected_audit_row['Équipe'],
                selected_audit_row['Semaine'],
                selected_audit_row['Année'],
                reponses_simulees,
                q_dict,
                selected_audit_row['Résultat (%)'],
                selected_audit_row['OK'],
                selected_audit_row['NOK'],
                selected_audit_row['OK'] + selected_audit_row['NOK']
            )

            st.download_button(
                label=f"📄 Extaire / Télécharger le Rapport PDF ({selected_audit_row['IDP']})",
                data=pdf_bytes,
                file_name=f"Rapport_{type_code}_{selected_audit_row['Zone / Équipement']}_S{selected_audit_row['Semaine']}.pdf",
                mime="application/pdf",
                use_container_width=False,
                type="primary"
            )

# ==============================================================================
# PAGE : PARAMÈTRES / ADMIN
# ==============================================================================
elif page == "⚙️ Paramètres / Admin":
    st.title("⚙️ Administration & Base de Données")
    st.write("Gérez les paramètres de l'application et les données sauvegardées.")

    st.subheader("🗑️ Réinitialiser la Base de Données")
    if st.button("Purger tout l'historique", type="primary"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historique_audits")
        conn.commit()
        conn.close()
        st.success("La base de données a été purgée.")
