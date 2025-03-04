import pandas as pd
import sqlite3
from django.http import JsonResponse
import os
from django.conf import settings

# 🔹 Dictionnaire des requêtes SQL dynamiques
QUERY_MAP = {
    "cat": "SELECT * FROM produits WHERE catID = {catID}",
    "fab-cat": "SELECT COUNT(DISTINCT fabID) AS total_fabricants FROM produits WHERE catID = {catID}",
    "avg-prod-per-fab": """
        SELECT AVG(product_count) AS avg_products_per_fab
        FROM (
            SELECT fabID, COUNT(prodID) AS product_count
            FROM produits
            WHERE catID = {catID}
            GROUP BY fabID
        ) AS subquery
    """,
    "top-magasins-cat": """
        SELECT magID,
            COUNT(DISTINCT fabID) AS total_fabricants,
            COUNT(DISTINCT catID) AS total_categories,
            COUNT(DISTINCT prodID) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT fabID) * 0.4 +
                COUNT(DISTINCT catID) * 0.3 +
                COUNT(DISTINCT prodID) * 0.2 +
                COUNT(*) * 0.1) AS score
        FROM pointDeVente_tous
        GROUP BY magID
        ORDER BY score DESC
        LIMIT 10;
    """,
    "all": "SELECT * FROM produits"
}

def api_produits_filtre(request):
    produits_csv = os.path.join(settings.DATA_DIR, 'produits-tous.csv')

    # 🔹 Vérifier si le fichier CSV existe
    if not os.path.exists(produits_csv):
        return JsonResponse({"error": "Fichier CSV non trouvé"}, status=404)

    # 🔹 Charger le CSV
    df_produits = pd.read_csv(produits_csv, sep="\t")

    # 🔹 Vérifier si la colonne catID et fabID existent
    required_columns = ["catID", "fabID"]
    for col in required_columns:
        if col not in df_produits.columns:
            return JsonResponse({"error": f"Colonne {col} manquante, colonnes trouvées: {df_produits.columns.tolist()}"}, status=500)

    # 🔹 Créer une base SQLite temporaire
    conn = sqlite3.connect(":memory:")
    df_produits.to_sql("produits", conn, index=False, if_exists="replace")

    # 🔹 Récupérer le type de requête et vérifier s'il est défini
    type_param = request.GET.get("type", "all")  # Par défaut, récupérer tout
    cat_id = request.GET.get("catID")

    # 🔹 Vérifier si le type est valide
    if type_param not in QUERY_MAP:
        return JsonResponse({"error": "Type de requête inconnu"}, status=400)

    # 🔹 Récupérer la requête SQL correspondante
    sql_query = QUERY_MAP[type_param]

    # 🔹 Remplacer les variables dynamiques dans la requête
    try:
        query = sql_query.format(catID=cat_id)
    except KeyError as e:
        return JsonResponse({"error": f"Paramètre manquant: {e}"}, status=400)

    # 🔹 Exécuter la requête et récupérer les résultats
    df_result = pd.read_sql(query, conn)
    conn.close()

    # 🔹 Convertir le résultat en JSON et renvoyer la réponse
    data = df_result.to_dict(orient="records")
    return JsonResponse(data, safe=False)
