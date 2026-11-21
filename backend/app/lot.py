"""
SOURCE UNIQUE de la version et du lot du serveur (règles du propriétaire n° 1 et 2).
À CHAQUE déploiement : augmenter VERSION (compteur « 1.N ») et mettre LOT = numéro de la PR fusionnée.
Modifier ce fichier force aussi le redéploiement sur Render (le service a un rootDir « backend »).
"""
VERSION = "1.3"
LOT = "7"
LOT_LIBELLE = "Bandeau « Une nouvelle version est disponible » avec Actualiser (vérification toutes les 5 minutes)."
