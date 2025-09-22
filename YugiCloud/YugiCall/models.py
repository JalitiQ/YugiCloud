from django.db import models

# Create your models here.

# On importe les classes de base pour définir des modèles Django.
from django.db import models


# ========================
#  Modèle principal : Card
# ========================
class Card(models.Model):
    """
    Représente une carte Yu-Gi-Oh! telle que renvoyée par l'API YGOPRODeck.
    Une carte est unique par son "id" (donné par l’API).
    """

    # Champ 'id' fourni par l’API (ex: 6983839).
    # BigIntegerField permet de stocker de grands entiers.
    # primary_key=True => ce champ devient la clé primaire dans la base.
    id = models.BigIntegerField(primary_key=True)

    # Nom de la carte ("Tornado Dragon").
    # max_length=255 : limite de taille.
    # db_index=True : index en base pour accélérer les recherches par nom.
    name = models.CharField(max_length=255, db_index=True)

    # Type de carte ("XYZ Monster", "Effect Monster", "Spell Card", etc.).
    # db_index=True : on pourra filtrer rapidement par type.
    type = models.CharField(max_length=100, db_index=True)

    # FrameType = type d'encadrement (par ex. "xyz", "effect", "spell").
    # max_length=50 suffit largement.
    frameType = models.CharField(max_length=50)

    # Description / texte d'effet.
    # TextField = champ texte long, parfait pour les descriptions.
    desc = models.TextField()

    # Valeur ATK (2100 dans l’exemple).
    # Certaines cartes n’ont pas d’ATK (Spell/Trap), donc on autorise null/blank.
    # db_index=True : on pourra faire des recherches rapides (ex: ATK > 2000).
    atk = models.IntegerField(null=True, blank=True, db_index=True)

    # Valeur DEF (2000 dans l’exemple).
    # ⚠️ On ne peut pas nommer ce champ 'def' (mot réservé Python),
    # donc on l’appelle 'def_stat'.
    # Même logique que pour ATK : null/blank autorisé + index.
    def_stat = models.IntegerField(null=True, blank=True, db_index=True)

    # Niveau / Rank / Link Rating.
    # null/blank car les Magies/Pièges n’ont pas de niveau.
    level = models.IntegerField(null=True, blank=True, db_index=True)

    # Race (ou sous-type, ex: "Dragon", "Wyrm", "Warrior").
    # db_index=True pour filtrer vite.
    race = models.CharField(max_length=100, db_index=True)

    # Attribut (ex: "WIND", "FIRE", "LIGHT", etc.).
    # db_index=True également.
    attribute = models.CharField(max_length=50, db_index=True)

    class Meta:
        # Options de métadonnées pour le modèle.
        indexes = [
            # Création d’index en base pour accélérer les recherches fréquentes.
            models.Index(fields=["name"]),
            models.Index(fields=["type"]),
            models.Index(fields=["race"]),
            models.Index(fields=["attribute"]),
            models.Index(fields=["atk"]),
            models.Index(fields=["def_stat"]),
            models.Index(fields=["level"]),
        ]

    def __str__(self):
        # Méthode qui définit la représentation textuelle de l’objet (utile dans l’admin).
        return f"{self.name} ({self.id})"


# ========================
#  Modèle secondaire : CardSet
# ========================
class CardSet(models.Model):
    """
    Représente une "édition" ou "set" d’une carte.
    Une carte peut apparaître dans plusieurs sets différents,
    avec un code, une rareté et un prix.
    """

    # ForeignKey = relation vers la table Card (1 carte → N sets).
    # on_delete=models.CASCADE : si on supprime la carte, ses sets disparaissent aussi.
    # related_name="card_sets" : permet d’accéder à card.card_sets.all().
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="card_sets")

    # Nom du set (ex: "Battles of Legend: Relentless Revenge").
    # db_index=True pour des recherches rapides.
    set_name = models.CharField(max_length=255, db_index=True)

    # Code du set (ex: "BLRR-EN084").
    # db_index=True pour pouvoir rechercher vite par code.
    set_code = models.CharField(max_length=50, db_index=True)

    # Nom de la rareté (ex: "Secret Rare").
    set_rarity = models.CharField(max_length=100)

    # Code de rareté abrégé (ex: "(ScR)").
    set_rarity_code = models.CharField(max_length=20)

    # Prix de la carte dans ce set (ex: "4.08").
    # DecimalField : stocke un nombre décimal précis.
    # max_digits=10, decimal_places=2 : max 99999999.99
    # null=True/blank=True car parfois l’API peut ne pas renvoyer de prix.
    set_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        # Métadonnées pour CardSet.
        constraints = [
            # Contrainte d’unicité : pas de doublon (même carte + même set_code).
            models.UniqueConstraint(fields=["card", "set_code"], name="uniq_card_setcode"),
        ]
        indexes = [
            # Index supplémentaires pour accélérer les recherches.
            models.Index(fields=["set_name"]),
            models.Index(fields=["set_code"]),
        ]

    def __str__(self):
        # Représentation textuelle : "Nom de carte — Code set"
        return f"{self.card.name} — {self.set_code}"
