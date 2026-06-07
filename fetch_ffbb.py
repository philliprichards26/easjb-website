"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Tests multiple search terms to find the club.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"

SEARCH_TERMS = [
    "arthes",
    "saint juery",
    "EASJB",
    "arth",
    "juery",
    "arthes basket",
]


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

    # Try each search term for organismes
    print("--- Testing organisme search terms ---")
    hits = []
    found_term = None
    for term in SEARCH_TERMS:
        try:
            result = client.search_organismes(term)
            h = result.hits if result.hits else []
            print(f"  '{term}' -> {len(h)} hits")
            if h and not hits:
                hits = h
                found_term = term
                first = obj_to_dict(h[0])
                print(f"  First hit: {json.dumps(first, default=str)[:300]}")
        except Exception as e:
            print(f"  '{term}' -> error: {e}")

    # Try each search term for rencontres
    print("--- Testing rencontres search terms ---")
    rencontres_raw = []
    for term in SEARCH_TERMS:
        try:
            result = client.search_rencontres(term)
            h = result.hits if result.hits else []
            print(f"  '{term}' -> {len(h)} hits")
            if h and not rencontres_raw:
                rencontres_raw = h
                first = obj_to_dict(h[0])
                print(f"  First rencontre: {json.dumps(first, default=str)[:500]}")
        except Exception as e:
            print(f"  '{term}' -> error: {e}")

    # Build output
    rencontres_out = []
    for r in rencontres_raw:
        try:
            rencontres_out.append(obj_to_dict(r))
        except Exception:
            pass

    club_nom = "EASJB"
    club_id = ""
    if hits:
        d = obj_to_dict(hits[0])
        club_nom = str(d.get("nom") or d.get("name") or "EASJB")
        club_id = str(d.get("id") or d.get("_id") or d.get("code") or "")
        print(f"Club found: {club_nom} (id={club_id})")

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club_nom": club_nom,
            "club_id": club_id,
            "source": "ffbb-api-client-v2",
        },
        "rencontres": rencontres_out,
        "prochain_match": None,
        "dernier_resultat": None,
        "lives": [],
        "stats": {
            "total": len(rencontres_out),
            "joues": 0,
            "a_venir": 0,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written {len(rencontres_out)} rencontres.")
    print("Done.")


if __name__ == "__main__":
    main()
