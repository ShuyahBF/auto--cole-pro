"""
Accès à MongoDB, multi-auto-écoles. La base est ouverte à la première utilisation (Atlas) ou injectée par les tests (base en mémoire).

MULTI-ÉCOLES (modèle éprouvé sur Dialyse) : l'auto-école « courante » est posée UNE FOIS par requête (auth.utilisateur_courant) dans une variable de contexte. Toute collection
listée dans COLLECTIONS_ECOLE est alors filtrée AUTOMATIQUEMENT sur cette école (lecture, modification, suppression) et marquée `ecole_id` à l'écriture : un écran ne peut pas
« oublier » de filtrer, et sans école courante l'accès est REFUSÉ (jamais « tout »). `brut()` (sans filtre) est réservé à la migration, aux listes d'écoles et aux contrôles
de plateforme : toute nouvelle utilisation doit avoir une raison écrite.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone

from .config import env

_base = None

# Collections dont chaque document appartient à UNE auto-école (le reste : comptes, écoles, journal… sont gérés à part).
COLLECTIONS_ECOLE = {"agences", "tarifs", "promotions", "eleves", "paiements", "compteurs",
                     "seances_conduite", "sessions_examen", "inscriptions_examen", "examens_internes", "transferts",
                     "vehicules", "releves_km", "pleins", "pannes", "interventions", "pieces", "mouvements_pieces", "fournisseurs", "commandes",
                     "contacts", "wa_messages", "wa_modeles", "avis", "demandes_avis"}
ecole_courante: ContextVar = ContextVar("ecole_courante", default=None)


def fixer_ecole(ecole_id) -> None:
    """Définit l'auto-école de travail de la requête en cours (None = aucune)."""
    ecole_courante.set(ecole_id)


def _ecole_ou_erreur() -> str:
    """École courante, ou erreur 400 « choisissez une auto-école » (le super administrateur doit en choisir une)."""
    e = ecole_courante.get()
    if not e:
        from fastapi import HTTPException
        raise HTTPException(400, "Choisissez d'abord une auto-école")
    return e


def _filtre(filtre) -> dict:
    """Filtre d'origine + condition école (la condition de l'école l'emporte toujours sur celle d'un appelant)."""
    return {**(filtre or {}), "ecole_id": _ecole_ou_erreur()}


class CollectionEcole:
    """Collection MongoDB limitée à l'auto-école courante. Seules les opérations sûres sont exposées (pas d'accès direct à la collection brute)."""

    def __init__(self, brute):
        self._c = brute

    def find(self, filtre=None, *a, **k):
        return self._c.find(_filtre(filtre), *a, **k)

    def find_one(self, filtre=None, *a, **k):
        return self._c.find_one(_filtre(filtre), *a, **k)

    def count_documents(self, filtre=None, *a, **k):
        return self._c.count_documents(_filtre(filtre), *a, **k)

    def distinct(self, cle, filtre=None, *a, **k):
        return self._c.distinct(cle, _filtre(filtre), *a, **k)

    def insert_one(self, doc, *a, **k):
        return self._c.insert_one({**doc, "ecole_id": _ecole_ou_erreur()}, *a, **k)

    def insert_many(self, docs, *a, **k):
        e = _ecole_ou_erreur()
        return self._c.insert_many([{**d, "ecole_id": e} for d in docs], *a, **k)

    def update_one(self, filtre, maj, *a, **k):
        return self._c.update_one(_filtre(filtre), maj, *a, **k)

    def update_many(self, filtre, maj, *a, **k):
        return self._c.update_many(_filtre(filtre), maj, *a, **k)

    def replace_one(self, filtre, doc, *a, **k):
        return self._c.replace_one(_filtre(filtre), {**doc, "ecole_id": _ecole_ou_erreur()}, *a, **k)

    def delete_one(self, filtre, *a, **k):
        return self._c.delete_one(_filtre(filtre), *a, **k)

    def delete_many(self, filtre, *a, **k):
        return self._c.delete_many(_filtre(filtre), *a, **k)

    def find_one_and_update(self, filtre, maj, *a, **k):
        return self._c.find_one_and_update(_filtre(filtre), maj, *a, **k)

    def aggregate(self, pipeline, *a, **k):
        return self._c.aggregate([{"$match": {"ecole_id": _ecole_ou_erreur()}}, *pipeline], *a, **k)


class BaseEcole:
    """Base « vue de l'école courante » : les collections de COLLECTIONS_ECOLE sont filtrées, les autres sont brutes."""

    def __init__(self, brute):
        self._b = brute

    def __getattr__(self, nom):
        if nom.startswith("_"):
            raise AttributeError(nom)
        return self[nom]

    def __getitem__(self, nom):
        return CollectionEcole(self._b[nom]) if nom in COLLECTIONS_ECOLE else self._b[nom]

    def command(self, *a, **k):
        return self._b.command(*a, **k)


def definir_base(base) -> None:
    """Utilisé par les tests pour fournir une base en mémoire."""
    global _base
    _base = base


