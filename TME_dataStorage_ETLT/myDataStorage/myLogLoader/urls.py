from django.urls import path
from myLogLoader import views

urlpatterns = [
    path('produits-tous-archive/', views.ArchiveDeProduits.as_view()),
]
