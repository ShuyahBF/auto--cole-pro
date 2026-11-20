"""
TARIFS (forfaits de formation par catégorie de permis) et PROMOTIONS (remises à durée limitée).
Montants dans la devise de l'auto-école (décimales selon la devise : 0 pour le FCFA). Un tarif utilisé par des élèves ne se supprime pas : on le DÉSACTIVE ;
le prix, le libellé et la remise sont COPIÉS sur le dossier à l'inscription (changer un tarif ne modifie jamais un dossier existant).
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, validation
from .auth import exiger_roles, journaliser, utilisateur_courant

routeur = APIRouter()


def decimales_ecole() -> int:
    """Nombre de décimales de la devise de l'école de travail."""
    e = db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}
    return int(e.get("decimales", 0))


def arrondi(x: float) -> float:
    """Arrondit un montant aux décimales de la devise (entier pour le FCFA)."""
    d = decimales_ecole()
    return int(round(x)) if d == 0 else round(x, d)


def _montant(corps: dict, cle: str, libelle: str, obligatoire: bool = True):
    n = validation.nombre(corps, cle, libelle, 0, 1_000_000_000)
    if n is None:
        if obligatoire:
            validation.erreur(f"{libelle} : montant obligatoire")
        return None
    return arrondi(n)


def _code(corps: dict, libelle: str) -> str:
    c = re.sub(r"[^A-Z0-9_-]", "", validation.texte(corps, "code", libelle, True, 20).upper().replace(" ", "-"))
    if not c:
        validation.erreur(f"{libelle} : lettres, chiffres, tiret")
    return c


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


# ---------- tarifs ----------

@routeur.get("/tarifs")
def lister(u: dict = Depends(exiger_roles(roles.LECTURE_TARIF))):
    """Tarifs de l'école (actifs d'abord, puis par catégorie)."""
    return [_public(t) for t in db.base().tarifs.find({}, {"_id": 0}).sort([("actif", -1), ("categorie", 1), ("libelle", 1)])]


def _lire_tarif(corps: dict) -> dict:
    ecole = db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}
    cats = {c["code"] for c in ecole.get("categories", [])}
    categorie = validation.choix(corps, "categorie", "Catégorie de permis", cats, obligatoire=True)
    return {"libelle": validation.texte(corps, "libelle", "Libellé", True, 80), "categorie": categorie, "prix": _montant(corps, "prix", "Prix"),
            "heures_conduite": int(validation.nombre(corps, "heures_conduite", "Heures de conduite", 0, 500) or 0),
            "seances_code": int(validation.nombre(corps, "seances_code", "Séances de code", 0, 500) or 0),
            "description": validation.texte(corps, "description", "Description", False, 300),
            "acompte_minimum": _montant(corps, "acompte_minimum", "Acompte minimum", False) or 0}


@routeur.post("/tarifs")
def creer(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_TARIF))):
    """Nouveau forfait."""
    t = {"id": str(uuid.uuid4()), "code": _code(corps, "Code"), "actif": True, "cree_le": db.maintenant(), **_lire_tarif(corps)}
    if db.base().tarifs.find_one({"code": t["code"]}):
        raise HTTPException(409, "Ce code de tarif existe déjà")
    if t["acompte_minimum"] > t["prix"]:
        validation.erreur("L'acompte minimum ne peut pas dépasser le prix")
    db.base().tarifs.insert_one(t)
    journaliser("tarif_cree", u, f"{t['code']} {t['prix']}")
    return _public(t)


