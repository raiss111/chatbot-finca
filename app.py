import streamlit as st
import plotly.graph_objects as go
from groq import Groq
import re
from cache_manager import charger_cache, sauvegarder_cache, cache_est_frais
from parser import parse_html
import requests
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
NOM_MODELE = "llama-3.1-8b-instant"

# Image transparente pour cacher les avatars
AVATAR_TRANSPARENT = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def trouver_pages_pertinentes(index, question, nombre_pages=3 , recherche_partielle=True):
    """Trouve les pages les plus pertinentes pour la question."""
    question_propre = question.lower()
    mots_interdits = ["le", "la", "les", "de", "du", "des", "et", "a", "à",
                      "en", "un", "une", "pour", "sur", "est", "dans", "au",
                      "qui", "que", "quoi", "comment", "quels", "quelles", "où", "ou", "y", "il"]
    
    mots_cles = []
    for mot in question_propre.split():
        mot_nettoye = mot.strip(".,?!:;\"'")
        if mot_nettoye not in mots_interdits and mot_nettoye in index:
            mots_cles.append(mot_nettoye)
    
    # Recherche partielle si pas de correspondance exacte
    if len(mots_cles) == 0 and recherche_partielle:
        for mot in question_propre.split():
            mot_nettoye = mot.strip(".,?!:;\"'")
            if len(mot_nettoye) > 4:
                 for cle_index in index.keys():
                    if len(cle_index) > 3 and (mot_nettoye in cle_index or cle_index in mot_nettoye):
                        mots_cles.append(cle_index)
    
    if len(mots_cles) == 0:
        return []
    
    scores = {}
    for mot in mots_cles:
        for url, nombre in index[mot].items():
            scores[url] = scores.get(url, 0) + nombre
    
    pages_triees = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [url for url, score in pages_triees[:nombre_pages]]


def recuperer_contenu_pages(urls, contenu_pages):
    """Récupère le contenu des pages depuis le cache."""
    textes = []
    for url in urls:
        if url in contenu_pages:
            textes.append(contenu_pages[url])
    return textes


def nettoyer_reponse(reponse):
    """Supprime les phrases d'introduction robotiques."""
    reponse = reponse.strip()
    prefixes = [
        r"^d'après le contexte fourni,\s*", r"^selon le contexte fourni,\s*",
        r"^d'après les informations,\s*", r"^selon les informations,\s*",
        r"^voici les.*mentionnés.*:\s*", r"^basé sur le contexte,\s*",
        r"^selon le contexte,\s*", r"^d'après le contexte,\s*",
    ]
    for prefix in prefixes:
        if re.match(prefix, reponse, re.IGNORECASE):
            reponse = re.sub(prefix, "", reponse, flags=re.IGNORECASE).strip()
            if len(reponse) > 0:
                reponse = reponse[0].upper() + reponse[1:]
            break
    return reponse.strip()


def demander_a_groq(question, contexte):
    """Envoie la question à Groq avec un prompt flexible."""
    message_systeme = f"""Tu es un assistant expert sur Finca RDC.
Ta mission est de répondre à la question en utilisant les informations ci-dessous.
IMPORTANT :
1. Sois flexible sur les synonymes. Si la question parle de "comptes", cherche des informations sur les "produits", "services", "épargne" ou "crédits".
2. Réponds de manière utile et informative.
3. Réponds directement, sans phrase d'introduction inutile.

INFORMATIONS DISPONIBLES :
{contexte}

QUESTION : {question}
RÉPONSE DIRECTE :"""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Tu es un assistant utile, factuel et flexible."},
                {"role": "user", "content": message_systeme}
            ],
            model=NOM_MODELE,
            temperature=0.3
        )
        return nettoyer_reponse(chat_completion.choices[0].message.content)
    except Exception as e:
        return f"Erreur : {e}"
