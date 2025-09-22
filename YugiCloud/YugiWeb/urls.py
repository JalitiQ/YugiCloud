from django.urls import path, include
from . import views

app_name = "YugiWeb"

urlpatterns = [
    path('', views.accueil, name="accueil"),
	path('search/fr/', views.recherche_BDD, name="search_fr"),
	path('search/en/', views.recherche_BDD_en, name="search_en"),
]