"""Authentification : connexion, jeton, utilisateur courant (avec son auto-école), blocage après échecs répétés, journal d'audit."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from . import db, roles, securite
from .config import BLOCAGE_MINUTES, TENTATIVES_MAX


def journaliser(action: str, acteur: dict | None, detail: str = "") -> None:
    """Ajoute une ligne au journal (qui, quoi, quand). Jamais de mot de passe ni de donnée sensible : seulement des références."""
    a = acteur or {}
    db.brut().journal.insert_one({"quand": db.maintenant(), "action": action, "acteur_id": a.get("id"), "acteur": a.get("login"), "role": a.get("role"),
                                  "detail": detail[:300], "ecole_id": a.get("ecole_id") or db.ecole_courante.get()})


def _lire_utilisateur(authorization: str, x_ecole: str) -> dict:
    """Partie bloquante (base de données) de `utilisateur_courant` : jeton, compte, auto-école de travail."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Connexion requise")
    contenu = securite.lire_jeton(authorization[7:].strip())
    if not contenu:
        raise HTTPException(401, "Session expirée, reconnectez-vous")
    u = db.brut().utilisateurs.find_one({"id": contenu["sub"]})
    if not u or not u.get("actif", True):
        raise HTTPException(401, "Compte inconnu ou désactivé")
    # --- Auto-école de travail ---
    # Un compte rattaché à une école travaille TOUJOURS dans la sienne (l'en-tête X-Ecole est ignoré : aucun passage d'une école à l'autre).
    # Le super administrateur de la plateforme (sans école) choisit la sienne par X-Ecole ; sans choix, aucune donnée d'école n'est accessible.
    ecole_id = u.get("ecole_id") or None
    plateforme = u["role"] in roles.ROLES_PLATEFORME and not ecole_id
    if plateforme and x_ecole.strip():
        ecole_id = x_ecole.strip()
    ecole = db.brut().ecoles.find_one({"id": ecole_id}) if ecole_id else None
    if ecole_id and not ecole:
        raise HTTPException(400 if plateforme else 403, "Auto-école inconnue")
    if ecole and not ecole.get("actif", True) and u["role"] != roles.SUPER_ADMIN:
        raise HTTPException(403, "Cette auto-école est désactivée")
    # Le rôle vient de la base (pas du jeton) : un changement de rôle ou une désactivation est immédiat.
    return {"id": u["id"], "login": u["login"], "nom": u.get("nom_affiche", u["login"]), "role": u["role"], "doit_changer_mdp": bool(u.get("doit_changer_mdp")),
            "ecole_id": ecole["id"] if ecole else None, "ecole_nom": ecole["nom"] if ecole else "", "ecole_prefixe": ecole["prefixe"] if ecole else "",
            "agence_id": u.get("agence_id") or None, "plateforme": plateforme}


async def utilisateur_courant(authorization: str = Header(default=""), x_ecole: str = Header(default="")) -> dict:
    """
    Utilisateur déduit du jeton « Bearer … » (401 si invalide) ET fixation de l'auto-école de travail de la requête. Dépendance ASYNCHRONE exprès : la variable de contexte
    de l'école est posée dans la tâche de la requête, donc visible de la fonction de route (exécutée ensuite dans un fil de calcul qui en reçoit une copie).
    """
    u = await run_in_threadpool(_lire_utilisateur, authorization, x_ecole)
    db.fixer_ecole(u["ecole_id"])
    return u


def exiger_roles(*roles_):
    """Dépendance FastAPI : refuse (403) tout rôle hors de la liste."""
    autorises = set()
    for r in roles_:
        autorises |= set(r) if isinstance(r, (set, frozenset, list, tuple)) else {r}

    def verif(u: dict = Depends(utilisateur_courant)) -> dict:
        if u["role"] not in autorises:
            raise HTTPException(403, "Droits insuffisants")
        return u
    return verif


def _compter_echec(u: dict, maintenant: datetime) -> None:
    """Un échec de plus ; au-delà de TENTATIVES_MAX de suite, le compte est bloqué BLOCAGE_MINUTES minutes."""
    n = u.get("echecs", 0) + 1
    maj = {"echecs": n}
    if n >= TENTATIVES_MAX:
        maj = {"echecs": 0, "bloque_jusqua": (maintenant + timedelta(minutes=BLOCAGE_MINUTES)).isoformat()}
    db.brut().utilisateurs.update_one({"id": u["id"]}, {"$set": maj})


def verifier_non_bloque(u: dict | None) -> None:
    """429 si le compte est bloqué temporairement après trop d'essais."""
    if u and u.get("bloque_jusqua") and datetime.now(timezone.utc) < datetime.fromisoformat(u["bloque_jusqua"]):
        raise HTTPException(429, f"Compte bloqué {BLOCAGE_MINUTES} minutes après trop d'essais")


def echec_acces(u: dict, detail: str) -> None:
    """Échec d'un moyen d'accès (ex. retrait de la liaison Google avec un mauvais mot de passe) : compté et journalisé comme un mot de passe faux."""
    _compter_echec(u, datetime.now(timezone.utc))
    journaliser("connexion_refusee", {"id": u["id"], "login": u["login"], "role": u["role"], "ecole_id": u.get("ecole_id")}, detail)


def connexion(login: str, mot_de_passe: str) -> dict:
    """Vérifie les identifiants ; blocage temporaire après TENTATIVES_MAX échecs de suite ; même réponse que le compte existe ou non."""
    u = db.brut().utilisateurs.find_one({"login": login.strip().lower()})
    verifier_non_bloque(u)
    acteur = {"id": (u or {}).get("id"), "login": login.strip().lower(), "role": (u or {}).get("role"), "ecole_id": (u or {}).get("ecole_id")}
    if not u or not u.get("actif", True) or not securite.verifier_mot_de_passe(mot_de_passe, u["mot_de_passe_hash"]):
        if u:
            _compter_echec(u, datetime.now(timezone.utc))
            journaliser("connexion_refusee", acteur, "")
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    return ouvrir_session(u)


def ouvrir_session(u: dict, moyen: str = "") -> dict:
    """Étape commune à tous les moyens d'accès (mot de passe, Google) une fois la personne reconnue : remise à zéro des échecs, journal, jeton."""
    db.brut().utilisateurs.update_one({"id": u["id"]}, {"$set": {"echecs": 0, "bloque_jusqua": None}})
    journaliser("connexion", {"id": u["id"], "login": u["login"], "role": u["role"], "ecole_id": u.get("ecole_id")}, moyen)
    return {"jeton": securite.creer_jeton(u["id"], u["role"]), "role": u["role"], "nom": u.get("nom_affiche", u["login"]), "login": u["login"],
            "doit_changer_mdp": bool(u.get("doit_changer_mdp")), "ecole_id": u.get("ecole_id"),
            "plateforme": u["role"] in roles.ROLES_PLATEFORME and not u.get("ecole_id")}
