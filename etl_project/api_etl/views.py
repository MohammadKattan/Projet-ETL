import pandas as pd
import sqlite3
from django.http import JsonResponse
import os
from django.conf import settings

# 🔹 Dictionnaire des requêtes SQL dynamiques
QUERY_MAP = {
    "cat": "SELECT * FROM produits WHERE catID = {catID}",
    
    "mag-cat": "SELECT COUNT(DISTINCT magID) AS total_magasins FROM pointDeVente_tous WHERE catID = {catID}",
    
    "fab-cat": "SELECT COUNT(DISTINCT fabID) AS total_fabricants FROM produits WHERE catID = {catID}",
    
    "avg-prod-per-fab": """
        SELECT AVG(product_count) AS avg_products_per_fab
        FROM (
            SELECT fabID, COUNT(DISTINCT prodID) AS product_count
            FROM produits
            WHERE catID = {catID}
            AND (dateID BETWEEN {debut} AND {fin})
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
    
    "nb-mag-date" : """
        SELECT COUNT(DISTINCT magID) as nbmag
            FROM pointDeVente_tous
            WHERE catID = {catID}
            AND (dateID BETWEEN {debut} AND {fin})
    """,
    
    "nb-mag-periode" : """
        SELECT COUNT(DISTINCT magID) AS nbmag
            FROM pointDeVente_tous
            WHERE catID = {catID}
            AND SUBSTR(dateID, 1, 4) = COALESCE('{annee}', strftime('%Y', 'now'))
            AND (
                (SUBSTR(dateID, 5, 2) BETWEEN '01' AND '03' AND {periode} = 1) OR
                (SUBSTR(dateID, 5, 2) BETWEEN '04' AND '06' AND {periode} = 2) OR
                (SUBSTR(dateID, 5, 2) BETWEEN '07' AND '09' AND {periode} = 3) OR
                (SUBSTR(dateID, 5, 2) BETWEEN '10' AND '12' AND {periode} = 4)
            );
    """,
    
    "nb-mag-all" : """
        SELECT 
            SUBSTR(dateID, 1, 4) || '-' || SUBSTR(dateID, 5, 2) AS mois, 
            COUNT(DISTINCT magID) AS nbmag
            FROM pointDeVente_tous
                WHERE catID = {catID}
                AND dateID >= '{annee}{mois}01'  -- début de la date choisie (format YYYYMMDD)
                AND dateID <= strftime('%Y%m%d', 'now')  -- date actuelle (format YYYYMMDD)
                GROUP BY mois
                ORDER BY mois;

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
    mois = request.GET.get("mois")
    annee = request.GET.get("annee")
    periode = request.GET.get("periode")
    debut = request.GET.get("debut")
    fin = request.GET.get("fin")

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
        query = sql_query.format(catID=cat_id,magID= mag_id,fabID = fab_id, mois = mois, annee = annee, periode = periode, debut = debut, fin = fin)
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
    top_magasins_ID = tuple(df_top_mag["magID"].tolist())
    # Vérifier si la liste est vide
    if not top_magasins_ID:
        return JsonResponse({"error": "Aucun magasin trouvé"}, status=404)
    # Requête SQL pour obtenir les produits par magasin
    query_best_seller = f"""
        SELECT magID, catID,
            COUNT(DISTINCT prodID) AS total_produits
        FROM pointDeVente_tous
        WHERE catID = {cat_id} AND fabID = {fab_id} AND magID IN {top_magasins_ID}
        GROUP BY magID
    """
    df_best_seller = pd.read_sql(query_best_seller, conn)
    # Convertir les résultats en dictionnaire
    best_seller_dict = dict(zip(df_best_seller["magID"], df_best_seller["total_produits"]))
    # Convertir `df_top_mag` en dictionnaire pour un accès plus rapide
    top_mag_dict = dict(zip(df_top_mag["magID"], df_top_mag["total_produits"]))

    top_mag_list = []
    total_percentage = 0.0
    valid_count = 0

    # Parcours de **tous** les magasins de df_top_mag
    for magID, total_produits_top in top_mag_dict.items():
        total_produits_best = best_seller_dict.get(magID, 0)  # 0 si magID n'existe pas dans best_seller_dict

        if total_produits_top != 0:
            percentage = (total_produits_best / total_produits_top) * 100
            total_percentage += percentage
            valid_count += 1
        else:
            percentage = 0.0

        top_mag_list.append({
            "magID": magID,
            "total_produits": total_produits_top,
            "nb_produits_fab" : total_produits_best,
            "percentage": percentage
        })

    # Calcul de la moyenne générale uniquement sur les magasins valides
    avg_percentage = total_percentage / valid_count if valid_count > 0 else 0.0

    return JsonResponse({
        "average": avg_percentage,
        "top_mag": top_mag_list
    })

