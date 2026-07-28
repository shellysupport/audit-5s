import streamlit as st
import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Gestion des Audits 5S & Auto Maintenance",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLES CSS PROPRES & SÉCURISÉS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    
    /* En-têtes de sections 5S */
    .s-header { 
        display: flex; 
        align-items: center; 
        gap: 10px; 
        margin-top: 25px; 
        margin-bottom: 15px; 
        background-color: #0f172a;
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
    }
    .s-title-text { 
        font-size: 16px; 
        font-weight: 700; 
        letter-spacing: 0.5px; 
    }

    /* Carte d'en-tête (Auditeur, Ligne, etc.) */
    .header-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 20px;
    }

    /* Bannière de Score */
    .score-banner { 
        background-color: #0f172a; 
        color: white; 
        border-radius: 12px; 
        padding: 24px; 
        text-align: center; 
        margin: 20px 0; 
    }
    .score-percent { 
        font-size: 52px; 
        font-weight: 900; 
        line-height: 1; 
        margin-bottom: 6px; 
    }
    .score-detail { 
        font-size: 14px; 
        font-weight: 600; 
        color: #cbd5e1; 
    }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio(
    "Menu principal",
    ["Audit 5S Hebdo", "Audit Auto Maintenance", "Paramètres / Admin"]
)

# Initialisation du stockage en session si inexistant
if "audits_5s" not in st.session_state:
    st.session_state["audits_5s"] = []

if "audits_am" not in st.session_state:
    st.session_state["audits_am"] = []


# ==============================================================================
# PAGE 1 : AUDIT 5S HEBDO
# ==============================================================================
if page == "Audit 5S Hebdo":
    st.title("📌 Audit 5S Hebdomadaire")
    st.write("Renseignez les informations de l'audit et évaluez chaque critère.")

    today = datetime.date.today()
    current_week = today.isocalendar()[1]

    with st.form("audit_5s_form"):
        # --- BLOC EN-TÊTE DE L'AUDIT ---
        st.subheader("📋 Informations Générales")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            auditeur = st.text_input("👤 Auditeur", placeholder="Nom & Prénom")
        with col2:
            ligne = st.selectbox(
                "🏭 Ligne / Zone", 
                ["Ligne A", "Ligne B", "Ligne C", "Magasin", "Atelier Maintenance", "Autre"]
            )
        with col3:
            semaine = st.number_input("📅 Semaine N°", min_value=1, max_value=53, value=int(current_week))
        with col4:
            date_audit = st.date_input("📆 Date de l'audit", value=today)

        st.divider()

        # --- QUESTIONNAIRE 5S ---
        questions_5s = [
            # S1
            {"id": "q1", "section": "S1 – DÉBARRASSER (Seiri)", "text": "1. Y a-t-il du matériel, fournitures ou équipements inutiles sur le poste ?"},
            {"id": "q2", "section": "S1 – DÉBARRASSER (Seiri)", "text": "2. Les équipements endommagés ou hors d'usage sont-ils évacués ?"},
            # S2
            {"id": "q3", "section": "S2 – RANGER (Seiton)", "text": "3. Chaque outil/objet a-t-il une place définie et clairement identifiée ?"},
            {"id": "q4", "section": "S2 – RANGER (Seiton)", "text": "4. Les outils et équipements sont-ils bien remis à leur place après usage ?"},
            # S3
            {"id": "q5", "section": "S3 – NETTOYER (Seiso)", "text": "5. Le poste de travail et le sol sont-ils propres et exempts de fuites/déchets ?"},
            {"id": "q6", "section": "S3 – NETTOYER (Seiso)", "text": "6. Le matériel de nettoyage est-il disponible, propre et rangé ?"},
            # S4
            {"id": "q7", "section": "S4 – STANDARDISER (Seiketsu)", "text": "7. Les standards d'organisation et marquages au sol sont-ils respectés et lisibles ?"},
            # S5
            {"id": "q8", "section": "S5 – RESPECTER (Shitsuke)", "text": "8. Les règles 5S sont-elles appliquées en routine par l'équipe ?"}
        ]

        answers = {}
        photos = {}
        observations = {}
        current_section = None

        for q in questions_5s:
            if q["section"] != current_section:
                current_section = q["section"]
                st.markdown(f'<div class="s-header"><span class="s-title-text">{current_section}</span></div>', unsafe_allow_html=True)

            st.write(f"**{q['text']}**")

            status = st.radio(
                label=q['text'],
                options=["✓ OK / Conforme", "✗ NOK / Non conforme"],
                key=f"val_{q['id']}",
                label_visibility="collapsed",
                horizontal=True
            )
            answers[q["id"]] = status

            c_photo, c_obs = st.columns([1, 1])
            with c_photo:
                photo = st.file_uploader("📷 Photo (si anomalie/preuve)", type=["png", "jpg", "jpeg"], key=f"photo_{q['id']}")
                if photo:
                    photos[q["id"]] = photo.name
            with c_obs:
                obs = st.text_input("📝 Remarque / Action corrective", placeholder="Observation...", key=f"obs_{q['id']}")
                if obs:
                    observations[q["id"]] = obs

            st.write("---")

        submitted = st.form_submit_button("💾 Enregistrer l'Audit 5S", use_container_width=True, type="primary")

    if submitted:
        if not auditeur:
            st.error("⚠️ Veuillez renseigner le nom de l'auditeur avant d'enregistrer.")
        else:
            total_q = len(questions_5s)
            ok_cnt = sum(1 for v in answers.values() if v and "OK" in v)
            nok_cnt = sum(1 for v in answers.values() if v and "NOK" in v)
            score = round((ok_cnt / total_q) * 100) if total_q > 0 else 0

            record = {
                "auditeur": auditeur,
                "ligne": ligne,
                "semaine": semaine,
                "date": str(date_audit),
                "score": score,
                "ok": ok_cnt,
                "nok": nok_cnt,
                "reponses": answers,
                "observations": observations
            }
            st.session_state["audits_5s"].append(record)

            st.success(f"Audit enregistré pour {auditeur} ({ligne} - Semaine {semaine}) !")
            
            st.markdown(f"""
                <div class="score-banner">
                    <div class="score-percent">{score}%</div>
                    <div class="score-detail">SCORE GLOBAL 5S — Conformes: {ok_cnt}/{total_q} | Non-conformes: {nok_cnt}</div>
                </div>
            """, unsafe_allow_html=True)


