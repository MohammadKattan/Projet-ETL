import pandas as pd
import sqlite3
from django.http import JsonResponse
import os
from django.conf import settings
from datetime import date

# 🔹 Dictionnaire des requêtes SQL dynamiques
QUERY_MAP = {
    "cat": "SELECT * FROM produits WHERE catid = {catID}",
    
    "mag-cat": "SELECT COUNT(DISTINCT magid) AS total_magasins FROM points_de_vente WHERE catid = {catID}",
    
    "fab-cat": "SELECT COUNT(DISTINCT fabid) AS total_fabricants FROM produits WHERE catid = {catID}",
    
    "avg-prod-per-fab": """
        SELECT AVG(product_count) AS avg_products_per_fab
        FROM (
            SELECT fabid, COUNT(DISTINCT prodid) AS product_count
            FROM produits
            WHERE catid = {catID}
            AND dateid BETWEEN '{debut}' AND '{fin}'
            GROUP BY fabid
        ) AS subquery
    """,
    
    "top-magasins": """
        SELECT magid,
            COUNT(DISTINCT fabid) AS total_fabricants,
            COUNT(DISTINCT catid) AS total_categories,
            COUNT(DISTINCT prodid) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT fabid) * 0.1 +
                COUNT(DISTINCT catid) * 0.2 +
                COUNT(DISTINCT prodid) * 0.3 +
                COUNT(*) * 0.4) AS score
        FROM points_de_vente
        WHERE dateid BETWEEN '{debut}' AND '{fin}'
        GROUP BY magid
        ORDER BY score DESC
        LIMIT 10;
    """,
    
    "top-magasins-cat": """
        SELECT magid,
            COUNT(DISTINCT fabid) AS total_fabricants,
            COUNT(DISTINCT prodid) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT fabid) * 0.1 +
                COUNT(DISTINCT prodid) * 0.3 +
                COUNT(*) * 0.6) AS score
        FROM points_de_vente
        WHERE catid = {catID}
        AND dateid BETWEEN '{debut}' AND '{fin}'
        GROUP BY magid
        ORDER BY score DESC
        LIMIT 10;
    """,
    
    "nb-mag-cat-date" : """
        SELECT 
            strftime('%Y-%m', dateid) AS mois,
            COUNT(DISTINCT magid) AS nbmag
            FROM points_de_vente
                WHERE catid = {catID}
                AND strftime('%Y', dateid) = '{annee}'
                GROUP BY mois
                ORDER BY mois;
    """,

"score-evolution": """
    SELECT 
        strftime('%Y-%m', dateid) AS mois,
        COUNT(*) AS total_ventes,
        SUM(CASE WHEN fabid = {fabID} THEN 1 ELSE 0 END) AS ventes_fab,
        -- ✅ Correction : éviter NaN en utilisant COALESCE
        COALESCE(
            (SUM(CASE WHEN fabid = {fabID} THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0)), 
            0.0
        ) AS score_sante
    FROM points_de_vente
    WHERE catid = {catID}
    AND dateid BETWEEN '2022-01-01' AND DATE('now')
    GROUP BY mois
    ORDER BY mois;
"""




}

