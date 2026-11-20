"""
ÉVALUATIONS PAR LES CLIENTS (élèves) : demande d'avis par lien personnel à usage unique (envoyé par WhatsApp), page publique de réponse (sans compte), satisfaction globale (1-5),
NPS (0-10), notes par critère (moniteur, véhicule, accueil, tarifs, organisation), commentaire ; synthèse (moyennes, NPS), réponse de l'école, publication des avis consentis.

Sécurité (règle 21) : le lien contient un jeton aléatoire dont seule l'EMPREINTE SHA-256 est gardée ; il ne sert qu'UNE fois et expire (30 jours) ; la page publique ne montre que le prénom
de l'élève et le nom de l'école ; réponses limitées par adresse IP ; les commentaires des clients sont du texte non fiable (jamais interprété comme du code, affiché échappé).
Le moniteur évalué est déduit du livret (celui qui a fait le plus de séances avec l'élève) : l'élève ne saisit aucun nom.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .config import origines_site

routeur = APIRouter()
CRITERES = {"moniteur": "Moniteur", "vehicule": "Véhicule", "accueil": "Accueil", "tarifs": "Rapport qualité / prix", "organisation": "Organisation des cours et examens"}
VALIDITE_JOURS = 30
_essais: dict = {}                 # IP → [horodatages] (limite de réponses par IP ; mémoire du processus)


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


def creer_demande(eleve: dict) -> str:
    """Crée la demande d'avis d'un élève (une seule demande valide à la fois) et rend le LIEN personnel à lui envoyer. Le jeton n'est gardé que sous forme d'empreinte."""
    db.base().demandes_avis.delete_many({"eleve_id": eleve["id"], "repondu": False})
    jeton = secrets.token_urlsafe(24)
    seances = db.base().seances_conduite.find({"eleve_id": eleve["id"], "type": "conduite"}, {"moniteur": 1, "duree_min": 1})
    par: dict = {}
    for s in seances:
        par[s["moniteur"]] = par.get(s["moniteur"], 0) + s["duree_min"]
    db.base().demandes_avis.insert_one({"id": str(uuid.uuid4()), "empreinte": _empreinte(jeton), "eleve_id": eleve["id"], "prenom": eleve["prenom"], "categorie": eleve["categorie"],
                                        "moniteur": max(par, key=par.get) if par else "", "repondu": False, "cree_le": _maintenant(),
                                        "expire_le": (datetime.now(timezone.utc) + timedelta(days=VALIDITE_JOURS)).isoformat(timespec="seconds")})
    origine = (origines_site() or [""])[0]
    return f"{origine}/avis/{jeton}"


def _demande_par_jeton(jeton: str) -> tuple[dict, dict]:
    """(demande, école) d'un lien ; erreur 404 générique si inconnu ou expiré (rien ne révèle ce qui existe)."""
    d = db.brut().demandes_avis.find_one({"empreinte": _empreinte(jeton)})
    if not d or d["expire_le"] < _maintenant():
        raise HTTPException(404, "Lien invalide ou expiré")
    return d, db.brut().ecoles.find_one({"id": d["ecole_id"]}) or {}


# ---------- pages publiques (sans compte) ----------

@routeur.get("/public/avis/{jeton}")
def formulaire(jeton: str):
    """Ce que la page publique affiche : nom de l'école, prénom de l'élève, critères, et si la réponse a déjà été donnée."""
    d, e = _demande_par_jeton(jeton)
    return {"ecole": e.get("nom", ""), "prenom": d["prenom"], "deja_repondu": d["repondu"], "criteres": [{"cle": k, "libelle": v} for k, v in CRITERES.items()]}


@routeur.post("/public/avis/{jeton}")
def repondre(jeton: str, corps: dict, request: Request):
    """Enregistre l'avis (une seule fois par lien). 10 réponses par heure et par adresse IP au plus."""
    ip = (request.client.host if request.client else "?")
    maintenant = time.time()
    _essais[ip] = [t for t in _essais.get(ip, []) if maintenant - t < 3600]
    if len(_essais[ip]) >= 10:
        raise HTTPException(429, "Trop de réponses depuis cette adresse, réessayez plus tard")
    _essais[ip].append(maintenant)
    d, e = _demande_par_jeton(jeton)
    if d["repondu"]:
        raise HTTPException(409, "Vous avez déjà répondu : merci !")
    globale = validation.nombre(corps, "note_globale", "Satisfaction globale", 1, 5)
    if globale is None:
        validation.erreur("Satisfaction globale : une note de 1 à 5 est obligatoire")
    notes = {}
    for k in CRITERES:
        n = validation.nombre({"n": (corps.get("notes") or {}).get(k)}, "n", CRITERES[k], 1, 5)
        if n is not None:
            notes[k] = int(n)
    nps = validation.nombre(corps, "nps", "Recommandation", 0, 10)
    avis = {"id": str(uuid.uuid4()), "ecole_id": d["ecole_id"], "demande_id": d["id"], "eleve_id": d["eleve_id"], "prenom": d["prenom"], "categorie": d["categorie"], "moniteur": d["moniteur"],
            "note_globale": int(globale), "nps": int(nps) if nps is not None else None, "notes": notes, "commentaire": validation.texte(corps, "commentaire", "Commentaire", False, 500),
            "autorise_publication": bool(corps.get("autorise_publication")), "publie": False, "reponse_ecole": "", "cree_le": _maintenant()}
    db.brut().avis.insert_one(avis)
    db.brut().demandes_avis.update_one({"id": d["id"]}, {"$set": {"repondu": True, "repondu_le": _maintenant()}})
    return {"ok": True, "message": f"Merci {d['prenom']} ! Votre avis a bien été enregistré."}


