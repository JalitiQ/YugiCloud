# YugiCall/management/commands/sync_yugioh_en.py
# -*- coding: utf-8 -*-

# Import standard libs
import time                                      # pour temporiser entre les requêtes (throttling)
from typing import Dict, Any, Iterable, Optional # annotations utiles

# HTTP client
import requests                                  # client HTTP simple et robuste

# Django
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction                 # pour grouper des écritures atomiques

# Tes modèles EN
from YugiCall.models import CardEN, CardSetEN


# --- Constantes d'API ---
API_BASE = "https://db.ygoprodeck.com/api/v7"     # base de l'API v7
CHECK_DB_VER_URL = f"{API_BASE}/checkDBVer.php"   # endpoint pour savoir si la DB a changé
CARDINFO_URL     = f"{API_BASE}/cardinfo.php"     # endpoint principal pour récupérer les cartes

# Rate limit officiel ~20 req/s ; on garde une marge confortable
MAX_REQ_PER_SEC = 5
MIN_SLEEP = 1.0 / MAX_REQ_PER_SEC


def _safe_get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    """
    GET avec throttle + retries simples.
    """
    last = getattr(_safe_get, "_last_call", 0.0)
    now  = time.monotonic()
    dt   = now - last
    if dt < MIN_SLEEP:
        time.sleep(MIN_SLEEP - dt)
    _safe_get._last_call = time.monotonic()       # type: ignore[attr-defined]

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=(5, 30))
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1 + attempt)
                continue
            return resp
        except requests.RequestException:
            time.sleep(1 + attempt)
    raise CommandError(f"Échec GET {url} après 3 tentatives")


def fetch_db_version() -> Dict[str, Any]:
    """
    Récupère la version distante (utile pour éviter des refetchs si inchangée).
    """
    r = _safe_get(CHECK_DB_VER_URL)
    if r.status_code != 200:
        raise CommandError(f"checkDBVer a répondu {r.status_code}: {r.text[:200]}")
    return r.json()   # ex: {"database_version": "...", "date": "YYYY-mm-dd"}


def fetch_all_cards_en() -> Dict[str, Any]:
    """
    Récupère *toutes* les cartes en anglais.
    IMPORTANT : pour obtenir le catalogue complet, on NE passe AUCUN paramètre.
                (EN est la langue par défaut de l'API.)
    Réponse: {"data": [ {card...}, ... ]}
    """
    r = _safe_get(CARDINFO_URL, params=None)  # aucun paramètre → full dump EN
    if r.status_code != 200:
        raise CommandError(f"cardinfo a répondu {r.status_code}: {r.text[:200]}")
    return r.json()


def upsert_card_en(card: Dict[str, Any]) -> CardEN:
    """
    Insère/Màj une carte EN (table CardEN) à partir du dict brut API.
    Ne gère pas les sets ici.
    """
    cid        = card.get("id")
    name       = card.get("name")
    ctype      = card.get("type")
    frametype  = card.get("frameType")
    desc       = card.get("desc")
    atk        = card.get("atk")
    deff       = card.get("def")
    level      = card.get("level")
    race       = card.get("race")
    attribute  = card.get("attribute")

    if cid is None or name is None or ctype is None or frametype is None or desc is None:
        raise CommandError(f"Carte invalide (id/name/type/frameType/desc manquant): {card}")

    obj, _created = CardEN.objects.update_or_create(
        id=cid,
        defaults=dict(
            name=name,
            type=ctype,
            frameType=frametype,
            desc=desc,
            atk=atk,
            def_stat=deff,              # 'def' API → champ def_stat du modèle
            level=level,
            race=race or "",
            attribute=attribute or "",
        ),
    )
    return obj


def upsert_card_sets_en(card_obj: CardEN, card: Dict[str, Any]) -> None:
    """
    Insère/Màj les éditions EN liées à une carte (table CardSetEN).
    Unicité (card, set_code).
    """
    sets = card.get("card_sets") or []
    for s in sets:
        set_name        = s.get("set_name")
        set_code        = s.get("set_code")
        set_rarity      = s.get("set_rarity")
        set_rarity_code = s.get("set_rarity_code")
        set_price       = s.get("set_price")

        if not set_code:
            continue

        CardSetEN.objects.update_or_create(
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
    Commande: python manage.py sync_yugioh_en
    - Vérifie la version distante
    - Si nouvelle version (ou --force), télécharge TOUT le catalogue EN et alimente CardEN/CardSetEN
    """

    help = "Synchronise la base locale EN depuis YGOPRODeck (CardEN + CardSetEN), avec throttling sûr."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force le téléchargement même si la version distante n'a pas changé.",
        )

    def handle(self, *args, **options):
        force = bool(options["force"])

        self.stdout.write("→ Vérification de la version distante (checkDBVer)…")
        remote_ver = fetch_db_version()
        self.stdout.write(f"   Version distante: {remote_ver}")

        # Marqueur de version EN séparé de la version FR
        import os, json
        marker_path = os.path.join(os.getcwd(), ".last_db_ver_en.json")

        last_ver = None
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r", encoding="utf-8") as fh:
                    last_ver = json.load(fh)
            except Exception:
                last_ver = None

        if (not force) and last_ver == remote_ver:
            self.stdout.write(self.style.SUCCESS("✓ Base EN déjà à jour (aucune MAJ distante détectée)."))
            return

        self.stdout.write("→ Téléchargement du dump EN (cardinfo)…")
        payload = fetch_all_cards_en()
        cards: Iterable[Dict[str, Any]] = payload.get("data", [])
        count = 0

        self.stdout.write("→ Écriture en base (EN)…")
        with transaction.atomic():
            for raw in cards:
                obj = upsert_card_en(raw)
                upsert_card_sets_en(obj, raw)
                count += 1
                if count % 500 == 0:
                    self.stdout.write(f"   Traitée: {count} cartes…")

        self.stdout.write(self.style.SUCCESS(f"✓ Terminé : {count} cartes EN synchronisées."))

        try:
            with open(marker_path, "w", encoding="utf-8") as fh:
                json.dump(remote_ver, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠ Impossible d’écrire {marker_path}: {e}"))

        self.stdout.write(self.style.SUCCESS("✓ Marqueur EN mis à jour."))
