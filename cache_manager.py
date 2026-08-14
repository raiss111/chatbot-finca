import json
import os
from datetime import datetime


# Nom du fichier de cache
FICHIER_CACHE = "cache_finca.json"


def sauvegarder_cache(index, contenu_pages):
    
    # On crée un dictionnaire qui contient tout
    donnees = {
        "date_creation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nombre_pages": len(contenu_pages),
        "index": index,
        "contenu_pages": contenu_pages
    }
    
    # On écrit dans le fichier JSON
    with open(FICHIER_CACHE, "w", encoding="utf-8") as fichier:
        json.dump(donnees, fichier, ensure_ascii=False, indent=2)
    
    print(f"Cache sauvegardé dans {FICHIER_CACHE}")
    print(f"   → {len(contenu_pages)} pages mises en cache")


def charger_cache():
    # Vérifier si le fichier existe
    if not os.path.exists(FICHIER_CACHE):
        print(f"Aucun cache trouvé ({FICHIER_CACHE} n'existe pas)")
        return None, None
    
    try:
        # Lire le fichier JSON
        with open(FICHIER_CACHE, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)
        
        print(f"Cache chargé depuis {FICHIER_CACHE}")
        print(f"   Créé le : {donnees['date_creation']}")
        print(f"   {donnees['nombre_pages']} pages en cache")
        
        # Retourner les données
        return donnees["index"], donnees["contenu_pages"]
    
    except Exception as e:
        print(f"Erreur lors du chargement du cache : {e}")
        return None, None


def cache_est_frais(max_heures=24):
    """
    Vérifie si le cache est encore "frais" (pas trop vieux).
    
    Argument :
        max_heures : nombre d'heures maximum avant de considérer le cache comme périmé
    
    Retourne :
        True si le cache est frais, False sinon
    """
    if not os.path.exists(FICHIER_CACHE):
        return False
    
    try:
        with open(FICHIER_CACHE, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)
        
        date_str = donnees["date_creation"]
        date_cache = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        date_actuelle = datetime.now()
        
        # Calculer la différence en heures
        difference = date_actuelle - date_cache
        heures = difference.total_seconds() / 3600
        
        if heures < max_heures:
            print(f"Cache frais (créé il y a {heures:.1f} heures)")
            return True
        else:
            print(f"Cache périmé (créé il y a {heures:.1f} heures, max = {max_heures}h)")
            return False
    
    except:
        return False


def supprimer_cache():
    """Supprime le fichier de cache (pour forcer un rafraîchissement)."""
    if os.path.exists(FICHIER_CACHE):
        os.remove(FICHIER_CACHE)
        print(f"Cache supprimé : {FICHIER_CACHE}")
    else:
        print("Aucun cache à supprimer")