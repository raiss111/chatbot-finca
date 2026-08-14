from bs4 import BeautifulSoup
import re
def parse_html(html,stop_words):
    soup = BeautifulSoup(html,"html.parser")
    texte=soup.get_text()
    texte=texte.lower()
    texte= re.sub(r"[^a-z0-9 ]","  ",texte)
    mots=texte.split() 
    mots_utiles = []
    for mot in mots:
        if mot not in stop_words:
            mots_utiles.append(mot) 
            
    return mots_utiles


    
    
    