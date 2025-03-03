from django.urls import path
from .views import api_produits_filtre  # ✅ Vérifier que l'import est correct

urlpatterns = [
    path('produits/<int:cat_id>/', api_produits_filtre),  # Route API pour filtrer les produits
]
