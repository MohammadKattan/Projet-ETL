from django.urls import path
from .views import api_produits_filtre

urlpatterns = [
    path('produits/', api_produits_filtre),  # Aucune donnée imposée dans l'URL
]