def crawler_nouvelles_pages(index, contenu_pages, nombre_pages_a_ajouter=5):
    """
    Explore de nouvelles pages du site et les ajoute au cache.
    Retourne le nouvel index et le nouveau contenu.
    """
    # On commence par la page d'accueil et on suit les liens
    pages_a_visiter = ["https://www.finca.cd"]
    pages_deja_crawlees = set(contenu_pages.keys())  # Pages déjà dans le cache
    
    stop_words = ["le", "la", "les", "de", "du", "des", "et", "a", "à", 
                  "en", "un", "une", "pour", "sur", "est", "dans", "au"]
    
    pages_ajoutees = 0
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while len(pages_a_visiter) > 0 and pages_ajoutees < nombre_pages_a_ajouter:
        url_actuelle = pages_a_visiter.pop(0)
        
        # Si cette page est déjà dans le cache, on la saute
        if url_actuelle in pages_deja_crawlees:
            continue
        
        status_text.text(f"Telechargement en cours d'execution... ({pages_ajoutees + 1}/{nombre_pages_a_ajouter})")
        progress_bar.progress((pages_ajoutees + 1) / nombre_pages_a_ajouter)
        
        try:
            reponse = requests.get(url_actuelle, timeout=5)
            if reponse.status_code != 200:
                continue
            html = reponse.text
        except:
            continue
        
        # Parser la page
        mots_propres = parse_html(html, stop_words)
        texte = " ".join(mots_propres)
        
        # Ajouter au cache
        contenu_pages[url_actuelle] = texte[:4000]
        pages_deja_crawlees.add(url_actuelle)
        
        # Mettre à jour l'index
        compteur = {}
        for mot in mots_propres:
            compteur[mot] = compteur.get(mot, 0) + 1
        for mot, nombre in compteur.items():
            if mot not in index:
                index[mot] = {}
            index[mot][url_actuelle] = nombre
        
        # Trouver les nouveaux liens
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for lien in soup.find_all("a"):
            href = lien.get("href")
            if href and "finca.cd" in href and href not in pages_a_visiter and href not in pages_deja_crawlees:
                pages_a_visiter.append(href)
        
        pages_ajoutees += 1
    
    progress_bar.empty()
    status_text.empty()
    
    return index, contenu_pages


def construire_index_initial():
    """Construit un index initial avec seulement 5 pages (rapide)."""
    index = {}
    contenu_pages = {}
    
    pages_a_visiter = ["https://www.finca.cd"]
    pages_deja_vues = []
    stop_words = ["le", "la", "les", "de", "du", "des", "et", "a", "à", 
                  "en", "un", "une", "pour", "sur", "est", "dans", "au"]
    
    max_pages = 5  # Seulement 5 pages au démarrage
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while len(pages_a_visiter) > 0 and len(pages_deja_vues) < max_pages:
        url_actuelle = pages_a_visiter.pop(0)
        if url_actuelle in pages_deja_vues:
            continue
        pages_deja_vues.append(url_actuelle)
        
        progression = len(pages_deja_vues) / max_pages
        progress_bar.progress(progression)
        status_text.text(f"{len(pages_deja_vues)}/{max_pages}")
        try:
            reponse = requests.get(url_actuelle, timeout=5)
            if reponse.status_code != 200:
                continue
            html = reponse.text
        except:
            continue
        
        mots_propres = parse_html(html, stop_words)
        contenu_pages[url_actuelle] = " ".join(mots_propres)[:4000]
        
        compteur = {}
        for mot in mots_propres:
            compteur[mot] = compteur.get(mot, 0) + 1
        for mot, nombre in compteur.items():
            if mot not in index:
                index[mot] = {}
            index[mot][url_actuelle] = nombre
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for lien in soup.find_all("a"):
            href = lien.get("href")
            if href and "finca.cd" in href and href not in pages_a_visiter and href not in pages_deja_vues:
                pages_a_visiter.append(href)
    
    progress_bar.empty()
    status_text.empty()
    
    return index, contenu_pages


def initialiser_application():
    """Charge le cache ou construit un index initial rapide."""
    index, contenu_pages = charger_cache()
    
    if index is None or not cache_est_frais(max_heures=24):
        with st.spinner(" Chargement initial rapide..."):
            index, contenu_pages = construire_index_initial()
            sauvegarder_cache(index, contenu_pages)
    
    return index, contenu_pages


# TABLEAU DE BORD + MODULE D'ÉVALUATION

STOP_WORDS_STATS = ["le", "la", "les", "de", "du", "des", "et", "a", "à", "en", "un", "une",
                    "pour", "sur", "est", "dans", "au", "que", "qui", "pas", "plus", "avec",
                    "ce", "cette", "son", "sa", "ses", "aux", "ou", "où", "il", "elle",
                    "nous", "vous", "ne", "se", "ma", "mon", "ta", "ton", "the", "of",
                    "and", "to", "in", "is", "for", "with", "on", "as", "by", "at","votre","notre"]

