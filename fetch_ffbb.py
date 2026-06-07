"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Final version - correct field names from API inspection.
Club: ENT. ARTHES ST JUERY BB (id=12493)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"
CLUB_ID = "12493"
SEARCH_TERMS = ["arthes", "arth", "saint juery", "juery"]


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


def is_easjb_organisme(d):
    """Check if either team's organisme id matches EASJB."""
    org1 = d.get("id_organisme_equipe1") or {}
    org2 = d.get("id_organisme_equipe2") or {}
    if isinstance(org1, dict) and str(org1.get("id", "")) == CLUB_ID:
        return True
    if isinstance(org2, dict) and str(org2.get("id", "")) == CLUB_ID:
        return True
    # Also check by name in lower fields
    lower1 = str(d.get("lower_nom_equipe1") or "")
    lower2 = str(d.get("lower_nom_equipe2") or "")
    for s in ["arth", "juery", "easjb"]:
        if s in lower1 or s in lower2:
            return True
    return False


def fmt_date(d):
    """Build ISO date string from date object dict."""
    if not isinstance(d, dict):
        return ""
    try:
        year  = d.get("year", 2026)
        month = d.get("month", 1)
        day   = d.get("day", 1)
        hour  = d.get("hour", 0)
        minute = d.get("minute", 0)
        return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"
    except Exception:
        return ""


def serialize(d):
    nom1 = str(d.get("nom_equipe1") or "")
    nom2 = str(d.get("nom_equipe2") or "")

    comp = d.get("competition_id") or {}
    if isinstance(comp, dict):
        comp_nom = str(comp.get("competition_origine_nom") or comp.get("nom") or "")
    else:
        comp_nom = ""

    date_iso = fmt_date(d.get("date_rencontre") or d.get("date"))

    salle = d.get("salle") or {}
    salle_nom = str(salle.get("libelle") or "") if isinstance(salle, dict) else ""

    score1 = d.get("resultat_equipe1")
    score2 = d.get("resultat_equipe2")
    joue   = d.get("joue", False)

    # Determine which team is EASJB
    org1 = d.get("id_organisme_equipe1") or {}
    is_home = isinstance(org1, dict) and str(org1.get("id", "")) == CLUB_ID

    return {
        "id":          str(d.get("id") or ""),
        "date":        date_iso,
        "competition": comp_nom,
        "equipe_dom":  nom1,
        "equipe_ext":  nom2,
        "score_dom":   int(score1) if joue and score1 is not None else None,
        "score_ext":   int(score2) if joue and score2 is not None else None,
        "salle":       salle_nom,
        "joue":        joue,
        "is_home":     is_home,
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

    # Collect all rencontres across search terms, deduplicate by id
    seen = set()
    rencontres = []

    for term in SEARCH_TERMS:
        try:
            result = client.search_rencontres(term)
            hits = result.hits or []
            print(f"'{term}' -> {len(hits)} hits")
            for h in hits:
                d = obj_to_dict(h)
                rid = str(d.get("id") or "")
                if rid in seen:
                    continue
                seen.add(rid)
                if is_easjb_organisme(d):
                    r = serialize(d)
                    print(f"  EASJB match: {r['equipe_dom']} vs {r['equipe_ext']} | {r['competition']} | {r['date']} | score: {r['score_dom']}-{r['score_ext']}")
                    rencontres.append(r)
        except Exception as e:
            print(f"Warning '{term}': {e}")

    rencontres.sort(key=lambda x: x.get("date") or "")
    played   = [r for r in rencontres if r.get("joue")]
    upcoming = [r for r in rencontres if not r.get("joue")]

    print(f"Total EASJB matches: {len(rencontres)} ({len(played)} played, {len(upcoming)} upcoming)")

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "club_nom": "ENT. ARTHES ST JUERY BB",
            "club_id": CLUB_ID,
            "source": "ffbb-api-client-v2",
        },
        "rencontres":       rencontres,
        "prochain_match":   upcoming[0] if upcoming else None,
        "dernier_resultat": played[-1]  if played   else None,
        "lives":            [],
        "stats": {
            "total":   len(rencontres),
            "joues":   len(played),
            "a_venir": len(upcoming),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written to {OUTPUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
