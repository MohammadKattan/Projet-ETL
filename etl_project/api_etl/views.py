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
            (COUNT(DISTINCT fabID) * 0.1 +
                COUNT(DISTINCT catID) * 0.2 +
                COUNT(DISTINCT prodID) * 0.3 +
                COUNT(*) * 0.4) AS score
        FROM pointDeVente_tous
        GROUP BY magID
        ORDER BY score DESC
        LIMIT 10;
    """,
    "all": "SELECT * FROM produits"
}

def api_produits_filtre(request):
    # 🔹 Définition des chemins des fichiers CSV
    produits_csv = os.path.join(settings.DATA_DIR, 'produits-tous.csv')
    point_de_vente_csv = os.path.join(settings.DATA_DIR, 'pointsDeVente-tous.csv')

    # 🔹 Vérification de l'existence des fichiers CSV
    for fichier in [produits_csv, point_de_vente_csv]:
        if not os.path.exists(fichier):
            return JsonResponse({"error": f"Fichier {os.path.basename(fichier)} non trouvé"}, status=404)

    # 🔹 Chargement des fichiers CSV dans des DataFrames pandas
    df_produits = pd.read_csv(produits_csv, sep="\t")
    df_point_de_vente = pd.read_csv(point_de_vente_csv, sep="\t")

    # 🔹 Création d'une base de données SQLite en mémoire
    conn = sqlite3.connect(":memory:")
    df_produits.to_sql("produits", conn, index=False, if_exists="replace")
    df_point_de_vente.to_sql("pointDeVente_tous", conn, index=False, if_exists="replace")

    # 🔹 Récupération des paramètres de la requête
    type_param = request.GET.get("type", "all")  # Par défaut, récupérer tout
    cat_id = request.GET.get("catID")

    # 🔹 Vérification de la validité du type de requête
    if type_param not in QUERY_MAP:
        return JsonResponse({"error": "Type de requête inconnu"}, status=400)
    # 🔹 Construction de la requête SQL
    sql_query = QUERY_MAP[type_param]

    try:
        query = sql_query.format(catID=cat_id)
    except KeyError as e:
        return JsonResponse({"error": f"Paramètre manquant: {e}"}, status=400)

    # 🔹 Exécution de la requête SQL
    df_result = pd.read_sql(query, conn)
    conn.close()

    # 🔹 Conversion du résultat en JSON et envoi de la réponse
    data = df_result.to_dict(orient="records")
    return JsonResponse(data, safe=False)
