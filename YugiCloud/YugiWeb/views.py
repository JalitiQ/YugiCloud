from django.shortcuts import render
from YugiCall.models import Card, CardSet

# Create your views here.
def accueil(request):
    return render(request, "page/index.html")

# Import de 'render' pour retourner une page HTML à partir d’un template.
from django.shortcuts import render

# Import de Q (pratique si tu veux complexifier plus tard), ici on reste simple.
from django.db.models import Q

# Import du modèle principal à filtrer.
from YugiCall.models import Card  # ← adapte le chemin si nécessaire

from .views import Card


# Déclare les champs autorisés dans la liste déroulante :
# - tuple (fname, label, ftype)
#   - fname  : chemin ORM du champ (peut inclure des jointures via "__")
#   - label  : texte affiché dans <option>
#   - ftype  : "text" => on fera __icontains ; "number" => on comparera par égalité (=)
FIELDS_CONFIG = [
    ("name",      "Nom",       "text"),    # Card.name : champ texte
    ("archetype", "Archétype", "text"),    # Card.archetype : champ texte
    ("type",      "Type",      "text"),    # Card.type : champ texte
    ("attribute", "Attribut",  "text"),    # Card.attribute : champ texte
    ("race",      "Race",      "text"),    # Card.race : champ texte
    ("desc",     "Description", "text"),
    ("level",     "Niveau",    "number"),  # Card.level : champ entier
    ("atk",       "ATK",       "number"),  # Card.atk : champ entier
    ("def",       "DEF",       "number"),  # Card.def : champ entier
    # Exemple de FK/M2M : décommente si tu as une relation vers CardSet
    # ("cardset__name", "Extension (nom du set)", "text"),
]


def recherche_BDD(request):
    """
    Vue de recherche simple :
    - lit deux paramètres GET : 'q' (valeur) et 'field' (champ choisi)
    - applique UN SEUL filtre correspondant au champ choisi
    - rend 'page/search.html' avec la liste 'cards'
    """

    # Récupère la valeur saisie par l’utilisateur dans la querystring : ?q=...
    # - request.GET.get("q") : lit la dernière valeur pour la clé 'q'
    # - or "" : remplace None par chaîne vide si non fourni
    # - .strip() : retire espaces en début/fin (sécurité UX)
    q = (request.GET.get("q") or "").strip()

    # Récupère le champ sélectionné : ?field=...
    # - "name" par défaut pour avoir un comportement utile sans choix explicite
    field = (request.GET.get("field") or "name").strip()

    # Point de départ : toutes les cartes
    # - .order_by("name") : tri par nom pour un affichage stable
    cards = Card.objects.all().order_by("name")

    # Si l’utilisateur a saisi quelque chose, on tente d’appliquer le filtre
    if q:
        # Construis un index {fname: (label, ftype)} pour valider rapidement le champ
        config_by_field = {fname: (label, ftype) for fname, label, ftype in FIELDS_CONFIG}

        # Vérifie que le champ demandé existe dans la config
        if field in config_by_field:
            label, ftype = config_by_field[field]

            # Cas champ texte : on utilise le lookup __icontains (contient, insensible à la casse)
            if ftype == "text":
                # .filter(**{f"{field}__icontains": q})
                # - **{...} : passe un dict comme arguments nommés (clé = "champ__lookup")
                # - f"{field}__icontains" : ex. "name__icontains"
                # - q : la valeur saisie
                cards = cards.filter(**{f"{field}__icontains": q})

            # Cas champ numérique : on applique une égalité stricte, mais seulement si q est entier valide
            elif ftype == "number":
                # q.lstrip("-").isdigit() : True si "123" ou "-123" (évite ValueError à la conversion)
                if q.lstrip("-").isdigit():
                    cards = cards.filter(**{field: int(q)})  # ex. {"atk": 2500}
                else:
                    # Si l’utilisateur tape "dragon" sur un champ numérique, on choisit de renvoyer 0 résultat
                    cards = cards.none()
        else:
            # Champ inconnu (ex. modification côté front non prévue) → 0 résultat pour rester explicite
            cards = cards.none()

    # .distinct() : utile si tu ajoutes des jointures (FK/M2M) pouvant créer des doublons
    cards = cards.distinct()

    # Rend le template avec le contexte :
    # - "cards" : queryset filtrée
    # - "q"     : valeur saisie (pour préremplir l’input)
    # - "field" : champ choisi (pour garder la sélection)
    # - "fields_config" : pour générer les <option> du select
    return render(
        request,
        "page/search_ad.html",
        {
            "cards": cards,
            "q": q,
            "field": field,
            "fields_config": FIELDS_CONFIG,
        },
    )

def recherche(request):
	return render(request, "page/search.html")
