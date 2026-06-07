"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Debug: print all match names to find correct filter.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"
CLUB_SEARCH = "arth"


def obj_to_dict(obj, depth=0):
    if depth > 4:
        return str(obj)
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [obj_to_dict(i, depth+1) for i in obj]
    if isinstance(obj, dict):
        return {k: obj_to_dict(v, depth+1) for k, v in obj.items()}
    result = {}
    for attr in dir(obj):
        if attr.startswith('_'):
            continue
        try:
            val = getattr(obj, attr)
            if callable(val):
                continue
            result[attr] = obj_to_dict(val, depth+1)
        except Exception:
            pass
    return result


def get_nom(val):
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("nom") or val.get("name") or val.get("libelle") or "")
    return str(val)


def serialize_rencontre(d):
    dom_nom = get_nom(d.get("equipe_dom"))
    ext_nom = get_nom(d.get("equipe_ext"))
    comp = d.get("competition_id") or d.get("competition") or {}
    if isinstance(comp, dict):
        orig = comp.get("competition_origine") or {}
        comp_nom = (comp.get("competition_origine_nom")
                    or orig.get("nom")
                    or comp.get("nom")
                    or comp.get("code") or "")
    else:
        comp_nom = str(comp)
    date_val = (d.get("date_reception") or d.get("date_rencontre") or d.get("date") or "")
    salle_nom = get_nom(d.get("salle"))
    score_dom = d.get("score_equipe_dom") or d.get("score_dom")
    score_ext = d.get("score_equipe_ext") or d.get("score_ext")
    return {
        "id":          str(d.get("id") or ""),
        "date":        str(date_val),
        "competition": str(comp_nom),
        "equipe_dom":  str(dom_nom),
        "equipe_ext":  str(ext_nom),
        "score_dom":   score_dom,
        "score_ext":   score_ext,
        "salle":       str(salle_nom),
        "statut":      str(d.get("statut") or ""),
    }


def main():
    print("Starting EASJB FFBB fetch...")

    try:
        from ffbb_api_client_v2 import FFBBAPIClientV2, TokenManager
    except ImportError:
        print("ffbb-api-client-v2 not installed.")
        sys.exit(1)

    print("Resolving tokens...")
    try:
        tokens = TokenManager.get_tokens()
        client = FFBBAPIClientV2.create(
            meilisearch_bearer_token=tokens.meilisearch_token,
            api_bearer_token=tokens.api_token,
        )
        print("Client ready.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    club_nom = "ENT. ARTHES ST JUERY BB"
    club_id = "12493"

    # Fetch rencontres - include ALL, print names for debugging
    rencontres = []
    try:
        result = client.search_rencontres(CLUB_SEARCH)
        hits = result.hits or []
        print(f"Rencontres found: {len(hits)}")
        for h in hits:
            try:
                d = obj_to_dict(h)
                r = serialize_rencontre(d)
                print(f"  Match: [{r['equipe_dom']}] vs [{r['equipe_ext']}] - {r['competition']}")
                rencontres.append(r)
            except Exception as e:
                print(f"  Skip: {e}")
    except Exception as e:
        print(f"Warning rencontres: {e}")

    rencontres.sort(key=lambda x: x.get("date") or "")
    played = [r for r in rencontres if r.get("score_dom") is not None]
    upcoming = [r for r in rencontres if r.get("score_dom") is None]

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club_nom": club_nom,
            "club_id": club_id,
            "source": "ffbb-api-client-v2",
        },
        "rencontres": rencontres,
        "prochain_match": upcoming[0] if upcoming else None,
        "dernier_resultat": played[-1] if played else None,
        "lives": [],
        "stats": {
            "total":   len(rencontres),
            "joues":   len(played),
            "a_venir": len(upcoming),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written {len(rencontres)} rencontres.")
    print("Done.")


if __name__ == "__main__":
    main()