@routeur.put("/tarifs/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_TARIF))):
    """Modifie un forfait (les dossiers déjà inscrits gardent leur prix) ; le désactive ou le réactive."""
    t = db.base().tarifs.find_one({"id": id_})
    if not t:
        raise HTTPException(404, "Tarif introuvable")
    maj = _lire_tarif({**t, **corps})
    if maj["acompte_minimum"] > maj["prix"]:
        validation.erreur("L'acompte minimum ne peut pas dépasser le prix")
    if "actif" in corps:
        maj["actif"] = bool(corps["actif"])
    db.base().tarifs.update_one({"id": id_}, {"$set": maj})
    journaliser("tarif_modifie", u, t["code"])
    return _public(db.base().tarifs.find_one({"id": id_}))


@routeur.delete("/tarifs/{id_}")
def supprimer(id_: str, u: dict = Depends(exiger_roles(roles.ECRITURE_TARIF))):
    """Supprime un tarif jamais utilisé ; sinon refuse (on le désactive)."""
    t = db.base().tarifs.find_one({"id": id_})
    if not t:
        raise HTTPException(404, "Tarif introuvable")
    if db.base().eleves.count_documents({"tarif_id": id_}, limit=1):
        raise HTTPException(409, "Des élèves utilisent ce tarif : désactivez-le plutôt que de le supprimer")
    db.base().tarifs.delete_one({"id": id_})
    journaliser("tarif_supprime", u, t["code"])
    return {"ok": True}


# ---------- promotions ----------

def promotion_valide(code: str, aujourdhui: str | None = None) -> dict | None:
    """Promotion active dont la période couvre aujourd'hui (None sinon)."""
    p = db.base().promotions.find_one({"code": str(code or "").strip().upper(), "actif": True})
    j = aujourdhui or date.today().isoformat()
    if not p or (p.get("debut") and j < p["debut"]) or (p.get("fin") and j > p["fin"]):
        return None
    return p


def remise_pour(prix: float, promo: dict | None) -> float:
    """Remise (en devise) d'une promotion sur un prix ; jamais au-delà du prix."""
    if not promo:
        return 0
    r = prix * promo["valeur"] / 100 if promo["type"] == "pourcentage" else promo["valeur"]
    return arrondi(min(prix, r))


@routeur.get("/promotions")
def lister_promotions(u: dict = Depends(exiger_roles(roles.LECTURE_TARIF))):
    """Promotions de l'école avec leur état (en cours, à venir, terminée, inactive)."""
    j = date.today().isoformat()
    out = []
    for p in db.base().promotions.find({}, {"_id": 0}).sort("code", 1):
        etat = "inactive" if not p.get("actif") else "a_venir" if p.get("debut") and j < p["debut"] else "terminee" if p.get("fin") and j > p["fin"] else "en_cours"
        out.append({**_public(p), "etat": etat})
    return out


@routeur.post("/promotions")
def creer_promotion(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_TARIF))):
    """Nouvelle promotion : pourcentage (1 à 100) ou montant fixe, période facultative."""
    typ = validation.choix(corps, "type", "Type de remise", ["pourcentage", "montant"], obligatoire=True)
    valeur = validation.nombre(corps, "valeur", "Valeur", 0.01, 100 if typ == "pourcentage" else 1_000_000_000)
    if valeur is None:
        validation.erreur("Valeur : obligatoire")
    debut, fin = validation.date_iso(corps, "debut", "Début"), validation.date_iso(corps, "fin", "Fin")
    if debut and fin and fin < debut:
        validation.erreur("La fin ne peut pas précéder le début")
    p = {"id": str(uuid.uuid4()), "code": _code(corps, "Code"), "libelle": validation.texte(corps, "libelle", "Libellé", True, 80), "type": typ,
         "valeur": valeur if typ == "pourcentage" else arrondi(valeur), "debut": debut, "fin": fin, "actif": True, "cree_le": db.maintenant()}
    if db.base().promotions.find_one({"code": p["code"]}):
        raise HTTPException(409, "Ce code de promotion existe déjà")
    db.base().promotions.insert_one(p)
    journaliser("promotion_creee", u, p["code"])
    return _public(p)


@routeur.put("/promotions/{id_}")
def modifier_promotion(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_TARIF))):
    """Active / désactive ou modifie la période et le libellé (le type et la valeur ne changent plus : créez une autre promotion)."""
    p = db.base().promotions.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Promotion introuvable")
    maj = {}
    if "libelle" in corps:
        maj["libelle"] = validation.texte(corps, "libelle", "Libellé", True, 80)
    for cle, lib in (("debut", "Début"), ("fin", "Fin")):
        if cle in corps:
            maj[cle] = validation.date_iso(corps, cle, lib)
    if "actif" in corps:
        maj["actif"] = bool(corps["actif"])
    d, f = maj.get("debut", p.get("debut")), maj.get("fin", p.get("fin"))
    if d and f and f < d:
        validation.erreur("La fin ne peut pas précéder le début")
    if maj:
        db.base().promotions.update_one({"id": id_}, {"$set": maj})
        journaliser("promotion_modifiee", u, p["code"])
    return _public(db.base().promotions.find_one({"id": id_}))
