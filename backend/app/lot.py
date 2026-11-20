"""
SOURCE UNIQUE de la version et du lot du serveur (règles du propriétaire n° 1 et 2).
À CHAQUE déploiement : augmenter VERSION (compteur « 1.N ») et mettre LOT = numéro de la PR fusionnée.
Modifier ce fichier force aussi le redéploiement sur Render (le service a un rootDir « backend »).
"""
VERSION = "1.0"
LOT = "1"
LOT_LIBELLE = "Fondation : auto-écoles et agences, comptes et rôles, tarifs et promotions, inscriptions des élèves, paiements et reçus, tableau de bord."
