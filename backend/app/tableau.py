"""TABLEAU DE BORD : chiffres clés de l'auto-école (élèves par statut, inscriptions et encaissements du mois, impayés, répartition par catégorie et par agence)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from . import db, roles
from .auth import exiger_roles, utilisateur_courant
from .eleves import STATUTS
from .tarifs import arrondi

routeur = APIRouter()


def _mois_precedent(a: int, m: int) -> str:
    return f"{a - 1}-12" if m == 1 else f"{a}-{m - 1:02d}"


@routeur.get("/tableau")
def tableau(u: dict = Depends(exiger_roles(roles.LECTURE_STATS))):
    """Photographie de l'école (ou de l'agence du compte). Lectures en bloc : élèves et paiements, une seule fois chacun."""
    auj = date.today()
    mois, precedent = auj.strftime("%Y-%m"), _mois_precedent(auj.year, auj.month)
    fe: dict = {"agence_id": u["agence_id"]} if u["agence_id"] else {}
    eleves = list(db.base().eleves.find(fe, {"_id": 0, "id": 1, "statut": 1, "categorie": 1, "agence_nom": 1, "net_a_payer": 1, "date_inscription": 1}))
    ids = {e["id"] for e in eleves}
    pay = [p for p in db.base().paiements.find({"annule": {"$ne": True}}, {"_id": 0, "eleve_id": 1, "montant": 1, "date": 1, "mode_libelle": 1}) if p["eleve_id"] in ids]
    paye: dict = {}
    for p in pay:
        paye[p["eleve_id"]] = paye.get(p["eleve_id"], 0) + p["montant"]
    par_statut = {k: 0 for k in STATUTS}
    par_categorie: dict = {}
    par_agence: dict = {}
    for e in eleves:
        par_statut[e["statut"]] = par_statut.get(e["statut"], 0) + 1
        par_categorie[e["categorie"]] = par_categorie.get(e["categorie"], 0) + 1
        par_agence[e.get("agence_nom", "")] = par_agence.get(e.get("agence_nom", ""), 0) + 1
    actifs = [e for e in eleves if e["statut"] not in ("abandon", "transfere")]
    reste = sum(max(0, e["net_a_payer"] - paye.get(e["id"], 0)) for e in actifs)
    encaisse = lambda m: arrondi(sum(p["montant"] for p in pay if p["date"].startswith(m)))
    insc = lambda m: sum(1 for e in eleves if e["date_inscription"].startswith(m))
    finance = u["role"] in roles.LECTURE_FINANCE
    return {"eleves_total": len(eleves), "par_statut": [{"statut": k, "libelle": v, "nombre": par_statut.get(k, 0)} for k, v in STATUTS.items()],
            "inscriptions_mois": insc(mois), "inscriptions_mois_precedent": insc(precedent),
            "encaisse_mois": encaisse(mois) if finance else None, "encaisse_mois_precedent": encaisse(precedent) if finance else None,
            "encaisse_aujourdhui": arrondi(sum(p["montant"] for p in pay if p["date"] == auj.isoformat())) if finance else None,
            "reste_du_total": arrondi(reste) if finance else None, "eleves_avec_impaye": sum(1 for e in actifs if e["net_a_payer"] - paye.get(e["id"], 0) > 0) if finance else None,
            "par_categorie": [{"categorie": k, "nombre": v} for k, v in sorted(par_categorie.items())], "par_agence": [{"agence": k, "nombre": v} for k, v in sorted(par_agence.items())]}


@routeur.get("/notifications/compteurs")
def compteurs(u: dict = Depends(utilisateur_courant)):
    """
    Pastilles du menu (une seule route légère, filtrée par droits) : « Élèves » = dossiers incomplets, « Impayés » = élèves en retard d'échéancier,
    « Parc automobile » = alertes rouges (panne immobilisante, document expiré, rupture de pièce). Aucun calcul lourd.
    """
    out: dict = {}
    if u["ecole_id"] is None:
        return out
    if u["role"] in roles.LECTURE_ELEVE:
        aujourdhui = date.today().isoformat()
        fe: dict = {"statut": {"$nin": ["abandon", "transfere", "diplome"]}}
        if u["agence_id"]:
            fe["agence_id"] = u["agence_id"]
        eleves = list(db.base().eleves.find(fe, {"_id": 0, "id": 1, "net_a_payer": 1, "echeances": 1, "pieces": 1}))
        obligatoires = [p["cle"] for p in (db.brut().ecoles.find_one({"id": u["ecole_id"]}) or {}).get("pieces", []) if p.get("obligatoire")]
        out["/eleves"] = sum(1 for e in eleves if any(not (e.get("pieces") or {}).get(c) for c in obligatoires))
        if u["role"] in roles.LECTURE_FINANCE:
            paye: dict = {}
            for p in db.base().paiements.find({"annule": {"$ne": True}}, {"eleve_id": 1, "montant": 1}):
                paye[p["eleve_id"]] = paye.get(p["eleve_id"], 0) + p["montant"]
            out["/impayes"] = sum(1 for e in eleves if sum(x["montant"] for x in e.get("echeances", []) if x["date"] < aujourdhui) > paye.get(e["id"], 0))
    if u["role"] in roles.LECTURE_PARC:
        from .parc import calculer_alertes
        out["/parc"] = sum(1 for a in calculer_alertes(u) if a["niveau"] == "rouge")
    return out
