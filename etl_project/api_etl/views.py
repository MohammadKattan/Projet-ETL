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
    "top-magasins": """
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
    "top-magasins-cat": """
        SELECT magID,
            COUNT(DISTINCT fabID) AS total_fabricants,
            COUNT(DISTINCT prodID) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT fabID) * 0.1 +
                COUNT(DISTINCT prodID) * 0.3 +
                COUNT(*) * 0.6) AS score
        FROM pointDeVente_tous
        WHERE catID = {catID}
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
    mag_id = request.GET.get("magID")
    fab_id = request.GET.get("fabID")

    # 🔹 Vérification de la validité du type de requête
    if type_param not in QUERY_MAP and type_param != "top-1" and type_param != "avg-cat-fab-10-mag":
        return JsonResponse({"error": "Type de requête inconnu"}, status=400)

    if type_param == "top-1": 
        return get_best_magasin_for_category(conn, cat_id)
    if type_param == "avg-cat-fab-10-mag":
        # Exécuter la requête "top-magasins-cat"
        query_top_magasin_cat = QUERY_MAP["top-magasins-cat"].format(catID=cat_id)
        df_top_mag = pd.read_sql(query_top_magasin_cat, conn)
        if df_top_mag.empty:
            return JsonResponse({"error": "Aucun magasin trouvé pour cette catégorie"}, status=404)
        top_10_magasins = dict(zip(df_top_mag["magID"], df_top_mag["total_produits"]))
        print(top_10_magasins)
        return get_avg_for_fab_of_top_magasin(conn, cat_id, fab_id, df_top_mag)

    # 🔹 Construction de la requête SQL
    sql_query = QUERY_MAP[type_param]

    try:
        query = sql_query.format(catID=cat_id,magID= mag_id,fabID = fab_id)
    except KeyError as e:
        return JsonResponse({"error": f"Paramètre manquant: {e}"}, status=400)

    # 🔹 Exécution de la requête SQL
    df_result = pd.read_sql(query, conn)
    conn.close()

    # 🔹 Conversion du résultat en JSON et envoi de la réponse
    data = df_result.to_dict(orient="records")
    return JsonResponse(data, safe=False)


def get_best_magasin_for_category(conn, cat_id):
    """
    Fonction qui trouve le meilleur magasin pour une catégorie donnée selon le score :
    - Nombre de produits vendus pour cette catégorie * 0.4
    - Nombre de lignes d'opération * 0.3
    - Nombre de fabricants présents dans ce magasin pour cette catégorie * 0.3
    """

    # Récupérer les 10 meilleurs magasins pour cette catégorie
    top_10_query = QUERY_MAP["top-magasins"].format(catID=cat_id)
    df_top_10 = pd.read_sql(top_10_query, conn)

    if df_top_10.empty:
        return JsonResponse({"error": "Aucun magasin trouvé pour cette catégorie"}, status=404)

    top_mag_ids = tuple(df_top_10["magID"].tolist())

    # Sélectionner le meilleur magasin parmi ces 10
    query_best_seller = f"""
        SELECT magID,
            COUNT(DISTINCT fabID) AS total_fabricants,
            COUNT(DISTINCT prodID) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT prodID) * 0.3 +
            COUNT(*) * 0.6 +
            COUNT(DISTINCT fabID) * 0.1) AS score
        FROM pointDeVente_tous
        WHERE catID = {cat_id} AND magID IN {top_mag_ids}
        GROUP BY magID
        ORDER BY score DESC
        LIMIT 1;
    """
    
    df_best_seller = pd.read_sql(query_best_seller, conn)

    if df_best_seller.empty:
        return JsonResponse({"error": "Aucun meilleur magasin trouvé"}, status=404)

    return JsonResponse(df_best_seller.to_dict(orient="records"), safe=False)


def get_avg_for_fab_of_top_magasin(conn, cat_id, fab_id, df_top_mag):
    # Convertir les magID en tuple pour être utilisé dans la requête SQL
    top_10_magasins_ID = tuple(df_top_mag["magID"].tolist())
    # Requête SQL pour obtenir les produits par magasin
    query_best_seller = f"""
        SELECT magID, catID,
            COUNT(DISTINCT prodID) AS total_produits
        FROM pointDeVente_tous
        WHERE catID = {cat_id} AND fabID = {fab_id} AND magID IN {top_10_magasins_ID}
        GROUP BY magID
    """
    df_best_seller = pd.read_sql(query_best_seller, conn)
    if df_best_seller.empty:
        return JsonResponse({"error": "Aucun meilleur magasin trouvé"}, status=404)
    # Convertir les résultats de la requête en dictionnaire
    best_seller_dict = dict(zip(df_best_seller["magID"], df_best_seller["total_produits"]))
    # Créer un dictionnaire de top magasins avec leurs produits
    top_mag_dict = dict(zip(df_top_mag["magID"], df_top_mag["total_produits"]))
    res = 0.0

    for magID in best_seller_dict:
        # Vérification si magID existe dans les deux dictionnaires et que total_produits n'est pas zéro
        if magID in top_mag_dict and top_mag_dict[magID] != 0:
            res += best_seller_dict[magID] / top_mag_dict[magID] 
    # Calculer la moyenne si des magasins valides ont été trouvés
    res = (res / len(top_10_magasins_ID))*100
    return JsonResponse({"average": res})

