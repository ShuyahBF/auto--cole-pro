"""
Configuration lue UNIQUEMENT dans les variables d'environnement (jamais de secret dans le code). Sur Render : onglet « Environment » du service.

  MONGODB_URI              chaîne de connexion Atlas (secret, saisie par le propriétaire)
  MONGODB_BASE             nom de la base (défaut « autoecole »)
  JWT_SECRET               longue phrase secrète aléatoire (secret)
  SUPERADMIN_LOGIN         identifiant du premier super administrateur de la plateforme (créé au 1er démarrage)
  SUPERADMIN_MOT_DE_PASSE  son mot de passe initial (secret ; à changer à la 1re connexion)
  LILUVINE_WA_URL / LILUVINE_WA_HMAC / LILUVINE_WA_EMETTEUR  WhatsApp par la « Transmission universelle » de SAWALI (la clé HMAC est un secret)
  FRONTEND_ORIGIN          adresse(s) du site web (CORS), séparées par des virgules
  PRESENCE_SAWALI          « 0 » pour désactiver le signal de présence (tests)
  TACHES_DE_FOND           « 0 » pour désactiver les tâches planifiées (tests)
"""
import os


def env(nom: str, defaut: str = "") -> str:
    """Valeur d'une variable d'environnement (chaîne vide si absente)."""
    return os.environ.get(nom, defaut)


DUREE_JETON_HEURES = 10          # un jeton de connexion vaut 10 heures (une journée de travail)
TENTATIVES_MAX = 5               # 5 mots de passe faux de suite = compte bloqué un moment
BLOCAGE_MINUTES = 15             # durée du blocage


def origines_site() -> list[str]:
    """Adresses autorisées du site web (FRONTEND_ORIGIN, séparées par des virgules), sans « / » final."""
    return [o.strip().rstrip("/") for o in env("FRONTEND_ORIGIN").split(",") if o.strip()]
