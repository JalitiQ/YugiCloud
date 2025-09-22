# YugiCall/management/commands/sync_yugioh.py
# -*- coding: utf-8 -*-

# Import standard libs
import time                                      # pour temporiser entre les requêtes (throttling)
from typing import Dict, Any, Iterable, Optional # annotations utiles

# HTTP client
import requests                                  # client HTTP simple et robuste

# Django
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction                 # pour grouper des écritures atomiques
from django.utils import timezone                 # timestamps si besoin

# Tes modèles
from YugiCall.models import Card, CardSet         # modèles définis plus tôt


# --- Constantes d'API ---
API_BASE = "https://db.ygoprodeck.com/api/v7"     # base de l'API v7
CHECK_DB_VER_URL = f"{API_BASE}/checkDBVer.php"   # endpoint pour savoir si la DB a changé
CARDINFO_URL     = f"{API_BASE}/cardinfo.php"     # endpoint principal pour récupérer les cartes

# D'après la doc v7:
# - Rate limit: 20 requêtes / seconde, ban 1 heure si dépassé.
#   On se garde une marge de sécurité : on enverra au plus 5 req/s.
# - Conseil: télécharger / stocker en local et limiter les appels.
# Réf: https://ygoprodeck.com/api-guide/
MAX_REQ_PER_SEC = 5                               # marge (<< 20/s) pour ne JAMAIS risquer le ban
MIN_SLEEP = 1.0 / MAX_REQ_PER_SEC                 # délai minimal entre 2 appels


def _safe_get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    """
    Enveloppe compacte autour requests.get avec:
    - temporisation minimale (throttle) pour respecter MAX_REQ_PER_SEC,
    - timeout raisonnable,
    - petite logique de retry en cas d'erreurs réseau passagères.
    """
    # On mémorise l'heure du dernier appel sur l'attribut de fonction (pattern simple)
    last = getattr(_safe_get, "_last_call", 0.0)          # 0 par défaut si non défini
    now  = time.monotonic()                               # horloge monotone (pas affectée par l'heure système)
    dt   = now - last                                     # temps écoulé depuis le dernier appel

    if dt < MIN_SLEEP:                                    # si on est "trop rapide"
        time.sleep(MIN_SLEEP - dt)                        # on attend ce qu'il faut pour respecter le quota

    # On met à jour le dernier appel tout de suite (pour les appels concurrents éventuels)
    _safe_get._last_call = time.monotonic()               # type: ignore[attr-defined]

    # Petite boucle de retry (ex: 500 ou petit raté réseau). On évite d'insister si 400.
    for attempt in range(3):                              # 3 essais max
        try:
            # timeout (connect=5s, read=30s) —> évite de bloquer le worker Django
            resp = requests.get(url, params=params, timeout=(5, 30))
            # Si code HTTP 429 (throttling côté serveur) ou 5xx : on retente gentiment
            if resp.status_code in (429, 500, 502, 503, 504):
                # Backoff simple (1s puis 2s) pour laisser souffler le serveur
                time.sleep(1 + attempt)
                continue
            return resp                                   # autres cas: on renvoie tel quel
        except requests.RequestException:
            # Erreur réseau (DNS, socket, etc.). On attend et on retente.
            time.sleep(1 + attempt)

    # Si on sort de la boucle, c’est qu’on a échoué 3 fois:
    raise CommandError(f"Échec GET {url} après 3 tentatives")


def fetch_db_version() -> Optional[Dict[str, Any]]:
    """
    Récupère la "version" de la base via /checkDBVer.php.
    La doc précise que cette valeur change si de nouvelles cartes arrivent
    ou si la base est mise à jour. On s'en sert pour éviter de refetch inutilement.
    """
    r = _safe_get(CHECK_DB_VER_URL)
    if r.status_code != 200:
        # v7 renvoie 400 pour les paramètres invalides — ici on n'en envoie pas.
        raise CommandError(f"checkDBVer a répondu {r.status_code}: {r.text[:200]}")
    return r.json()   # ex: {"database_version": "X.Y.Z", "date": "YYYY-mm-dd"}


def fetch_all_cards(language: str = "fr") -> Dict[str, Any]:
    """
    Récupère *toutes* les cartes.
    NOTE: en v7, appeler cardinfo.php **sans aucun paramètre** renvoie l’ensemble des cartes.
    On ajoute 'language=fr' pour localiser les champs quand disponible.
    Réf doc: "The only way to return all cards now is by having 0 parameters in the request."
    """
    params = {"language": language}  # on ne filtre pas → on obtient TOUT (mais localisé en FR si dispo)
    r = _safe_get(CARDINFO_URL, params=params)
    if r.status_code != 200:
        raise CommandError(f"cardinfo a répondu {r.status_code}: {r.text[:200]}")
    return r.json()   # structure: {"data": [ {card...}, ... ]}


def upsert_card(card: Dict[str, Any]) -> Card:
    """
    Insère ou met à jour 1 carte (table Card) à partir d'un dict brut de l'API.
    Ne gère PAS les card_sets ici (fait séparément).
    """
    # On extrait prudemment les champs (certains sont absents pour Spell/Trap).
    cid        = card.get("id")                        # ex: 6983839
    name       = card.get("name")                      # ex: "Tornado Dragon"
    ctype      = card.get("type")                      # ex: "XYZ Monster"
    frametype  = card.get("frameType")                 # ex: "xyz"
    desc       = card.get("desc")                      # texte d'effet
    atk        = card.get("atk")                       # peut être None
    deff       = card.get("def")                       # DEF → 'def' côté API, on mappe vers def_stat
    level      = card.get("level")                     # peut être None
    race       = card.get("race")                      # ex: "Wyrm"
    attribute  = card.get("attribute")                 # ex: "WIND"

    if cid is None or name is None or ctype is None or frametype is None or desc is None:
        # On exige ces champs minimum pour créer la Card
        raise CommandError(f"Carte invalide (id/name/type/frameType/desc manquant): {card}")

    # On fait un upsert "maison" (update_or_create)
    obj, _created = Card.objects.update_or_create(
        id=cid,                                       # clé primaire (vient de l'API)
        defaults=dict(
            name=name,
            type=ctype,
            frameType=frametype,
            desc=desc,
            atk=atk,
            def_stat=deff,                             # 'def' API → def_stat modèle
            level=level,
            race=race or "",                           # race peut être absente pour Spell/Trap
            attribute=attribute or "",                 # idem
        ),
    )
    return obj


