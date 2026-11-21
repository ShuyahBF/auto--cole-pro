"""
SOURCE UNIQUE de la version et du lot du serveur (règles du propriétaire n° 1 et 2).
À CHAQUE déploiement : augmenter VERSION (compteur « 1.N ») et mettre LOT = numéro de la PR fusionnée.
Modifier ce fichier force aussi le redéploiement sur Render (le service a un rootDir « backend »).
"""
VERSION = "1.2"
LOT = "6"
LOT_LIBELLE = "Champs clés (nom de l'auto-école, codes, références, immatriculations) en majuscules ; noms ordinaires (agences) avec une 1re lettre majuscule."
