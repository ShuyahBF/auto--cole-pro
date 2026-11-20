"""
TRANSFERTS DE DOSSIERS : entre agences de l'école (immédiat), SORTANT vers une autre auto-école (dossier de transfert PDF, élève « Transféré ») et ENTRANT depuis une autre
auto-école (inscription normale + origine et heures déjà effectuées reprises). Un transfert sortant avec un reste dû exige la confirmation explicite du solde.
Chaque transfert est conservé (qui, quand, motif) ; aucune donnée n'est supprimée.
"""
from __future__ import annotations

import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .eleves import _eleve_visible, inscrire as inscrire_eleve, total_paye
from .tarifs import arrondi

routeur = APIRouter()
LIBELLES = {"agence": "Entre agences", "sortant": "Vers une autre auto-école", "entrant": "Depuis une autre auto-école"}


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


@routeur.get("/transferts")
def lister(type: str = "", u: dict = Depends(exiger_roles(roles.TRANSFERT))):
    """Historique des transferts (récents d'abord)."""
    f: dict = {"type": type} if type else {}
    return [{**_public(t), "type_libelle": LIBELLES[t["type"]]} for t in db.base().transferts.find(f, {"_id": 0}).sort("date", -1).limit(500)]


def _noter(e: dict, typ: str, u: dict, **plus) -> dict:
    t = {"id": str(uuid.uuid4()), "type": typ, "eleve_id": e["id"], "matricule": e["matricule"], "eleve_nom": f"{e['nom']} {e['prenom']}", "date": date.today().isoformat(),
         "motif": plus.pop("motif", ""), "par": u["login"], "cree_le": db.maintenant(), **plus}
    db.base().transferts.insert_one(t)
    return t


@routeur.post("/transferts/agence")
def entre_agences(corps: dict, u: dict = Depends(exiger_roles(roles.TRANSFERT))):
    """Change l'agence d'un élève (les paiements déjà encaissés restent rattachés à l'agence qui les a reçus)."""
    e = _eleve_visible(str(corps.get("eleve_id") or ""), u)
    a = db.base().agences.find_one({"id": str(corps.get("agence_id") or ""), "actif": True})
    if not a:
        validation.erreur("Agence de destination inconnue ou désactivée")
    if a["id"] == e["agence_id"]:
        raise HTTPException(409, "L'élève est déjà dans cette agence")
    if u["agence_id"] and a["id"] != u["agence_id"] and e["agence_id"] != u["agence_id"]:
        raise HTTPException(403, "Droits insuffisants")
    t = _noter(e, "agence", u, motif=validation.texte(corps, "motif", "Motif", False, 200), de_agence=e.get("agence_nom", ""), vers_agence=a["nom"])
    db.base().eleves.update_one({"id": e["id"]}, {"$set": {"agence_id": a["id"], "agence_nom": a["nom"]}})
    journaliser("transfert_agence", u, f"{e['matricule']} → {a['nom']}")
    return _public(t)


@routeur.post("/transferts/sortant")
def sortant(corps: dict, u: dict = Depends(exiger_roles(roles.TRANSFERT))):
    """Transfert vers une autre auto-école : l'élève passe « Transféré ». Un reste dû exige `accepter_solde` (le solde est alors noté dans le transfert)."""
    e = _eleve_visible(str(corps.get("eleve_id") or ""), u)
    if e["statut"] in ("transfere", "diplome", "abandon"):
        raise HTTPException(409, "Cet élève ne peut plus être transféré")
    reste = arrondi(e["net_a_payer"] - total_paye(e["id"]))
    if reste > 0 and not corps.get("accepter_solde"):
        raise HTTPException(409, f"Reste dû de {reste} : confirmez que le solde est accepté ou réglé avant le transfert")
    destination = validation.texte(corps, "ecole_destination", "Auto-école de destination", True, 120)
    t = _noter(e, "sortant", u, motif=validation.texte(corps, "motif", "Motif", False, 200), ecole_destination=destination, solde_restant=reste)
    ligne = {"quand": db.maintenant(), "de": e["statut"], "a": "transfere", "par": u["login"], "motif": f"Transfert vers {destination}"}
    db.base().eleves.update_one({"id": e["id"]}, {"$set": {"statut": "transfere"}, "$push": {"historique_statuts": ligne}})
    journaliser("transfert_sortant", u, f"{e['matricule']} → {destination}")
    return _public(t)


