"""
LIVRET DE PROGRESSION : séances de conduite et de code consignées par le moniteur (date, durée, thème, appréciation, kilométrage), heures effectuées comparées aux heures prévues
au forfait. Le moniteur n'enregistre que SES séances ; la correction est réservée aux responsables.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .eleves import _eleve_visible

routeur = APIRouter()
TYPES = {"conduite": "Conduite", "code": "Code de la route"}
APPRECIATIONS = {"insuffisant": "Insuffisant", "en_progres": "En progrès", "acquis": "Acquis", "maitrise": "Maîtrisé"}


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


@routeur.get("/eleves/{eleve_id}/seances")
def livret(eleve_id: str, u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Livret de l'élève : séances (récentes d'abord) et totaux d'heures effectuées / prévues."""
    e = _eleve_visible(eleve_id, u)
    seances = [_public(s) for s in db.base().seances_conduite.find({"eleve_id": eleve_id}, {"_id": 0}).sort([("date", -1), ("cree_le", -1)])]
    minutes = sum(s["duree_min"] for s in seances if s["type"] == "conduite")
    repris = e.get("heures_deja_faites", 0)
    return {"seances": seances, "heures_conduite": round(minutes / 60 + repris, 1), "heures_reprises": repris, "heures_prevues": e.get("heures_conduite_prevues", 0),
            "seances_code": sum(1 for s in seances if s["type"] == "code"), "seances_code_prevues": e.get("seances_code_prevues", 0), "km": sum(s.get("km") or 0 for s in seances)}


@routeur.post("/eleves/{eleve_id}/seances")
def ajouter(eleve_id: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_SEANCE))):
    """Consigne une séance (durée 15 à 480 min, date non future). Une séance de conduite fait passer l'élève « En formation » s'il était seulement inscrit."""
    e = _eleve_visible(eleve_id, u)
    if e["statut"] in ("abandon", "transfere", "diplome"):
        raise HTTPException(409, "Cet élève n'est plus en formation")
    duree = validation.nombre(corps, "duree_min", "Durée (minutes)", 15, 480)
    if duree is None:
        validation.erreur("Durée : obligatoire")
    s = {"id": str(uuid.uuid4()), "eleve_id": eleve_id, "type": validation.choix(corps, "type", "Type de séance", TYPES, "conduite"), "date": validation.date_iso(corps, "date", "Date", False, futur_ok=False) or date.today().isoformat(),
         "duree_min": int(duree), "theme": validation.texte(corps, "theme", "Thème travaillé", False, 120), "appreciation": validation.choix(corps, "appreciation", "Appréciation", APPRECIATIONS),
         "observations": validation.texte(corps, "observations", "Observations", False, 300), "km": validation.nombre(corps, "km", "Kilométrage", 0, 2000), "vehicule_id": str(corps.get("vehicule_id") or "") or None,
         "moniteur": u["nom"], "moniteur_login": u["login"], "cree_le": db.maintenant()}
    db.base().seances_conduite.insert_one(s)
    if e["statut"] == "inscrit":
        ligne = {"quand": db.maintenant(), "de": "inscrit", "a": "en_formation", "par": u["login"], "motif": "Première séance"}
        db.base().eleves.update_one({"id": eleve_id}, {"$set": {"statut": "en_formation"}, "$push": {"historique_statuts": ligne}})
    journaliser("seance_ajoutee", u, f"{e['matricule']} {s['type']} {s['duree_min']} min")
    return _public(s)


@routeur.delete("/seances/{id_}")
def supprimer(id_: str, u: dict = Depends(exiger_roles(roles.GESTION))):
    """Corrige une erreur de saisie (responsables seulement ; l'action est journalisée)."""
    s = db.base().seances_conduite.find_one({"id": id_})
    if not s:
        raise HTTPException(404, "Séance introuvable")
    _eleve_visible(s["eleve_id"], u)
    db.base().seances_conduite.delete_one({"id": id_})
    journaliser("seance_supprimee", u, f"{s['date']} {s['duree_min']} min")
    return {"ok": True}


@routeur.get("/seances")
def planning_moniteur(du: str = "", au: str = "", moniteur: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Séances d'une période (7 derniers jours par défaut), par moniteur ; un moniteur ne voit que les siennes. Heures totales par moniteur."""
    au = au or date.today().isoformat()
    du = du or date.fromordinal(date.fromisoformat(au).toordinal() - 7).isoformat()
    f: dict = {"date": {"$gte": du, "$lte": au}}
    if u["role"] == roles.MONITEUR:
        f["moniteur_login"] = u["login"]
    elif moniteur:
        f["moniteur_login"] = moniteur
    lignes = [_public(s) for s in db.base().seances_conduite.find(f, {"_id": 0}).sort([("date", -1), ("cree_le", -1)]).limit(1000)]
    noms = {e["id"]: f"{e['nom']} {e['prenom']}" for e in db.base().eleves.find({"id": {"$in": list({s["eleve_id"] for s in lignes})}}, {"id": 1, "nom": 1, "prenom": 1})}
    par: dict = {}
    for s in lignes:
        s["eleve_nom"] = noms.get(s["eleve_id"], "")
        par[s["moniteur"]] = round(par.get(s["moniteur"], 0) + s["duree_min"] / 60, 1)
    return {"du": du, "au": au, "seances": lignes, "heures_par_moniteur": par}