# ==============================================================================
# PAGE 2 : AUDIT AUTO MAINTENANCE
# ==============================================================================
elif page == "Audit Auto Maintenance":
    st.title("🔧 Audit Auto Maintenance")
    st.write("Vérification des niveaux, organes de sécurité et points de graissage/nettoyage machine.")

    today = datetime.date.today()
    current_week = today.isocalendar()[1]

    with st.form("audit_am_form"):
        st.subheader("📋 Informations Générales")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            operateur = st.text_input("👤 Opérateur / Auditeur", placeholder="Nom & Prénom")
        with col2:
            machine = st.selectbox("⚙️ Machine / Équipement", ["Presse 01", "Ligne d'assemblage", "Robot de soudure", "Convoyeur Principal", "Autre"])
        with col3:
            semaine = st.number_input("📅 Semaine N°", min_value=1, max_value=53, value=int(current_week))
        with col4:
            date_audit = st.date_input("📆 Date", value=today)

        st.divider()
        st.subheader("🔍 Points de contrôle Auto Maintenance")

        points_am = [
            "1. Vérification des niveaux d'huile et lubrifiants",
            "2. Absences de fuites (Air, Huile, Eau)",
            "3. Propreté des capteurs et cellules de détection",
            "4. Contrôle des arrêts d'urgence et carters de sécurité",
            "5. État des tuyaux, câbles et raccordements pneumatiques",
            "6. Vérification des bruits ou vibrations anormaux"
        ]

        am_answers = {}
        am_obs = {}

        for idx, pt in enumerate(points_am, 1):
            st.write(f"**{pt}**")
            res = st.radio(
                f"Status {idx}",
                ["✓ OK / Conforme", "✗ NOK / Non conforme"],
                key=f"am_val_{idx}",
                label_visibility="collapsed",
                horizontal=True
            )
            am_answers[f"pt_{idx}"] = res
            
            rem = st.text_input("Remarque / Remède immédiat", key=f"am_obs_{idx}", placeholder="Détail du problème si NOK...")
            if rem:
                am_obs[f"pt_{idx}"] = rem
            st.write("---")

        submit_am = st.form_submit_button("💾 Enregistrer la Fiche Auto Maintenance", use_container_width=True, type="primary")

    if submit_am:
        if not operateur:
            st.error("⚠️ Veuillez saisir le nom de l'opérateur.")
        else:
            total_pts = len(points_am)
            ok_cnt = sum(1 for v in am_answers.values() if "OK" in v)
            nok_cnt = total_pts - ok_cnt
            score = round((ok_cnt / total_pts) * 100)

            record = {
                "operateur": operateur,
                "machine": machine,
                "semaine": semaine,
                "date": str(date_audit),
                "score": score,
                "ok": ok_cnt,
                "nok": nok_cnt
            }
            st.session_state["audits_am"].append(record)

            st.success(f"Fiche Auto Maintenance enregistrée pour {machine} !")
            st.metric("Taux de Conformité Machine", f"{score}%", f"{ok_cnt}/{total_pts} points conformes")


# ==============================================================================
# PAGE 3 : PARAMÈTRES / ADMIN
# ==============================================================================
elif page == "Paramètres / Admin":
    st.title("⚙️ Administration & Historique des Audits")

    tab1, tab2 = st.tabs(["📊 Historique Audits 5S", "🛠️ Historique Auto Maintenance"])

    with tab1:
        st.subheader("Audits 5S Enregistrés")
        if len(st.session_state["audits_5s"]) == 0:
            st.info("Aucun audit 5S n'a encore été enregistré durant cette session.")
        else:
            for i, item in enumerate(reversed(st.session_state["audits_5s"]), 1):
                with st.expander(f"Audit #{len(st.session_state['audits_5s']) - i + 1} - {item['ligne']} (Semaine {item['semaine']}) - Score : {item['score']}%"):
                    st.write(f"**Auditeur :** {item['auditeur']}")
                    st.write(f"**Date :** {item['date']}")
                    st.write(f"**Conformes :** {item['ok']} | **Non-Conformes :** {item['nok']}")
                    if item["observations"]:
                        st.write("**Observations saisies :**")
                        st.json(item["observations"])

    with tab2:
        st.subheader("Audits Auto Maintenance Enregistrés")
        if len(st.session_state["audits_am"]) == 0:
            st.info("Aucune fiche auto maintenance enregistrée pour le moment.")
        else:
            for i, item in enumerate(reversed(st.session_state["audits_am"]), 1):
                with st.expander(f"Machine : {item['machine']} (Semaine {item['semaine']}) - Conformité : {item['score']}%"):
                    st.write(f"**Opérateur :** {item['operateur']}")
                    st.write(f"**Date :** {item['date']}")
                    st.write(f"**Points OK :** {item['ok']} / Points NOK : {item['nok']}")