@routeur.post("/transferts/entrant")
def entrant(corps: dict, u: dict = Depends(exiger_roles(roles.TRANSFERT))):
    """Inscription d'un élève venu d'une autre auto-école : mêmes contrôles qu'une inscription, plus l'école d'origine et les heures de conduite déjà effectuées (reprises au livret)."""
    origine = validation.texte(corps, "ecole_origine", "Auto-école d'origine", True, 120)
    heures = validation.nombre(corps, "heures_deja_faites", "Heures déjà effectuées", 0, 500) or 0
    fiche = inscrire_eleve(corps, u)
    db.base().eleves.update_one({"id": fiche["id"]}, {"$set": {"origine_transfert": origine, "heures_deja_faites": heures}})
    e = db.base().eleves.find_one({"id": fiche["id"]})
    _noter(e, "entrant", u, motif=validation.texte(corps, "motif", "Motif", False, 200), ecole_origine=origine, heures_deja_faites=heures)
    journaliser("transfert_entrant", u, f"{e['matricule']} ← {origine}")
    return {**fiche, "origine_transfert": origine, "heures_deja_faites": heures}


@routeur.get("/transferts/{id_}/dossier")
def dossier_pdf(id_: str, u: dict = Depends(exiger_roles(roles.TRANSFERT))):
    """Dossier de transfert PDF (A4) remis à l'élève : identité, formation suivie (heures, séances de code), parcours d'examens, situation financière."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from .examens import _entete_pdf
    t = db.base().transferts.find_one({"id": id_})
    if not t:
        raise HTTPException(404, "Transfert introuvable")
    e = _eleve_visible(t["eleve_id"], u)
    ecole = db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}
    heures = round(sum(s["duree_min"] for s in db.base().seances_conduite.find({"eleve_id": e["id"], "type": "conduite"}, {"duree_min": 1})) / 60, 1)
    seances_code = db.base().seances_conduite.count_documents({"eleve_id": e["id"], "type": "code"})
    exam = list(db.base().inscriptions_examen.find({"eleve_id": e["id"], "statut": {"$in": ["admis", "ajourne", "absent"]}}).sort("date", 1))
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); larg, haut = A4
    _entete_pdf(c, ecole, "DOSSIER DE TRANSFERT", larg, haut)
    y = haut - 125
    def ligne(k, v):
        nonlocal y
        c.setFont("Helvetica-Bold", 9); c.drawString(30, y, k); c.setFont("Helvetica", 10); c.drawString(170, y, str(v)[:75]); y -= 17
    for k, v in (("Élève", f"{e['nom']} {e['prenom']}"), ("Matricule", e["matricule"]), ("Date de naissance", e["date_naissance"]), ("Catégorie", e["categorie"]), ("Inscrit le", e["date_inscription"]),
                 ("Transféré le", t["date"]), ("Vers", t.get("ecole_destination") or t.get("vers_agence") or ""), ("Motif", t["motif"]),
                 ("Conduite effectuée", f"{heures + e.get('heures_deja_faites', 0)} h sur {e.get('heures_conduite_prevues', 0)} h prévues"), ("Séances de code suivies", f"{seances_code} sur {e.get('seances_code_prevues', 0)}"),
                 ("Montant du forfait", e["net_a_payer"]), ("Déjà payé", total_paye(e["id"])), ("Solde restant", t.get("solde_restant", 0))):
        ligne(k, v)
    y -= 10; c.setFont("Helvetica-Bold", 10); c.drawString(30, y, "Parcours d'examens"); y -= 18; c.setFont("Helvetica", 9)
    for i in exam:
        c.drawString(30, y, f"{i['date']}  {i['epreuve']}  ({i['type']})  tentative {i['tentative']} : {i['statut']}"); y -= 14
    c.setFont("Helvetica-Oblique", 8); c.drawString(30, 50, "Document établi par l'auto-école d'origine. Signature et cachet :"); c.line(30, 40, 260, 40)
    c.showPage(); c.save()
    journaliser("dossier_transfert_consulte", u, e["matricule"])
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="dossier-transfert.pdf"', "Cache-Control": "no-store"})
