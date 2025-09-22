from django.urls import path, include
from . import views

app_name = "YugiWeb"

urlpatterns = [
    path('', views.accueil, name="accueil"),
	path('search/', views.recherche_BDD, name="search"),
	path('search2/', views.recherche, name="search2"),
]