def base():
    """Base de travail VUE DE L'ÉCOLE COURANTE (collections par école filtrées automatiquement). Pour toutes les écoles : `brut()`."""
    return BaseEcole(brut())


def brut():
    """Base complète, SANS filtre d'école (migration, liste des écoles, contrôles de plateforme). À n'utiliser que là, avec une raison claire."""
    global _base
    if _base is None:
        from pymongo import MongoClient
        uri = env("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI absent : à définir dans les variables d'environnement.")
        _base = MongoClient(uri, serverSelectionTimeoutMS=8000)[env("MONGODB_BASE", "autoecole")]
        creer_index(_base)
    return _base


def maintenant() -> str:
    """Date et heure UTC au format ISO (celle que l'on range en base)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def numero_suivant(cle: str) -> int:
    """Prochain numéro d'un compteur de l'école courante (matricules, reçus…) : incrément ATOMIQUE, deux saisies simultanées n'obtiennent jamais le même numéro."""
    r = base().compteurs.find_one_and_update({"cle": cle}, {"$inc": {"n": 1}}, upsert=True, return_document=True)
    return int(r["n"])


def creer_index(b) -> None:
    """Index sur tout filtre fréquent (règle 7) : jamais de parcours complet d'une collection."""
    b.utilisateurs.create_index("login", unique=True)
    b.utilisateurs.create_index("id", unique=True)
    b.utilisateurs.create_index("ecole_id")
    b.journal.create_index([("quand", -1)])
    b.journal.create_index([("ecole_id", 1), ("quand", -1)])
    b.ecoles.create_index("id", unique=True)
    b.ecoles.create_index("prefixe", unique=True)
    b.agences.create_index([("ecole_id", 1), ("id", 1)], unique=True)
    b.compteurs.create_index([("ecole_id", 1), ("cle", 1)], unique=True)
    b.tarifs.create_index([("ecole_id", 1), ("code", 1)], unique=True)
    b.promotions.create_index([("ecole_id", 1), ("code", 1)], unique=True)
    b.eleves.create_index([("ecole_id", 1), ("id", 1)], unique=True)
    b.eleves.create_index([("ecole_id", 1), ("matricule", 1)], unique=True)
    b.eleves.create_index([("ecole_id", 1), ("statut", 1), ("agence_id", 1)])
    b.eleves.create_index([("ecole_id", 1), ("nom_norm", 1), ("prenom_norm", 1)])
    b.paiements.create_index([("ecole_id", 1), ("eleve_id", 1), ("date", -1)])
    b.paiements.create_index([("ecole_id", 1), ("date", -1)])
    b.paiements.create_index([("ecole_id", 1), ("recu", 1)], unique=True)
    # Lot 2 : examens, transferts, séances de conduite
    b.sessions_examen.create_index([("ecole_id", 1), ("date", 1)])
    b.sessions_examen.create_index([("ecole_id", 1), ("id", 1)], unique=True)
    b.inscriptions_examen.create_index([("ecole_id", 1), ("session_id", 1)])
    b.inscriptions_examen.create_index([("ecole_id", 1), ("eleve_id", 1)])
    b.transferts.create_index([("ecole_id", 1), ("eleve_id", 1)])
    b.seances_conduite.create_index([("ecole_id", 1), ("eleve_id", 1), ("date", -1)])
    b.seances_conduite.create_index([("ecole_id", 1), ("date", -1)])
    # Lot 3 : parc automobile
    b.vehicules.create_index([("ecole_id", 1), ("immatriculation", 1)], unique=True)
    b.vehicules.create_index([("ecole_id", 1), ("id", 1)], unique=True)
    for c in (b.releves_km, b.pleins, b.pannes, b.interventions):
        c.create_index([("ecole_id", 1), ("vehicule_id", 1), ("date", -1)])
    b.pieces.create_index([("ecole_id", 1), ("reference", 1)], unique=True)
    b.mouvements_pieces.create_index([("ecole_id", 1), ("piece_id", 1), ("date", -1)])
    b.fournisseurs.create_index([("ecole_id", 1), ("nom", 1)])
    b.commandes.create_index([("ecole_id", 1), ("numero", 1)], unique=True)
    # Lot 4 : messagerie WhatsApp et évaluations
    b.contacts.create_index([("ecole_id", 1), ("numero", 1)])
    b.contacts.create_index([("ecole_id", 1), ("id", 1)], unique=True)
    b.wa_messages.create_index([("ecole_id", 1), ("contact_id", 1), ("cree_le", 1)])
    b.wa_messages.create_index("id", unique=True)
    b.wa_modeles.create_index([("ecole_id", 1), ("nom", 1)], unique=True)
    b.demandes_avis.create_index("empreinte", unique=True)
    b.demandes_avis.create_index([("ecole_id", 1), ("eleve_id", 1), ("cree_le", -1)])
    b.avis.create_index([("ecole_id", 1), ("cree_le", -1)])
    b.avis.create_index("demande_id", unique=True)
