"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Debug: print raw structure of first rencontre.
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

    rencontres = []
    try:
        result = client.search_rencontres(CLUB_SEARCH)
        hits = result.hits or []
        print(f"Rencontres found: {len(hits)}")
        for i, h in enumerate(hits):
            d = obj_to_dict(h)
            if i == 0:
                print(f"RAW FIRST: {json.dumps(d, default=str)[:1200]}")
            rencontres.append(d)
    except Exception as e:
        print(f"Warning: {e}")

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club_nom": "ENT. ARTHES ST JUERY BB",
            "club_id": "12493",
            "source": "ffbb-api-client-v2",
        },
        "rencontres": rencontres,
        "prochain_match": None,
        "dernier_resultat": None,
        "lives": [],
        "stats": {"total": len(rencontres), "joues": 0, "a_venir": 0},
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written {len(rencontres)} rencontres.")
    print("Done.")


if __name__ == "__main__":
    main()
