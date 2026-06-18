# 📊 Data Monitor : Pipeline ETL & Business Intelligence

## 🎯 Objectif du Projet
Création d'un pipeline de données complet (Extract, Transform, Load), de la collecte brute jusqu'à la recommandation stratégique. 
L'objectif était d'analyser le positionnement tarifaire et qualitatif d'Intersport face à 6 concurrents majeurs: <br>Zalando, Decathlon, JD Sports, Alltricks, i-Run, Sport 2000. 
<br>Le but final : Transformer un volume massif de données web non structurées en un tableau de bord décisionnel.

## 🛠️ Stack Technique & Outils
* **Extraction (Scraping) :** Python (Playwright, BeautifulSoup4, Pandas, Regex).
* **Nettoyage & Structuration :** Excel (Tableaux Croisés Dynamiques, Tris Matriciels) puis Power Query.
* **Data Visualisation & Modélisation :** Power BI, Langage DAX.

## ⚙️ Architecture du Pipeline (Réalisation End-to-End)

### 1. Extraction Automatisée (Python)
* Développement d'un script `scrapper.py` robuste pour naviguer dynamiquement sur les 7 sites.
* Gestion avancée des comportements asynchrones : scroll dynamique, clics automatisés sur les boutons "Voir plus", gestion des timeouts et contournement des blocages (Headless browser).
* Dédoublonnage sur les clés [Marque + Titre + Source] et filtrage des prix invalides via `Pandas`.
* **Résultat :** Constitution d'une base de données brute de 1 849 références uniques.

### 2. Transformation et Nettoyage (Excel & Power Query)
* **Excel :** Utilisation avancée d'Excel pour le pré-traitement des données. Création de matrices croisées (Catégories X Sources), organisation en onglets de nettoyage et utilisation de Tableaux Croisés Dynamiques (TCD) pour vérifier la volumétrie des stocks et la réparition des cibles (Homme/Femme/Enfant).
* **Power Query :** Structuration de la base de données finale. Traitement des valeurs textuelles aberrantes (conversion des "N/A" en valeurs nulles pour garantir l'intégrité des futurs calculs de moyennes) et typage strict des données (prix en décimal, nombre d'avis en entier).

### 3. Modélisation et Analyse (Power BI & DAX)
* Développement de requêtes **DAX** complexes pour calculer des indicateurs clés de performance (KPI) dynamiques : Taux de rupture de stock, écarts de prix en pourcentage, et prix moyens par catégorie.
* Actualisation automatisée : Le pipeline est conçu pour être vivant. Les tableaux de bord Power BI sont connectés directement à la base de données. Lorsqu'une nouvelle requête de scraping est lancée via Python, la base se met à jour, ce qui actualise automatiquement les indicateurs sur Power BI en temps réel pour refléter l'état actuel du marché.
* Création de 3 tableaux de bord interactifs :
  1. *Analyse des Prix* (Démonstration mathématique d'un avantage tarifaire de -15,05%).
  2. *Qualité & Catalogue* (Analyse des avis clients et des ruptures logistiques).
  3. *Synthèse & Insights Stratégiques* (Génération de 5 recommandations d'aide à la décision).

## 📂 Contenu du Répertoire
* `scrapper.py` : Le code source de l'extracteur Python.
* `donnees_brutes_total.csv` : L'échantillon de la base de données consolidée (1 849 lignes).
* `data_monitor_analyse.xlsx` : Fichier de pré-traitement, de nettoyage matriciel et de Tableaux Croisés Dynamiques (TCD).
* *Note : Les interfaces visuelles du tableau de bord (fichiers `.pbix`) et le rapport détaillé des insights stratégiques sont consultables sur mon portfolio: https://daupindavid.github.io/Ma-Carte-de-Visite/#projects*
