"""
fetch_ffbb.py - Fetch EASJB data from FFBB API
Generates public/data.json for the static website.
Club: ENT. ARTHES ST JUERY BB (id=12493)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "data.json"
CLUB_ID = "12493"
CLUB_SEARCH = "arth"
CLUB_SEARCH_RENCONTRES = "arth"


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


def is_easjb(name):
    if not name:
        return False
    n = str(name).lower()
    return any(k in n for k in ["arth", "juery", "easjb", "12493"])


def get_str(d, *keys):
    for key in keys:
        val = d.get(key)
        if val is not None:
            if isinstance(val, dict):
                return str(val.get("nom") or val.get("name") or val.get("libelle") or "")
            return str(val)
    return ""


def serialize_rencontre(d):
    # equipe_dom / equipe_ext can be dicts with "nom" key
    dom = d.get("equipe_dom") or {}
    ext = d.get("equipe_ext") or {}
    if isinstance(dom, dict):
        dom_nom = dom.get("nom") or dom.get("name") or ""
    else:
        dom_nom = str(dom)
    if isinstance(ext, dict):
        ext_nom = ext.get("nom") or ext.get("name") or ""
    else:
        ext_nom = str(ext)

    # competition
    comp = d.get("competition_id") or d.get("competition") or {}
    if isinstance(comp, dict):
        comp_nom = (comp.get("competition_origine_nom")
                    or comp.get("nom")
                    or comp.get("code")
                    or "")
        if not comp_nom:
            orig = comp.get("competition_origine") or {}
            comp_nom = orig.get("nom") or comp.get("code") or ""
    else:
        comp_nom = str(comp)

    # date
    date_val = (d.get("date_reception")
                or d.get("date_rencontre")
                or d.get("date")
                or "")

    # salle
    salle = d.get("salle") or {}
    if isinstance(salle, dict):
        salle_nom = salle.get("nom") or salle.get("name") or ""
    else:
        salle_nom = str(salle)

    # scores
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

    # Find club
    club_nom = "ENT. ARTHES ST JUERY BB"
    club_id = CLUB_ID
    try:
        result = client.search_organismes(CLUB_SEARCH)
        hits = result.hits or []
        for h in hits:
            d = obj_to_dict(h)
            cid = str(d.get("id") or d.get("cartographie", {}).get("cartographie_id", "").replace("G-", "") or "")
            nom = str(d.get("nom") or "")
            if "arth" in nom.lower() and "juery" in nom.lower().replace("juery","juery"):
                club_nom = nom
                club_id = cid
                break
            if cid == CLUB_ID:
                club_nom = nom
                club_id = cid
                break
        print(f"Club: {club_nom} (id={club_id})")
    except Exception as e:
        print(f"Warning club search: {e}")

    # Fetch rencontres
    rencontres = []
    try:
        result = client.search_rencontres(CLUB_SEARCH_RENCONTRES)
        hits = result.hits or []
        print(f"Rencontres found: {len(hits)}")
        for h in hits:
            try:
                d = obj_to_dict(h)
                r = serialize_rencontre(d)
                # Only keep matches involving EASJB
                print(f"  Match: {r['equipe_dom']} vs {r['equipe_ext']}")
                rencontres.append(r)
                    rencontres.append(r)
            except Exception as e:
                print(f"Skip rencontre: {e}")
        print(f"EASJB rencontres: {len(rencontres)}")
    except Exception as e:
        print(f"Warning rencontres: {e}")

    rencontres.sort(key=lambda x: x.get("date") or "")
    played   = [r for r in rencontres if r.get("score_dom") is not None]
    upcoming = [r for r in rencontres if r.get("score_dom") is None]

    # Lives
    lives = []
    try:
        result = client.get_lives()
        lives_hits = result.hits if hasattr(result, "hits") else (result or [])
        if isinstance(lives_hits, list):
            for lv in lives_hits:
                d = obj_to_dict(lv)
                nom = str(d.get("nom") or "")
                if is_easjb(nom):
                    lives.append({
                        "id":   str(d.get("id") or ""),
                        "nom":  nom,
                        "lien": str(d.get("lien") or d.get("url") or ""),
                    })
        print(f"Lives: {len(lives)}")
    except Exception as e:
        print(f"Warning lives: {e}")

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
        "lives": lives,
        "stats": {
            "total":   len(rencontres),
            "joues":   len(played),
            "a_venir": len(upcoming),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Written {len(rencontres)} rencontres to {OUTPUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
