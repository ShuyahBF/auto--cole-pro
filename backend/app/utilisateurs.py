"""Comptes : connexion, profil, changement de mot de passe, gestion des comptes d'une auto-école (création, rôle, agence, activation, réinitialisation)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from . import auth, db, roles, securite, validation
from .auth import exiger_roles, journaliser, utilisateur_courant

routeur = APIRouter()


def _public(u: dict, ecoles: dict | None = None) -> dict:
    """Compte sans secret (jamais de hachage ni de compteur d'échecs)."""
    return {"id": u["id"], "login": u["login"], "nom_affiche": u.get("nom_affiche", ""), "role": u["role"], "role_libelle": roles.LIBELLES.get(u["role"], u["role"]),
            "actif": u.get("actif", True), "doit_changer_mdp": bool(u.get("doit_changer_mdp")), "created_at": u.get("created_at", ""),
            "ecole_id": u.get("ecole_id"), "ecole_nom": (ecoles or {}).get(u.get("ecole_id"), ""), "agence_id": u.get("agence_id")}


@routeur.post("/auth/login")
def login(corps: dict):
    """Connexion. Corps : {login, mot_de_passe}."""
    return auth.connexion(str(corps.get("login", "")), str(corps.get("mot_de_passe", "")))


@routeur.get("/me")
def moi(u: dict = Depends(utilisateur_courant)):
    """Compte connecté et auto-école de travail."""
    return {**u, "role_libelle": roles.LIBELLES.get(u["role"], u["role"])}


@routeur.post("/auth/changer-mot-de-passe")
def changer_mot_de_passe(corps: dict, u: dict = Depends(utilisateur_courant)):
    """Le compte change lui-même son mot de passe (ancien mot de passe exigé)."""
    fiche = db.brut().utilisateurs.find_one({"id": u["id"]})
    if not securite.verifier_mot_de_passe(str(corps.get("ancien", "")), fiche["mot_de_passe_hash"]):
        raise HTTPException(400, "Ancien mot de passe incorrect")
    nouveau = str(corps.get("nouveau", ""))
    if not securite.mot_de_passe_assez_fort(nouveau):
        raise HTTPException(400, "Mot de passe trop faible : 8 caractères au moins, avec une lettre et un chiffre")
    db.brut().utilisateurs.update_one({"id": u["id"]}, {"$set": {"mot_de_passe_hash": securite.hacher_mot_de_passe(nouveau), "doit_changer_mdp": False}})
    journaliser("mot_de_passe_change", u)
    return {"ok": True}


def _roles_autorises(u: dict) -> set:
    """Rôles que ce compte peut créer ou modifier : tous pour le super administrateur, les rôles d'équipe pour un directeur."""
    return set(roles.TOUS_LES_ROLES) if u["role"] == roles.SUPER_ADMIN else set(roles.ROLES_GERES_PAR_DIRECTEUR)


def _agence_valide(corps: dict, role: str) -> str | None:
    """Agence de rattachement (facultative ; obligatoire pour un rôle d'agence n'a pas de sens sans école : vérifiée dans l'école courante)."""
    agence = str(corps.get("agence_id") or "").strip() or None
    if agence and not db.base().agences.find_one({"id": agence}):
        validation.erreur("Agence inconnue dans cette auto-école")
    return agence


def _compte_de_l_ecole(id_: str, u: dict) -> dict:
    """Compte ciblé : doit appartenir à l'école de travail (un compte d'une autre école est « introuvable »), le super administrateur plateforme voit tout."""
    c = db.brut().utilisateurs.find_one({"id": id_})
    if not c or (not u["plateforme"] and c.get("ecole_id") != u["ecole_id"]) or (u["plateforme"] and u["ecole_id"] and c.get("ecole_id") not in (u["ecole_id"], None)):
        raise HTTPException(404, "Compte introuvable")
    return c


@routeur.get("/comptes")
def lister(u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Comptes de l'école de travail (le super administrateur sans école choisie voit tous les comptes)."""
    f = {"ecole_id": u["ecole_id"]} if u["ecole_id"] else {}
    ecoles = {e["id"]: e["nom"] for e in db.brut().ecoles.find({}, {"_id": 0, "id": 1, "nom": 1})}
    return [_public(c, ecoles) for c in db.brut().utilisateurs.find(f).sort("login", 1)]


@routeur.post("/comptes")
def creer(corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Crée un compte dans l'école de travail ; mot de passe provisoire à changer à la première connexion."""
    role = validation.choix(corps, "role", "Rôle", roles.TOUS_LES_ROLES, obligatoire=True)
    if role not in _roles_autorises(u):
        raise HTTPException(403, "Vous ne pouvez pas créer ce rôle")
    login = validation.texte(corps, "login", "Identifiant", True, 40).lower()
    mdp = str(corps.get("mot_de_passe", ""))
    if not securite.mot_de_passe_assez_fort(mdp):
        validation.erreur("Mot de passe provisoire : 8 caractères au moins, avec une lettre et un chiffre")
    if db.brut().utilisateurs.find_one({"login": login}):
        raise HTTPException(409, "Cet identifiant existe déjà")
    ecole_id = None if role == roles.SUPER_ADMIN else u["ecole_id"]
    if role != roles.SUPER_ADMIN and not ecole_id:
        raise HTTPException(400, "Choisissez d'abord une auto-école")
    c = {"id": str(uuid.uuid4()), "login": login, "nom_affiche": validation.texte(corps, "nom_affiche", "Nom", True, 80), "role": role, "actif": True, "echecs": 0,
         "mot_de_passe_hash": securite.hacher_mot_de_passe(mdp), "doit_changer_mdp": True, "created_at": db.maintenant(), "ecole_id": ecole_id,
         "agence_id": _agence_valide(corps, role) if ecole_id else None}
    db.brut().utilisateurs.insert_one(c)
    journaliser("compte_cree", u, f"{login} ({role})")
    return _public(c)


@routeur.put("/comptes/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Modifie nom, rôle, agence, état ; on ne peut ni se désactiver ni changer son propre rôle."""
    c = _compte_de_l_ecole(id_, u)
    if c["role"] not in _roles_autorises(u) and c["id"] != u["id"]:
        raise HTTPException(403, "Vous ne pouvez pas modifier ce compte")
    maj: dict = {}
    if "nom_affiche" in corps:
        maj["nom_affiche"] = validation.texte(corps, "nom_affiche", "Nom", True, 80)
    if "role" in corps and corps["role"] != c["role"]:
        if c["id"] == u["id"]:
            raise HTTPException(409, "Vous ne pouvez pas changer votre propre rôle")
        role = validation.choix(corps, "role", "Rôle", roles.TOUS_LES_ROLES, obligatoire=True)
        if role not in _roles_autorises(u):
            raise HTTPException(403, "Vous ne pouvez pas attribuer ce rôle")
        maj["role"] = role
    if "agence_id" in corps and c.get("ecole_id"):
        maj["agence_id"] = _agence_valide(corps, c["role"])
    if "actif" in corps and bool(corps["actif"]) != c.get("actif", True):
        if c["id"] == u["id"]:
            raise HTTPException(409, "Vous ne pouvez pas désactiver votre propre compte")
        maj["actif"] = bool(corps["actif"])
    if maj:
        db.brut().utilisateurs.update_one({"id": id_}, {"$set": maj})
        journaliser("compte_modifie", u, f"{c['login']} : {', '.join(sorted(maj))}")
    return _public(db.brut().utilisateurs.find_one({"id": id_}))


@routeur.post("/comptes/{id_}/reinitialiser")
def reinitialiser(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Nouveau mot de passe provisoire (à changer à la première connexion) ; lève un éventuel blocage."""
    c = _compte_de_l_ecole(id_, u)
    if c["role"] not in _roles_autorises(u):
        raise HTTPException(403, "Vous ne pouvez pas modifier ce compte")
    mdp = str(corps.get("mot_de_passe", ""))
    if not securite.mot_de_passe_assez_fort(mdp):
        validation.erreur("Mot de passe provisoire : 8 caractères au moins, avec une lettre et un chiffre")
    db.brut().utilisateurs.update_one({"id": id_}, {"$set": {"mot_de_passe_hash": securite.hacher_mot_de_passe(mdp), "doit_changer_mdp": True, "echecs": 0, "bloque_jusqua": None}})
    journaliser("mot_de_passe_reinitialise", u, c["login"])
    return {"ok": True}


@routeur.get("/journal")
def journal(limite: int = 200, u: dict = Depends(exiger_roles(roles.LECTURE_JOURNAL))):
    """Dernières lignes du journal d'audit de l'école de travail (qui, quoi, quand)."""
    f = {"ecole_id": u["ecole_id"]} if u["ecole_id"] else {}
    return [{k: v for k, v in j.items() if k != "_id"} for j in db.brut().journal.find(f).sort("quand", -1).limit(max(1, min(limite, 500)))]
