"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Debug version - dumps raw API response structure
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"
CLUB_SEARCH = "arthes saint juery"


def obj_to_dict(obj, depth=0):
    """Recursively convert any object to a JSON-serializable dict."""
    if depth > 5:
        return str(obj)
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [obj_to_dict(i, depth+1) for i in obj]
    if isinstance(obj, dict):
        return {k: obj_to_dict(v, depth+1) for k, v in obj.items()}
    # It's a custom object - get all its attributes
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


def extract_list(obj):
    """Try every possible way to get a list from a result object."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    for attr in ["hits", "results", "items", "data", "organismes",
                 "rencontres", "competitions", "lives", "value"]:
        val = getattr(obj, attr, None)
        if val is not None:
            if isinstance(val, list):
                return val
            inner = getattr(val, "hits", None)
            if inner and isinstance(inner, list):
                return inner
    try:
        return list(obj)
    except Exception:
        return []


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

    # --- Search organismes and dump raw structure ---
    print(f"Searching: {CLUB_SEARCH}")
    try:
        result = client.search_organismes(CLUB_SEARCH)
        print(f"Result type: {type(result)}")
        print(f"Result attrs: {[a for a in dir(result) if not a.startswith('_')]}")

        hits = extract_list(result)
        print(f"Hits count: {len(hits)}")

        if hits:
            first = hits[0]
            print(f"First hit type: {type(first)}")
            print(f"First hit attrs: {[a for a in dir(first) if not a.startswith('_')]}")
            first_dict = obj_to_dict(first)
            print(f"First hit data: {json.dumps(first_dict, default=str)[:500]}")
    except Exception as e:
        print(f"Error organismes: {e}")
        hits = []

    # --- Search rencontres and dump raw structure ---
    print("Fetching rencontres...")
    rencontres_raw = []
    try:
        result2 = client.search_rencontres(CLUB_SEARCH)
        print(f"Rencontres result type: {type(result2)}")
        print(f"Rencontres result attrs: {[a for a in dir(result2) if not a.startswith('_')]}")

        rencontres_raw = extract_list(result2)
        print(f"Rencontres count: {len(rencontres_raw)}")

        if rencontres_raw:
            first_r = rencontres_raw[0]
            print(f"First rencontre type: {type(first_r)}")
            first_r_dict = obj_to_dict(first_r)
            print(f"First rencontre data: {json.dumps(first_r_dict, default=str)[:1000]}")
    except Exception as e:
        print(f"Error rencontres: {e}")

    # --- Build output with raw data for inspection ---
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
        club_id  = str(d.get("id") or d.get("_id") or d.get("code") or "")

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

    print(f"Written {len(rencontres_out)} rencontres to {OUTPUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
