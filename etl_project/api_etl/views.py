import pandas as pd
import sqlite3
from django.http import JsonResponse
import os
from django.conf import settings

def api_produits_filtre(request, cat_id):
    produits_csv = os.path.join(settings.DATA_DIR, 'produits-tous.csv')

    # 🔹 Vérifier si le fichier existe
    if not os.path.exists(produits_csv):
        return JsonResponse({"error": "Fichier CSV non trouvé"}, status=404)

    # 🔹 Lire le CSV avec le bon séparateur (tabulation)
    df_produits = pd.read_csv(produits_csv, sep="\t")

    # 🔹 Vérifier que la colonne catID existe
    if "catID" not in df_produits.columns:
        return JsonResponse({"error": f"Colonne catID manquante, colonnes trouvées: {df_produits.columns.tolist()}"}, status=500)

    # 🔹 Créer une base SQLite en mémoire et insérer les données
    conn = sqlite3.connect(":memory:")
    df_produits.to_sql("produits", conn, index=False, if_exists="replace")

    # 🔹 Exécuter une requête SQL pour filtrer les produits de la catégorie demandée
    query = f"""
        SELECT * FROM produits WHERE catID = {cat_id}
            
    """
    df_filtered = pd.read_sql(query, conn)

    # 🔹 Fermer la connexion SQLite
    conn.close()

    # 🔹 Convertir en JSON et renvoyer via Django REST API
    data = df_filtered.to_dict(orient="records")
    return JsonResponse(data, safe=False)
