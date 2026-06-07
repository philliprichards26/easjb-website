"""
fetch_ffbb.py  Rcupre les donnes EASJB depuis l'API FFBB
et gnre public/data.json pour le site statique.

Utilise ffbb-api-client-v2 (TokenManager auto-rsout les tokens FFBB).
Club : Entente Arths Saint-Jury Basket  code organisme 081081
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Import du client FFBB
# ---------------------------------------------------------------------------
try:
from ffbb_api_client_v2 import FFBBAPIClientV2
from ffbb_api_client_v2 import TokenManager
except ImportError:
    print("  ffbb-api-client-v2 non install. Lance : pip install ffbb-api-client-v2")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Constantes EASJB
# ---------------------------------------------------------------------------
CLUB_NOM        = "Entente Arths Saint-Jury Basket"
CLUB_SEARCH     = "arthes saint juery"   # terme de recherche
OUTPUT_PATH     = Path(__file__).parent / "public" / "data.json"

# ---------------------------------------------------------------------------
# 3. Helpers
# ---------------------------------------------------------------------------

def safe_get(obj, *keys, default=None):
    """Accs scuris dans des objets ou dicts imbriqus."""
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
    return obj if obj is not None else default


def serialize_rencontre(r):
    """Convertit une rencontre API en dict JSON-friendly."""
    return {
        "id":            safe_get(r, "id", default=""),
        "date":          safe_get(r, "date_reception", default=safe_get(r, "date", default="")),
        "competition":   safe_get(r, "competition", "nom", default=safe_get(r, "competition", default="")),
        "equipe_dom":    safe_get(r, "equipe_dom", "nom", default=safe_get(r, "equipe_dom", default="")),
        "equipe_ext":    safe_get(r, "equipe_ext", "nom", default=safe_get(r, "equipe_ext", default="")),
        "score_dom":     safe_get(r, "score_dom", default=None),
        "score_ext":     safe_get(r, "score_ext", default=None),
        "salle":         safe_get(r, "salle", "nom", default=safe_get(r, "salle", default="")),
        "statut":        safe_get(r, "statut", default=""),
        "is_home":       True,   # will be refined below
    }


def to_str(val):
    """Assure que la valeur est une chane pour les comparaisons."""
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("nom", val.get("id", "")))
    return str(val)

# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------

def main():
    print(" Dmarrage fetch_ffbb.py pour EASJB")

    #  Tokens auto-rsolus depuis l'endpoint public FFBB 
    print(" Rsolution des tokens FFBB...")
    try:
        tokens = TokenManager.get_tokens()
        client = FFBBAPIClientV2.create(
            meilisearch_bearer_token=tokens.meilisearch_token,
            api_bearer_token=tokens.api_token,
        )
        print(" Client FFBB initialis")
    except Exception as e:
        print(f" Erreur initialisation client : {e}")
        sys.exit(1)

    #  Recherche du club 
    print(f" Recherche organisme : {CLUB_SEARCH!r}")
    try:
        organismes = client.search_organismes(CLUB_SEARCH)
    except Exception as e:
        print(f" Erreur recherche organismes : {e}")
        sys.exit(1)

    if not organismes:
        print("  Aucun organisme trouv  vrifier le terme de recherche")
        sys.exit(1)

    # Slection du bon club (recherche insensible  la casse)
    club = None
    for org in organismes:
        nom = to_str(safe_get(org, "nom", default="")).lower()
        if "arth" in nom and ("juery" in nom or "jury" in nom):
            club = org
            break

    if club is None:
        # Fallback : premier rsultat
        club = organismes[0]
        print(f"  Club exact non trouv, utilisation du 1er rsultat : {safe_get(club, 'nom')}")
    else:
        print(f" Club trouv : {safe_get(club, 'nom')}")

    club_id = safe_get(club, "id", default=safe_get(club, "_id"))
    club_nom = safe_get(club, "nom", default=CLUB_NOM)
    print(f"   ID club : {club_id}")

    #  Rcupration des rencontres 
    print(" Rcupration des rencontres...")
    rencontres_brutes = []
    try:
        # Recherche par nom de club
        rencontres_brutes = client.search_rencontres(CLUB_SEARCH) or []
        print(f"   {len(rencontres_brutes)} rencontre(s) trouve(s)")
    except Exception as e:
        print(f"  Erreur rencontres : {e}")

    #  Tri et enrichissement 
    rencontres = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for r in rencontres_brutes:
        try:
            d = serialize_rencontre(r)
            # Dtecter si domicile
            dom_str = to_str(d["equipe_dom"]).lower()
            d["is_home"] = any(k in dom_str for k in ["arth", "juery", "jury", "easjb"])
            rencontres.append(d)
        except Exception:
            pass  # On ignore les rencontres mal formes

    # Tri par date
    rencontres.sort(key=lambda x: x.get("date") or "", reverse=False)

    # Prochain match et dernier rsultat
    played   = [r for r in rencontres if r.get("score_dom") is not None]
    upcoming = [r for r in rencontres if r.get("score_dom") is None]

    #  Rcupration des lives ventuels 
    lives = []
    try:
        lives_raw = client.get_lives() or []
        for lv in lives_raw:
            nom = to_str(safe_get(lv, "nom", default="")).lower()
            if any(k in nom for k in ["arth", "juery", "jury", "easjb"]):
                lives.append({
                    "id":        safe_get(lv, "id", default=""),
                    "nom":       safe_get(lv, "nom", default=""),
                    "lien":      safe_get(lv, "lien", default=""),
                })
        print(f"   {len(lives)} live(s) EASJB en cours")
    except Exception as e:
        print(f"  Erreur lives : {e}")

    #  Construction du JSON final 
    data = {
        "meta": {
            "generated_at": now_iso,
            "club_nom":     club_nom,
            "club_id":      str(club_id) if club_id else "",
            "source":       "ffbb-api-client-v2 / FFBB",
        },
        "rencontres":      rencontres,
        "prochain_match":  upcoming[0] if upcoming else None,
        "dernier_resultat": played[-1] if played else None,
        "lives":           lives,
        "stats": {
            "total":    len(rencontres),
            "joues":    len(played),
            "a_venir":  len(upcoming),
        },
    }

    #  criture 
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f" data.json crit  {OUTPUT_PATH}")
    print(f"   {len(rencontres)} rencontres | {len(lives)} lives")
    print(" Termin.")


if __name__ == "__main__":
    main()
