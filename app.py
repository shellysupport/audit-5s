import streamlit as st
import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Audit 5S Hebdo",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLES CSS SECURISE & STRUCTURE ---
st.markdown("""
    <style>
    /* Arrière-plan principal */
    .stApp { 
        background-color: #f8fafc; 
    }
    
    /* En-tête des catégories (S1, S2, etc.) */
    .s-header { 
        display: flex; 
        align-items: center; 
        gap: 10px; 
        margin-top: 30px; 
        margin-bottom: 15px; 
    }
    .badge-s { 
        background-color: #0f172a; 
        color: white; 
        font-weight: 800; 
        padding: 6px 12px; 
        border-radius: 8px; 
        font-size: 14px; 
    }
    .s-title-text { 
        font-size: 18px; 
        font-weight: 800; 
        color: #0f172a; 
        letter-spacing: -0.3px; 
    }

    /* Cartes de prévisualisation & métriques */
    .info-grid { 
        display: grid; 
        grid-template-columns: 1fr 1fr; 
        gap: 12px; 
        margin-bottom: 20px; 
    }
    .info-card { 
        background-color: #ffffff; 
        border: 1px solid #e2e8f0; 
        border-radius: 10px; 
        padding: 12px 16px; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.02); 
    }
    .info-label { 
        font-size: 11px; 
        font-weight: 700; 
        color: #64748b; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
    }
    .info-val { 
        font-size: 15px; 
        font-weight: 800; 
        color: #0f172a; 
        margin-top: 2px; 
    }
    .info-val-nok { 
        font-size: 15px; 
        font-weight: 800; 
        color: #dc2626; 
        margin-top: 2px; 
    }

    /* Bannière de Score Finale */
    .score-banner { 
        background-color: #0f172a; 
        color: white; 
        border-radius: 12px; 
        padding: 24px; 
        text-align: center; 
        margin: 20px 0; 
    }
    .score-percent { 
        font-size: 56px; 
        font-weight: 900; 
        line-height: 1; 
        margin-bottom: 6px; 
    }
    .score-subtitle { 
        font-size: 12px; 
        font-weight: 800; 
        letter-spacing: 1px; 
        color: #94a3b8; 
        text-transform: uppercase; 
    }
    .score-detail { 
        font-size: 14px; 
        font-weight: 600; 
        margin-top: 8px; 
        color: #cbd5e1; 
    }

    /* Boutons de soumission et UI */
    div.stButton > button { 
        border-radius: 8px; 
        font-weight: 700; 
    }
    </style>
""", unsafe_allow_html=True)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("📌 Menu")
page = st.sidebar.radio(
    "Navigation",
    ["Audit 5S Hebdo", "Audit Auto Maintenance", "Paramètres / Admin"]
)

# --- PAGE : AUDIT 5S HEBDO ---
if page == "Audit 5S Hebdo":
    st.title("Audit 5S Hebdo")

    # Définition des questions
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
            # Affichage de l'en-tête de section s'il change
            if q["section"] != current_section:
                current_section = q["section"]
                st.markdown(f"""
                    <div class="s-header">
                        <span class="badge-s">📌</span>
                        <span class="s-title-text">{current_section}</span>
                    </div>
                """, unsafe_allow_html=True)

            # Intitulé de la question
            st.markdown(f"**{q['text']}**")

            # Choix OK / NOK (Segmented Control si dispo, sinon Radio)
            if hasattr(st, "segmented_control"):
                status = st.segmented_control(
                    label=q['text'],
                    options=["✓ OK / Conforme", "✗ NOK / Non conforme"],
                    key=f"val_{q['id']}",
                    label_visibility="collapsed"
                )
            else:
                status = st.radio(
                    label=q['text'],
                    options=["✓ OK / Conforme", "✗ NOK / Non conforme"],
                    key=f"val_{q['id']}",
                    label_visibility="collapsed",
                    horizontal=True
                )

            answers[q["id"]] = status

            # Champs conditionnels si NOK ou besoin de précision
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

        # Bouton de soumission du formulaire
        submitted = st.form_submit_button("💾 Enregistrer l'audit", use_container_width=True, type="primary")

    if submitted:
        # Calcul du score
        total_questions = len(questions_5s)
        ok_count = sum(1 for v in answers.values() if v and "OK" in v)
        nok_count = sum(1 for v in answers.values() if v and "NOK" in v)
        score_percent = round((ok_count / total_questions) * 100) if total_questions > 0 else 0

        st.success("Audit enregistré avec succès !")

        # Affichage du score final
        st.markdown(f"""
            <div class="score-banner">
                <div class="score-percent">{score_percent}%</div>
                <div class="score-subtitle">SCORE GLOBAL 5S</div>
                <div class="score-detail">Conformes: {ok_count} / {total_questions} | Non-conformes: {nok_count}</div>
            </div>
        """, unsafe_allow_html=True)

# --- PAGES SECONDAIRES ---
elif page == "Audit Auto Maintenance":
    st.title("Audit Auto Maintenance")
    st.info("Module Auto Maintenance en cours de configuration.")

elif page == "Paramètres / Admin":
    st.title("Paramètres / Administration")
    st.info("Espace réservé à la gestion des utilisateurs et des bases de données.")