def upsert_card_sets(card_obj: Card, card: Dict[str, Any]) -> None:
    """
    Insère/MAJ les éditions (CardSet) liées à une carte.
    On applique l'unicité (card, set_code) définie dans le modèle.
    """
    # L’API renvoie une liste "card_sets" (peut être absente)
    sets = card.get("card_sets") or []
    for s in sets:
        set_name        = s.get("set_name")        # ex: "Battles of Legend: Relentless Revenge"
        set_code        = s.get("set_code")        # ex: "BLRR-EN084"
        set_rarity      = s.get("set_rarity")      # ex: "Secret Rare"
        set_rarity_code = s.get("set_rarity_code") # ex: "(ScR)" (présent quand tcgplayer_data sinon pas toujours)
        set_price       = s.get("set_price")       # string ou nombre (on laisse DecimalField gérer)

        if not set_code:
            # Sans code, on ne peut pas garantir l'unicité; on ignore proprement.
            continue

        # Upsert sur (card, set_code)
        CardSet.objects.update_or_create(
            card=card_obj,
            set_code=set_code,
            defaults=dict(
                set_name=set_name or "",
                set_rarity=set_rarity or "",
                set_rarity_code=set_rarity_code or "",
                set_price=(set_price if set_price not in ("", None) else None),
            ),
        )


class Command(BaseCommand):
    """
    Commande: python manage.py sync_yugioh
    - Vérifie si la DB distante a changé (checkDBVer).
    - Si oui ou si --force : récupère toutes les cartes et alimente la base.
    - Respecte un rate limit << limite officielle pour éviter tout ban.
    """

    help = "Synchronise la base de données avec YGOPRODeck (cartes + card_sets), avec rate limiting sûr."

    def add_arguments(self, parser):
        # --force : ignore la version distante et force un refetch complet
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force le téléchargement de toutes les cartes même si checkDBVer n'a pas changé.",
        )
        # --language : 'fr' par défaut; tu peux passer 'en' si tu préfères
        parser.add_argument(
            "--language",
            default="fr",
            help="Langue à demander à l'API (par défaut: fr).",
        )

    def handle(self, *args, **options):
        # On lit les options
        force = bool(options["force"])            # booléen: forcer le refresh
        language = str(options["language"])       # langue de l'API

        # 1) On récupère la “version” de la DB distante.
        self.stdout.write("→ Vérification de la version distante (checkDBVer)…")
        remote_ver = fetch_db_version()           # ex: {"database_version": "...", "date": "YYYY-mm-dd"}
        ver_str = f"{remote_ver}"                 # toString pour logs
        self.stdout.write(f"   Version distante: {ver_str}")

        # (Optionnel) Tu peux mémoriser localement la dernière version importée (en DB ou fichier).
        # Pour rester simple, on compare simplement à un "marqueur" stocké via un petit modèle,
        # ou, si tu veux éviter de créer un modèle, tu peux stocker un fichier texte dans /tmp.
        # Ici, simplicité: fichier local .last_db_ver (fonctionne en single-host).
        import os, json
        marker_path = os.path.join(os.getcwd(), ".last_db_ver.json")

        last_ver = None
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r", encoding="utf-8") as fh:
                    last_ver = json.load(fh)
            except Exception:
                last_ver = None

        # Si la version n'a pas changé ET pas de --force, on s'arrête gentiment.
        if (not force) and last_ver == remote_ver:
            self.stdout.write(self.style.SUCCESS("✓ Base déjà à jour (aucune MAJ distante détectée)."))
            return

        # 2) On récupère toutes les cartes (1 seule requête si aucun filtre !)
        self.stdout.write("→ Téléchargement de toutes les cartes (cardinfo)…")
        payload = fetch_all_cards(language=language)   # {"data": [ {...}, ... ]}
        cards: Iterable[Dict[str, Any]] = payload.get("data", [])
        count = 0

        # 3) On enregistre en base (transaction pour la cohérence)
        self.stdout.write("→ Écriture en base…")
        with transaction.atomic():
            for card in cards:
                # Insère/MAJ la Card
                obj = upsert_card(card)
                # Insère/MAJ les CardSet liés
                upsert_card_sets(obj, card)
                count += 1
                # (Facultatif) petits prints périodiques
                if count % 500 == 0:
                    self.stdout.write(f"   Traitée: {count} cartes…")

        self.stdout.write(self.style.SUCCESS(f"✓ Terminé : {count} cartes synchronisées."))

        # 4) On met à jour le marqueur local de version (pour éviter les refetchs inutiles)
        try:
            with open(marker_path, "w", encoding="utf-8") as fh:
                json.dump(remote_ver, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            # Non bloquant : on prévient juste
            self.stdout.write(self.style.WARNING(f"⚠ Impossible d’écrire {marker_path}: {e}"))

        # NB: Si tu souhaites historiser la date/heure d'import, tu peux créer un modèle "ImportLog".
        self.stdout.write(self.style.SUCCESS("✓ Marqueur de version mis à jour."))
