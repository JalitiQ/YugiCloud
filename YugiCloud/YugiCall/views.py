from django.shortcuts import render

# Create your views here.

# views.py
import requests
from django.http import JsonResponse
from django.views import View

API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

class CardSearchFRView(View):
    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        field = (request.GET.get("field") or "name_contains").strip()

        if not q:
            return JsonResponse({"error": "Paramètre 'q' manquant"}, status=400)

        # Paramètres de base : FR + (tu peux ajouter 'misc': 'yes', 'sort': 'name', etc.)
        params = {"language": "fr"}

        # --- Mapping du select vers les bons paramètres YGOPRODeck ---
        # Nom (contient) -> 'fname'
        if field == "name_contains":
            params["fname"] = q

        # Nom (exact) -> 'name'
        elif field == "name_exact":
            params["name"] = q

        # Extension (set) -> 'cardset' (ex: "Legend of Blue Eyes White Dragon" ou code set)
        elif field == "set":
            params["cardset"] = q

        # Archétype -> 'archetype'
        elif field == "archetype":
            params["archetype"] = q

        # Type (ex: "Monstre à Effet", "Magie", "Piège", "XYZ Monster"… selon localisations)
        elif field == "type":
            params["type"] = q

        # Attribut (ex: "FEU", "EAU", "LUMIÈRE", souvent "FIRE", "WATER", "LIGHT" selon data)
        elif field == "attribute":
            params["attribute"] = q

        # Race (ex: "Dragon", "Guerrier", "Spellcaster", …)
        elif field == "race":
            params["race"] = q

        # Numériques : YGOPRODeck accepte les comparateurs sous forme préfixée (lte/gte/lt/gt/eq)
        elif field == "level_eq":
            params["level"] = f"eq{q}"
        elif field == "level_gte":
            params["level"] = f"gte{q}"
        elif field == "level_lte":
            params["level"] = f"lte{q}"
        elif field == "atk_gte":
            params["atk"] = f"gte{q}"
        elif field == "def_lte":
            params["def"] = f"lte{q}"

        else:
            return JsonResponse({"error": f"Filtre inconnu: {field}"}, status=400)

        # --- Appel API ---
        try:
            r = requests.get(API_URL, params=params, timeout=10)
            r.raise_for_status()
        except requests.HTTPError as e:
            return JsonResponse(
                {"error": "Erreur HTTP YGOPRODeck", "details": str(e), "api_body": getattr(r, "text", None)},
                status=r.status_code if "r" in locals() else 502,
            )
        except requests.RequestException as e:
            return JsonResponse({"error": "Erreur réseau", "details": str(e)}, status=502)

        return JsonResponse(r.json(), status=200)
