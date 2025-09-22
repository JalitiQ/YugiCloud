from django.contrib import admin

# Register your models here.
# YugiCall/admin.py
from django.contrib import admin
from .models import Card, CardSet


# === Configuration pour CardSet ===
class CardSetInline(admin.TabularInline):
    """
    Permet d’afficher/éditer les sets directement dans la page d’admin d’une Card.
    TabularInline = affichage sous forme de tableau.
    """
    model = CardSet
    extra = 1   # combien de lignes vides afficher pour ajouter de nouveaux sets


# === Configuration pour Card ===
@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    """
    Affichage personnalisé du modèle Card dans l’admin.
    """
    # Colonnes visibles dans la liste des cartes
    list_display = ("id", "name", "type", "atk", "def_stat", "level", "race", "attribute")
    # Champs sur lesquels on peut rechercher
    search_fields = ("name", "type", "race", "attribute")
    # Filtres sur la droite
    list_filter = ("type", "race", "attribute", "level")
    # Lien direct dans la liste (clickable)
    list_display_links = ("id", "name")
    # Inline pour afficher les sets associés
    inlines = [CardSetInline]


# === Configuration pour CardSet ===
@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    """
    Affichage personnalisé du modèle CardSet (si on veut les gérer séparément).
    """
    list_display = ("card", "set_name", "set_code", "set_rarity", "set_price")
    search_fields = ("set_name", "set_code", "set_rarity")
    list_filter = ("set_rarity",)