# ---------- gestion par l'école ----------

@routeur.post("/avis/demandes")
def demander(corps: dict, u: dict = Depends(exiger_roles(roles.GESTION_AVIS))):
    """Crée la demande d'un élève et rend son lien (à envoyer par WhatsApp depuis la messagerie, ou à copier). Refusé si l'élève a répondu il y a moins de 90 jours."""
    e = db.base().eleves.find_one({"id": str(corps.get("eleve_id") or "")})
    if not e:
        raise HTTPException(404, "Élève introuvable")
    recent = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(timespec="seconds")
    if db.base().demandes_avis.find_one({"eleve_id": e["id"], "repondu": True, "repondu_le": {"$gte": recent}}):
        raise HTTPException(409, "Cet élève a déjà donné son avis récemment")
    lien = creer_demande(e)
    journaliser("avis_demande", u, e["matricule"])
    return {"lien": lien, "valide_jours": VALIDITE_JOURS}


@routeur.get("/avis")
def lister(note_max: int = 5, u: dict = Depends(exiger_roles(roles.LECTURE_AVIS))):
    """Avis reçus (récents d'abord), filtrables par note globale maximale (pour traiter d'abord les insatisfaits)."""
    f = {"note_globale": {"$lte": note_max}}
    return [_public(a) for a in db.base().avis.find(f, {"_id": 0}).sort("cree_le", -1).limit(500)]


@routeur.get("/avis/synthese")
def synthese(du: str = "", au: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_AVIS))):
    """
    Satisfaction moyenne, moyenne par critère, par moniteur, NPS (% de promoteurs 9-10 moins % de détracteurs 0-6) et taux de réponse (avis ÷ demandes envoyées).
    """
    f: dict = {}
    if du or au:
        f["cree_le"] = {k: v for k, v in (("$gte", du), ("$lte", (au + "T99") if au else "")) if v}
    avis = list(db.base().avis.find(f, {"_id": 0}))
    demandes = db.base().demandes_avis.count_documents({})

    def moy(xs):
        return round(sum(xs) / len(xs), 2) if xs else None
    nps = [a["nps"] for a in avis if a.get("nps") is not None]
    promoteurs, detracteurs = sum(1 for n in nps if n >= 9), sum(1 for n in nps if n <= 6)
    par_moniteur: dict = {}
    for a in avis:
        if a.get("moniteur"):
            par_moniteur.setdefault(a["moniteur"], []).append(a["notes"].get("moniteur") or a["note_globale"])
    return {"nombre": len(avis), "satisfaction": moy([a["note_globale"] for a in avis]), "par_critere": [{"cle": k, "libelle": v, "moyenne": moy([a["notes"][k] for a in avis if k in a["notes"]]), "nombre": sum(1 for a in avis if k in a["notes"])} for k, v in CRITERES.items()],
            "nps": round(100 * (promoteurs - detracteurs) / len(nps)) if nps else None, "promoteurs": promoteurs, "detracteurs": detracteurs, "neutres": len(nps) - promoteurs - detracteurs,
            "taux_reponse": round(100 * len(avis) / demandes) if demandes else None, "demandes": demandes,
            "par_moniteur": [{"moniteur": m, "moyenne": moy(v), "nombre": len(v)} for m, v in sorted(par_moniteur.items())]}


@routeur.put("/avis/{id_}")
def traiter(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.GESTION_AVIS))):
    """Répond à un avis (note interne) et le publie : seulement si le client a AUTORISÉ la publication."""
    a = db.base().avis.find_one({"id": id_})
    if not a:
        raise HTTPException(404, "Avis introuvable")
    maj = {}
    if "reponse_ecole" in corps:
        maj["reponse_ecole"] = validation.texte(corps, "reponse_ecole", "Réponse", False, 400)
    if "publie" in corps:
        if corps["publie"] and not a["autorise_publication"]:
            raise HTTPException(409, "Le client n'a pas autorisé la publication de son avis")
        maj["publie"] = bool(corps["publie"])
    if maj:
        db.base().avis.update_one({"id": id_}, {"$set": maj})
        journaliser("avis_traite", u, id_[:8])
    return _public(db.base().avis.find_one({"id": id_}))
