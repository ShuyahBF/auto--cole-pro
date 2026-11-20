"""
Rôles et permissions d'AutoÉcole Pro. Liste finie de rôles = liste déroulante dans l'interface (règle 10).

Principe : chaque compte appartient à UNE auto-école (jamais plusieurs) ; le super administrateur de la plateforme (propriétaire) est le seul à n'en dépendre d'aucune
et choisit l'auto-école où il travaille (en-tête X-Ecole). Un compte peut en plus être limité à UNE agence : il ne voit alors que les élèves de son agence.
Les données financières (paiements, soldes, coûts du parc) ne sont vues que des rôles qui en ont besoin ; le moniteur ne voit que ses élèves et son planning.
"""

SUPER_ADMIN = "super_admin"       # propriétaire de la plateforme : crée les auto-écoles, voit tout
DIRECTEUR = "directeur"           # dirigeant d'une auto-école : tout dans son école (comptes, tarifs, paramètres, statistiques)
GESTIONNAIRE = "gestionnaire"     # responsable d'agence : élèves, examens, parc de son agence
SECRETAIRE = "secretaire"         # accueil et caisse : inscriptions, paiements, convocations
COMPTABLE = "comptable"           # finances : paiements, impayés, états (lecture des dossiers)
MONITEUR = "moniteur"             # enseignant : ses élèves, son planning, ses évaluations
MECANICIEN = "mecanicien"         # parc automobile : véhicules, pannes, interventions, pièces

TOUS_LES_ROLES = [SUPER_ADMIN, DIRECTEUR, GESTIONNAIRE, SECRETAIRE, COMPTABLE, MONITEUR, MECANICIEN]
LIBELLES = {SUPER_ADMIN: "Super administrateur", DIRECTEUR: "Directeur", GESTIONNAIRE: "Responsable d'agence", SECRETAIRE: "Secrétaire",
            COMPTABLE: "Comptable", MONITEUR: "Moniteur", MECANICIEN: "Mécanicien"}

ADMINISTRATION = {DIRECTEUR, SUPER_ADMIN}
GESTION = {GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
# Rôles qu'un DIRECTEUR peut créer ou modifier (jamais un autre directeur ni le super administrateur).
ROLES_GERES_PAR_DIRECTEUR = {GESTIONNAIRE, SECRETAIRE, COMPTABLE, MONITEUR, MECANICIEN}
# Seul compte à ne dépendre d'AUCUNE auto-école : il choisit celle où il travaille (en-tête X-Ecole).
ROLES_PLATEFORME = {SUPER_ADMIN}
# Rôles qu'on peut limiter à une agence.
ROLES_D_AGENCE = {GESTIONNAIRE, SECRETAIRE, MONITEUR, MECANICIEN}

# Élèves : lecture large (le moniteur ne voit que ses élèves, voir eleves.py) ; écriture par l'accueil et la gestion.
LECTURE_ELEVE = {SECRETAIRE, COMPTABLE, MONITEUR, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ECRITURE_ELEVE = {SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
# Finances : encaissement par l'accueil et la comptabilité ; annulation d'un paiement et paramétrage des tarifs : gestion / administration.
LECTURE_FINANCE = {SECRETAIRE, COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ENCAISSEMENT = {SECRETAIRE, COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ANNULATION_PAIEMENT = {COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
# Tarifs : lecture par tous les rôles d'accueil ; écriture par la gestion.
LECTURE_TARIF = {SECRETAIRE, COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN, MONITEUR}
ECRITURE_TARIF = GESTION
# Tableau de bord et statistiques : encadrement et comptabilité.
LECTURE_STATS = {COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
LECTURE_JOURNAL = ADMINISTRATION

# --- Lot 2 : examens, transferts, séances de conduite ---
LECTURE_EXAMEN = {SECRETAIRE, COMPTABLE, MONITEUR, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ECRITURE_EXAMEN = {SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ECRITURE_SEANCE = {MONITEUR, SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
TRANSFERT = {GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}

# --- Lot 3 : parc automobile ---
LECTURE_PARC = {MECANICIEN, MONITEUR, SECRETAIRE, COMPTABLE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
ECRITURE_PARC = {MECANICIEN, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}            # fiches véhicules, pannes, interventions, pièces, commandes
SAISIE_TERRAIN = {MONITEUR, MECANICIEN, SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}   # kilométrage, pleins de carburant, signalement de panne
COUTS_PARC = {COMPTABLE, MECANICIEN, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}    # montants (carburant, pièces, interventions) : jamais le moniteur ni le secrétariat

# --- Lot 4 : messagerie et évaluations ---
MESSAGERIE = {SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
LECTURE_AVIS = {SECRETAIRE, GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN, COMPTABLE}
GESTION_AVIS = {GESTIONNAIRE, DIRECTEUR, SUPER_ADMIN}
