import pandas as pd
import os
from django.conf import settings
from django.http import JsonResponse

def api_produits_filtre(request, cat_id):
    produits_csv = os.path.join(settings.DATA_DIR, 'produits-tous.csv')
    #produits_csv = "/home/shyam/2.CFA/4.ETLT/Projet-ETL/data/produits-tous.csv"

    # Vérifier si le fichier existe
    if not os.path.exists(produits_csv):
        return JsonResponse({"error": "Fichier CSV non trouvé"}, status=404)

    # Lire le CSV et afficher les colonnes détectées
    df_produits = pd.read_csv(produits_csv, sep="\t")  # 🔹 Lire avec séparateur tabulation
    print("Colonnes détectées :", df_produits.columns.tolist())  # 🔹 Debugging

    # Vérifier la présence de catID
    if "catID" not in df_produits.columns:
        return JsonResponse({"error": f"Colonne catID manquante, colonnes trouvées: {df_produits.columns.tolist()}"}, status=500)

    # Filtrer les produits par catégorie
    df_filtered = df_produits[df_produits["catID"] == cat_id]
    
    data = df_filtered.to_dict(orient="records")
    return JsonResponse(data, safe=False)