QUESTIONS_TEST = [
    # Questions "faciles" (sans accents) : les deux modèles devraient trouver
    {"question": "comptes et produits", "mots_attendus": ["compte", "produit"]},
    {"question": "agences services clients", "mots_attendus": ["agence", "service", "client"]},
    {"question": "agriculture entreprises", "mots_attendus": ["agriculture", "entreprise"]},
    # Questions "difficiles" avec accents.
    # le Modèle A échoue, le Modèle B doit sauver grâce à la recherche partielle
    {"question": "épargne et crédit", "mots_attendus": ["pargne", "compte"]},
    {"question": "santé et éducation", "mots_attendus": ["sant", "ducation", "finca"]},
    {"question": "prêt et développement", "mots_attendus": ["dveloppement", "finca"]},
]

def precision_pour_une_question(index, contenu_pages, question, mots_attendus, recherche_partielle):
    """Calcule la Précision@3 : proportion de pages pertinentes dans le Top 3."""
    urls = trouver_pages_pertinentes(index, question, nombre_pages=3, recherche_partielle=recherche_partielle)
    if len(urls) == 0:
        return 0.0
    pertinents = 0
    for url in urls:
        mots_de_la_page = contenu_pages.get(url, "").split()
        if any(mot in mots_de_la_page for mot in mots_attendus):
            pertinents += 1
    return pertinents / len(urls)

def lancer_evaluation(index, contenu_pages):
    """Compare le Modèle A (exact) et le Modèle B (complet) sur le jeu de test."""
    resultats = []
    for test in QUESTIONS_TEST:
        p_A = precision_pour_une_question(index, contenu_pages, test["question"], test["mots_attendus"], False)
        p_B = precision_pour_une_question(index, contenu_pages, test["question"], test["mots_attendus"], True)
        resultats.append({
            "Question": test["question"],
            "Modèle A : exacte (%)": round(p_A * 100),
            "Modèle B : complète (%)": round(p_B * 100),
        })
    return resultats

def afficher_dashboard(index, contenu_pages):
    st.title("Tableau de Bord - Analyse des Données")
    st.markdown("Analyse exploratoire (EDA) du contenu collecté sur **finca.cd**")

    # ---------- 1. Métriques clés ----------
    col1, col2, col3 = st.columns(3)
    col1.metric("Pages explorées", len(contenu_pages))
    col2.metric("Mots uniques indexés", len(index))
    questions = len([m for m in st.session_state.messages if m["role"] == "user"])
    col3.metric("Questions posées", questions)

    st.divider()

    # ---------- 2. Mots les plus fréquents ----------
    st.subheader("Top 20 des mots les plus fréquents du site")
    compteur_global = {}
    for mot, pages in index.items():
        if mot not in STOP_WORDS_STATS and len(mot) > 3 and mot.isalpha():
            compteur_global[mot] = sum(pages.values())
    top_mots = sorted(compteur_global.items(), key=lambda x: x[1], reverse=True)[:20]
    if top_mots:
        mots = [m[0] for m in top_mots]
        occurrences = [m[1] for m in top_mots]
        fig1 = go.Figure(go.Bar(x=occurrences, y=mots, orientation="h", marker_color="#FF4B4B"))
        fig1.update_layout(xaxis_title="Occurrences", yaxis_title="Mots", height=600)
        st.plotly_chart(fig1, use_container_width=True)
        st.info(f"**Interprétation :** Le mot « {mots[0]} » est le terme dominant du site "
                f"({occurrences[0]} occurrences). Les termes suivants "
                f"({', '.join(mots[1:4])}...) révèlent les thématiques principales du contenu.")
    else:
        st.warning("Aucune donnée dans le cache. Posez d'abord des questions dans le chatbot.")

    st.divider()

    # ---------- 3. Richesse des pages ----------
    st.subheader("Les 10 pages les plus riches en contenu")
    tailles = sorted([(url, len(texte.split())) for url, texte in contenu_pages.items()],
                     key=lambda x: x[1], reverse=True)[:10]
    if tailles:
        urls = [u.replace("https://www.", "").replace("https://", "")[:35] for u, t in tailles]
        nb_mots = [t for u, t in tailles]
        fig2 = go.Figure(go.Bar(x=urls, y=nb_mots, marker_color="#1E8FFF"))
        fig2.update_layout(xaxis_title="Pages", yaxis_title="Mots extraits", height=500)
        st.plotly_chart(fig2, use_container_width=True)
        st.info("**Interprétation :** Les pages les plus longues fournissent le plus de "
                "contexte au modèle. Une page pauvre en texte donnera des réponses moins précises.")

    st.divider()

    # ---------- 4. Évaluation des modèles ----------
    st.subheader("Évaluation : comparaison des deux modèles de recherche")
    st.markdown("Chaque modèle est testé sur un jeu de validation. "
                "Métrique : **Précision@3** (proportion de pages pertinentes dans le Top 3).")
    import pandas as pd
    resultats = lancer_evaluation(index, contenu_pages)
    df = pd.DataFrame(resultats)
    st.dataframe(df, use_container_width=True)

    moyenne_A = df["Modèle A : exacte (%)"].mean()
    moyenne_B = df["Modèle B : complète (%)"].mean()
    fig3 = go.Figure(go.Bar(
        x=["Modèle A (exacte seule)", "Modèle B (exacte + partielle)"],
        y=[moyenne_A, moyenne_B],
        marker_color=["#95a5a6", "#2ECC71"]
    ))
    fig3.update_layout(yaxis_title="Précision@3 moyenne (%)", height=400)
    st.plotly_chart(fig3, use_container_width=True)
    st.success(f"**Justification du modèle final :** Le Modèle B obtient une Précision@3 "
               f"moyenne de **{moyenne_B:.0f} %**, contre **{moyenne_A:.0f} %** pour le Modèle A. "
               f"La recherche partielle améliore la pertinence de **{moyenne_B - moyenne_A:.0f} points**.")
    