def api_produits_filtre(request):
    # 🔹 Chemin de la base de données SQLite
    db_path = os.path.join(settings.BASE_DIR, 'database.db')

    # 🔹 Vérification de l'existence du fichier de base de données
    if not os.path.exists(db_path):
        return JsonResponse({"error": "Base de données non trouvée"}, status=404)

    # 🔹 Connexion à la base de données SQLite
    conn = sqlite3.connect(db_path)

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
    if type_param not in QUERY_MAP and type_param != "top-1" and type_param != "avg-cat-fab-10-mag" and type_param != "score-sante-touts-les-mois":
        return JsonResponse({"error": "Type de requête inconnu"}, status=400)

    if type_param == "top-1": 
        return get_best_magasin_for_category(conn, cat_id)
    if type_param == "avg-cat-fab-10-mag":
        # Exécuter la requête "top-magasins-cat"
        query_top_magasin_cat = QUERY_MAP["top-magasins-cat"].format(catID=cat_id,debut=debut,fin=fin)
        df_top_mag = pd.read_sql(query_top_magasin_cat, conn)
        if df_top_mag.empty:
            return JsonResponse({"error": "Aucun magasin trouvé pour cette catégorie"}, status=404)
        top_10_magasins = dict(zip(df_top_mag["magid"], df_top_mag["total_produits"]))
        print(top_10_magasins)
        return get_avg_for_fab_of_top_magasin(conn, cat_id, fab_id, df_top_mag)
    if type_param == "score-sante-touts-les-mois":
        today = date.today().strftime('%Y-%m-%d')
        print(today)
        # Exécuter la requête "top-magasins-cat"
        query_top_magasin_cat = QUERY_MAP["top-magasins-cat"].format(catID=cat_id,debut='2022-01-01',fin=today)
        df_top_mag = pd.read_sql(query_top_magasin_cat, conn)
        if df_top_mag.empty:
            return JsonResponse({"error": "Aucun magasin trouvé pour cette catégorie"}, status=404)
        top_10_magasins = dict(zip(df_top_mag["magid"], df_top_mag["total_produits"]))
        print(top_10_magasins)
        return get_avg_for_fab_of_top_magasin2(conn, cat_id, fab_id, df_top_mag)

    # 🔹 Construction de la requête SQL
    sql_query = QUERY_MAP[type_param]

    try:
        query = sql_query.format(catID=cat_id, magID=mag_id, fabID=fab_id, mois=mois, annee=annee, periode=periode, debut=debut, fin=fin)
    except KeyError as e:
        return JsonResponse({"error": f"Paramètre manquant: {e}"}, status=400)

    # 🔹 Exécution de la requête SQL
    df_result = pd.read_sql(query, conn)
    conn.close()

    # 🔹 Conversion du résultat en JSON et envoi de la réponse
    data = df_result.to_dict(orient="records")
    print(data)
    return JsonResponse(data, safe=False)


def get_best_magasin_for_category(conn, cat_id):

    # Récupérer les 10 meilleurs magasins pour cette catégorie
    top_10_query = QUERY_MAP["top-magasins"].format(catid=cat_id)
    df_top_10 = pd.read_sql(top_10_query, conn)

    if df_top_10.empty:
        return JsonResponse({"error": "Aucun magasin trouvé pour cette catégorie"}, status=404)

    top_mag_ids = tuple(df_top_10["magid"].tolist())

    # Sélectionner le meilleur magasin parmi ces 10
    query_best_seller = f"""
        SELECT magid,
            COUNT(DISTINCT fabid) AS total_fabricants,
            COUNT(DISTINCT prodid) AS total_produits,
            COUNT(*) AS total_ventes,
            -- Calcul du score combiné avec pondération
            (COUNT(DISTINCT prodid) * 0.3 +
            COUNT(*) * 0.6 +
            COUNT(DISTINCT fabid) * 0.1) AS score
        FROM points_de_vente
        WHERE catid = {cat_id} AND magid IN {top_mag_ids}
        GROUP BY magid
        ORDER BY score DESC
        LIMIT 1;
    """
    
    df_best_seller = pd.read_sql(query_best_seller, conn)

    if df_best_seller.empty:
        return JsonResponse({"error": "Aucun meilleur magasin trouvé"}, status=404)

    return JsonResponse(df_best_seller.to_dict(orient="records"), safe=False)

    if type_param == "score-evolution":
        if not cat_id or not fab_id:
            return JsonResponse({"error": "catID et fabID sont requis"}, status=400)

        # Exécuter la requête "score-evolution"
        query_score_evolution = QUERY_MAP["score-evolution"].format(catID=cat_id, fabID=fab_id)
        df_score_evolution = pd.read_sql(query_score_evolution, conn)

        if df_score_evolution.empty:
            return JsonResponse({"error": "Aucune donnée disponible"}, status=404)

        return JsonResponse(df_score_evolution.to_dict(orient="records"), safe=False)


