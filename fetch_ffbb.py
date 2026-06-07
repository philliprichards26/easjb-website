"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Generates public/data.json for the static website.
Club: Entente Arthes Saint-Juery Basket
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"
CLUB_SEARCH = "arthes saint juery"

try:
    from ffbb_api_client_v2 import FFBBAPIClientV2, TokenManager
except ImportError:
    print("ffbb-api-client-v2 not installed.")
    sys.exit(1)


def safe_get(obj, *keys, default=None):
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
    return obj if obj is not None else default


def to_str(val):
    if val is None:
        return ""
    if isinstance(obj, dict):
        return str(val.get("nom", val.get("id", "")))
    return str(val)


def is_easjb(name):
    if not name:
        return False
    n = str(name).lower()
    return any(k in n for k in ["arth", "juery", "easjb"])


def serialize_match(r):
    return {
        "id":          safe_get(r, "id", default=""),
        "date":        safe_get(r, "date_reception", default=safe_get(r, "date", default="")),
        "competition": safe_get(r, "competition", "nom", default=safe_get(r, "competition", default="")),
        "equipe_dom":  safe_get(r, "equipe_dom", "nom", default=safe_get(r, "equipe_dom", default="")),
        "equipe_ext":  safe_get(r, "equipe_ext", "nom", default=safe_get(r, "equipe_ext", default="")),
        "score_dom":   safe_get(r, "score_dom", default=None),
        "score_ext":   safe_get(r, "score_ext", default=None),
        "salle":       safe_get(r, "salle", "nom", default=safe_get(r, "salle", default="")),
        "statut":      safe_get(r, "statut", default=""),
    }


def main():
    print("Starting EASJB FFBB fetch...")

    print("Resolving FFBB tokens...")
    try:
        tokens = TokenManager.get_tokens()
        client = FFBBAPIClientV2.create(
            meilisearch_bearer_token=tokens.meilisearch_token,
            api_bearer_token=tokens.api_token,
        )
        print("Client ready.")
    except Exception as e:
        print(f"Error creating client: {e}")
        sys.exit(1)

    print(f"Searching club: {CLUB_SEARCH}")
    try:
        organismes = client.search_organismes(CLUB_SEARCH) or []
    except Exception as e:
        print(f"Error searching organismes: {e}")
        sys.exit(1)

    club = None
    for org in organismes:
        nom = str(safe_get(org, "nom", default="")).lower()
        if "arth" in nom and "juery" in nom:
            club = org
            break
    if club is None and organismes:
        club = organismes[0]

    club_nom = safe_get(club, "nom", default="EASJB") if club else "EASJB"
    club_id  = str(safe_get(club, "id", default="")) if club else ""
    print(f"Club: {club_nom} (id={club_id})")

    print("Fetching matches...")
    rencontres_raw = []
    try:
        rencontres_raw = client.search_rencontres(CLUB_SEARCH) or []
        print(f"Found {len(rencontres_raw)} matches.")
    except Exception as e:
        print(f"Warning - matches error: {e}")

    rencontres = []
    for r in rencontres_raw:
        try:
            rencontres.append(serialize_match(r))
        except Exception:
            pass

    rencontres.sort(key=lambda x: x.get("date") or "")

    played   = [r for r in rencontres if r.get("score_dom") is not None]
    upcoming = [r for r in rencontres if r.get("score_dom") is None]

    lives = []
    try:
        lives_raw = client.get_lives() or []
        for lv in lives_raw:
            nom = str(safe_get(lv, "nom", default="")).lower()
            if is_easjb(nom):
                lives.append({
                    "id":   safe_get(lv, "id", default=""),
                    "nom":  safe_get(lv, "nom", default=""),
                    "lien": safe_get(lv, "lien", default=""),
                })
        print(f"Lives: {len(lives)}")
    except Exception as e:
        print(f"Warning - lives error: {e}")

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club_nom":     club_nom,
            "club_id":      club_id,
            "source":       "ffbb-api-client-v2",
        },
        "rencontres":       rencontres,
        "prochain_match":   upcoming[0] if upcoming else None,
        "dernier_resultat": played[-1]  if played   else None,
        "lives":            lives,
        "stats": {
            "total":   len(rencontres),
            "joues":   len(played),
            "a_venir": len(upcoming),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written: {OUTPUT_PATH}")
    print(f"Done - {len(rencontres)} matches, {len(lives)} lives.")


if __name__ == "__main__":
    main()