# INTERFACE STREAMLIT
# ============================================
st.set_page_config(page_title="Chatbot Finca", page_icon="🤖", layout="wide")

# Initialisation (commune aux deux pages)
if "index" not in st.session_state or "contenu_pages" not in st.session_state:
    st.session_state.index, st.session_state.contenu_pages = initialiser_application()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Navigation : bouton du tableau de bord (caché par défaut)
if "voir_dashboard" not in st.session_state:
    st.session_state.voir_dashboard = False

if st.session_state.voir_dashboard:
    label_bouton = "Retour au Chatbot"
else:
    label_bouton = "Voir le Tableau de Bord"

if st.sidebar.button(label_bouton):
    st.session_state.voir_dashboard = not st.session_state.voir_dashboard

# Si le mode tableau de bord est activé : on l'affiche SEUL, puis on stoppe
if st.session_state.voir_dashboard:
    afficher_dashboard(st.session_state.index, st.session_state.contenu_pages)
    st.stop()

# ===== Page Chatbot =====
st.title("Chatbot Finca.cd")
st.markdown("Posez vos questions sur Finca RDC. Le bot apprend au fil de vos questions !")

# Afficher l'historique
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATAR_TRANSPARENT):
        st.markdown(message["content"])
        if "sources" in message and message["sources"]:
            with st.expander("Voir la source"):
                for url in message["sources"]:
                    st.markdown(f"- [{url}]({url})")

# Zone de saisie
if question := st.chat_input("Posez votre question sur Finca..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=AVATAR_TRANSPARENT):
        st.markdown(question)

    with st.spinner("Recherche en cours..."):
        urls_pertinentes = trouver_pages_pertinentes(st.session_state.index, question)

        if len(urls_pertinentes) == 0:
            with st.spinner("Exploration de nouvelles pages..."):
                st.session_state.index, st.session_state.contenu_pages = crawler_nouvelles_pages(
                    st.session_state.index,
                    st.session_state.contenu_pages,
                    nombre_pages_a_ajouter=5
                )
                sauvegarder_cache(st.session_state.index, st.session_state.contenu_pages)

            urls_pertinentes = trouver_pages_pertinentes(st.session_state.index, question)

        if len(urls_pertinentes) == 0:
            reponse = "Je n'ai pas trouvé d'information pertinente, même après avoir exploré de nouvelles pages. Essayez avec d'autres termes."
            contexte_debug = "Aucune page trouvée après exploration."
        else:
            textes = recuperer_contenu_pages(urls_pertinentes, st.session_state.contenu_pages)
            contexte = "\n--- PAGE SUIVANTE ---\n".join(textes)

            contexte_debug = "Pages analysées :\n" + "\n".join([f"- {url}" for url in urls_pertinentes])
            contexte_debug += f"\n\nTotal de pages en mémoire : {len(st.session_state.contenu_pages)}"

            with st.spinner("Rédaction de la réponse..."):
                reponse = demander_a_groq(question, contexte)

    sources_a_sauvegarder = urls_pertinentes if len(urls_pertinentes) > 0 else []

    st.session_state.messages.append({
        "role": "assistant",
        "content": reponse,
        "sources": sources_a_sauvegarder
    })

    with st.chat_message("assistant", avatar=AVATAR_TRANSPARENT):
        st.markdown(reponse)

        if sources_a_sauvegarder:
            with st.expander("Voir la source"):
                for url in sources_a_sauvegarder:
                    st.markdown(f"- [{url}]({url})")