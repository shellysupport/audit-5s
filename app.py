import streamlit as st

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Audit 5S Hebdo",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("📌 Menu")
page = st.sidebar.radio(
    "Navigation",
    ["Audit 5S Hebdo", "Audit Auto Maintenance", "Paramètres / Admin"]
)

# --- PAGE : AUDIT 5S HEBDO ---
if page == "Audit 5S Hebdo":
    st.title("Audit 5S Hebdo")

    questions_5s = [
        # S1 - DÉBARRASSER
        {"id": "q1", "section": "S1 – DÉBARRASSER", "text": "1. Est-ce qu'il y a du matériel / fournitures / machines / équipement inutiles ?"},
        {"id": "q2", "section": "S1 – DÉBARRASSER", "text": "2. Est-ce qu'il y a du matériel / fourniture / machines / équipement Endommagé ?"},
        
        # S2 - RANGER
        {"id": "q3", "section": "S2 – RANGER", "text": "3. Chaque objet a-t-il une place définie et clairement identifiée ?"},
        {"id": "q4", "section": "S2 – RANGER", "text": "4. Les outils et équipements sont-ils rangés à leur place après utilisation ?"},

        # S3 - NETTOYER
        {"id": "q5", "section": "S3 – NETTOYER", "text": "5. Le poste de travail et le sol sont-ils propres et exempts de déchets ?"},
        {"id": "q6", "section": "S3 – NETTOYER", "text": "6. Les équipements de nettoyage sont-ils disponibles et en bon état ?"},

        # S4 - STANDARDISER
        {"id": "q7", "section": "S4 – STANDARDISER", "text": "7. Les standards 5S sont-ils affichés et visibles par l'équipe ?"},

        # S5 - RESPECTER
        {"id": "q8", "section": "S5 – RESPECTER", "text": "8. Les règles 5S sont-elles suivies au quotidien sans rappel ?"}
    ]

    answers = {}
    photos = {}
    observations = {}

    current_section = None

    with st.form("audit_form"):
        for q in questions_5s:
            # Séparateurs de sections
            if q["section"] != current_section:
                current_section = q["section"]
                st.subheader(f"📌 {current_section}")

            st.write(f"**{q['text']}**")

            # Boutons radio natifs Streamlit (sans CSS injecté)
            status = st.radio(
                label=q['text'],
                options=["✓ OK / Conforme", "✗ NOK / Non conforme"],
                key=f"val_{q['id']}",
                label_visibility="collapsed",
                horizontal=True
            )

            answers[q["id"]] = status

            col_photo, col_obs = st.columns([1, 1])
            with col_photo:
                photo = st.file_uploader(
                    "📷 PRENDRE / JOINDRE UNE PHOTO", 
                    type=["png", "jpg", "jpeg"], 
                    key=f"photo_{q['id']}"
                )
                if photo:
                    photos[q["id"]] = photo

            with col_obs:
                obs = st.text_input(
                    "Observation / Actions à accomplir", 
                    placeholder="Observation (optionnel)", 
                    key=f"obs_{q['id']}"
                )
                if obs:
                    observations[q["id"]] = obs

            st.divider()

        submitted = st.form_submit_button("💾 Enregistrer l'audit", use_container_width=True, type="primary")

    if submitted:
        total_questions = len(questions_5s)
        ok_count = sum(1 for v in answers.values() if v and "OK" in v)
        nok_count = sum(1 for v in answers.values() if v and "NOK" in v)
        score_percent = round((ok_count / total_questions) * 100) if total_questions > 0 else 0

        st.success("Audit enregistré avec succès !")
        st.metric(label="Score Global 5S", value=f"{score_percent}%", delta=f"{ok_count}/{total_questions} OK")

# --- PAGES SECONDAIRES ---
elif page == "Audit Auto Maintenance":
    st.title("Audit Auto Maintenance")
    st.info("Module Auto Maintenance en cours de configuration.")

elif page == "Paramètres / Admin":
    st.title("Paramètres / Administration")
    st.info("Espace réservé à la gestion des utilisateurs et des bases de données.")
