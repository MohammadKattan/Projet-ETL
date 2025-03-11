import pandas as pd
import sqlite3

# 📌 Lire les fichiers CSV avec gestion des espaces
df_produits = pd.read_csv("data/produits-tous.csv", delimiter=r"\s+", engine="python")
df_points_vente = pd.read_csv("data/pointsDeVente-tous.csv", delimiter=r"\s+", engine="python")

# 📌 Normaliser les noms de colonnes (minuscules pour éviter les erreurs)
df_produits.columns = df_produits.columns.str.lower()
df_points_vente.columns = df_points_vente.columns.str.lower()

# 📌 Conversion de la date au format DATE pour SQLite
df_produits["dateid"] = pd.to_datetime(df_produits["dateid"], format="%Y%m%d").dt.date
df_points_vente["dateid"] = pd.to_datetime(df_points_vente["dateid"], format="%Y%m%d").dt.date

# 📌 Connexion à la base SQLite
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# 📌 Création des tables dans SQLite
cursor.execute("""
CREATE TABLE IF NOT EXISTS produits (
    dateid DATE,
    prodid INTEGER,
    catid INTEGER,
    fabid INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS points_de_vente (
    dateid DATE,
    prodid INTEGER,
    catid INTEGER,
    fabid INTEGER,
    magid INTEGER
)
""")

# 📌 Insertion des données dans SQLite
df_produits.to_sql("produits", conn, if_exists="replace", index=False)
df_points_vente.to_sql("points_de_vente", conn, if_exists="replace", index=False)

# 📌 Validation et fermeture de la connexion
conn.commit()
conn.close()

print("✅ Données importées avec succès dans SQLite !")
