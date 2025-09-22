# On importe la fonction path qui sert à définir les routes de l'application Django.
from django.urls import path
# On importe la vue que l’on vient de créer.
from .views import CardSearchFRView

# On définit la liste des routes (URL patterns).
urlpatterns = [
    # Quand quelqu’un appelle /api/cards-fr, Django déclenche CardSearchFRView.
    path("api/cards-fr", CardSearchFRView.as_view(), name="card-search-fr"),
    #path("api/cards-en", CardSearchENView.as_view(), name="card-search-en"),
]
