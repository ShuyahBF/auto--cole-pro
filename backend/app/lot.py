"""
SOURCE UNIQUE de la version et du lot du serveur (règles du propriétaire n° 1 et 2).
À CHAQUE déploiement : augmenter VERSION (compteur « 1.N ») et mettre LOT = numéro de la PR fusionnée.
Modifier ce fichier force aussi le redéploiement sur Render (le service a un rootDir « backend »).
"""
VERSION = "1.1"
LOT = "5"
LOT_LIBELLE = "Intitulés des entités en majuscules, champs obligatoires marqués d'une étoile et signalés en rouge à la validation."