def get_avg_for_fab_of_top_magasin(conn, cat_id, fab_id, df_top_mag):
    # Convertir les magid en tuple pour être utilisé dans la requête SQL
    top_magasins_ID = tuple(df_top_mag["magid"].tolist())
    # Vérifier si la liste est vide
    if not top_magasins_ID:
        return JsonResponse({"error": "Aucun magasin trouvé"}, status=404)
    # Requête SQL pour obtenir les produits par magasin
    query_best_seller = f"""
        SELECT magid, catid,
            COUNT(DISTINCT prodid) AS total_produits
        FROM points_de_vente
        WHERE catid = {cat_id} AND fabid = {fab_id} AND magid IN {top_magasins_ID}
        GROUP BY magid
    """
    df_best_seller = pd.read_sql(query_best_seller, conn)
    # Convertir les résultats en dictionnaire
    best_seller_dict = dict(zip(df_best_seller["magid"], df_best_seller["total_produits"]))
    # Convertir `df_top_mag` en dictionnaire pour un accès plus rapide
    top_mag_dict = dict(zip(df_top_mag["magid"], df_top_mag["total_produits"]))

    top_mag_list = []
    total_percentage = 0.0
    valid_count = 0

    # Parcours de **tous** les magasins de df_top_mag
    for magid, total_produits_top in top_mag_dict.items():
        total_produits_best = best_seller_dict.get(magid, 0)  # 0 si magid n'existe pas dans best_seller_dict

        if total_produits_top != 0:
            percentage = (total_produits_best / total_produits_top) * 100
            total_percentage += percentage
            valid_count += 1
        else:
            percentage = 0.0

        top_mag_list.append({
            "magID": magid,
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


import pandas as pd

def get_avg_for_fab_of_top_magasin2(conn, cat_id, fab_id, df_top_mag):
    # Convertir les magid en tuple pour être utilisé dans la requête SQL
    top_magasins_ID = tuple(df_top_mag["magid"].tolist())
    
    # Vérifier si la liste est vide
    if not top_magasins_ID:
        return JsonResponse({"error": "Aucun magasin trouvé"}, status=404)
    
    # Requête SQL pour obtenir les produits par mois et année pour tous les magasins du top 10
    query_best_seller = f"""
        SELECT strftime('%Y-%m', dateID) AS mois_annee, 
               COUNT(DISTINCT prodid) AS total_produits
        FROM points_de_vente
        WHERE catid = {cat_id} AND fabid = {fab_id} AND magid IN {top_magasins_ID}
        GROUP BY mois_annee
        ORDER BY mois_annee
    """
    
    # Exécution de la requête et récupération des résultats
    df_best_seller = pd.read_sql(query_best_seller, conn)
    
    # Vérifier si le résultat est vide
    if df_best_seller.empty:
        return JsonResponse({"error": "Aucune donnée trouvée pour cette période"}, status=404)

    # Dictionnaire pour stocker les résultats par mois
    mois_annee_dict = {}

    for index, row in df_best_seller.iterrows():
        mois_annee = row['mois_annee']
        total_produits = row['total_produits']
        mois_annee_dict[mois_annee] = total_produits

    # Requête SQL pour obtenir les produits totaux par mois et magasin
    query_total_produits_top_mag = f"""
        SELECT magid, strftime('%Y-%m', dateID) AS mois_annee, 
               COUNT(DISTINCT prodid) AS total_produits
        FROM points_de_vente
        WHERE catid = {cat_id} AND fabid = {fab_id} AND magid IN {top_magasins_ID}
        GROUP BY magid, mois_annee
        ORDER BY mois_annee
    """
    
    # Exécution de la requête et récupération des résultats
    df_total_produits_top_mag = pd.read_sql(query_total_produits_top_mag, conn)
    
    # Dictionnaire pour stocker les produits de chaque magasin par mois
    top_mag_dict = dict(zip(df_top_mag["magid"], df_top_mag["total_produits"]))

    # Liste pour stocker les résultats pour chaque mois
    top_mag_list = []
    total_percentage = 0.0
    valid_count = 0

    # Créer une liste complète des mois pour la période
    mois_list = pd.date_range("2022-01-01", pd.to_datetime("today"), freq="MS").strftime("%Y-%m").tolist()

    # Parcours des mois et calcul des pourcentages
    for mois_annee in mois_list:
        total_percentage_for_month = 0.0
        count_for_month = 0

        # Parcours des magasins
        for magid, total_produits_top in top_mag_dict.items():
            # Filtrer les produits par magasin et mois
            mois_data = df_total_produits_top_mag[df_total_produits_top_mag['magid'] == magid]
            mois_data = mois_data[mois_data['mois_annee'] == mois_annee]
            
            if not mois_data.empty:
                total_produits_best = mois_data['total_produits'].values[0]
                if total_produits_top != 0:
                    percentage = (total_produits_best / total_produits_top) * 100
                    total_percentage_for_month += percentage
                    count_for_month += 1
        
        # Si des magasins ont des données, calculer la moyenne du pourcentage
        if count_for_month > 0:
            avg_percentage_for_month = total_percentage_for_month / count_for_month
            total_percentage += avg_percentage_for_month
            valid_count += 1
        else:
            avg_percentage_for_month = 0.0  # Si aucun magasin n'a de données, on met 0
        
        top_mag_list.append({
            "mois_annee": mois_annee,
            "avg_percentage": avg_percentage_for_month
        })
    
    # Calcul de la moyenne générale uniquement sur les mois valides
    avg_percentage = total_percentage / valid_count if valid_count > 0 else 0.0

    return JsonResponse({
        "average": avg_percentage,
        "top_mag": top_mag_list
    })

