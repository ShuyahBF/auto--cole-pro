"""
PAIEMENTS : encaissements d'un élève (espèces, mobile money, virement, chèque, carte), reçus numérotés (PDF), annulation motivée (jamais de suppression), impayés avec retard
d'échéancier, caisse du jour. Un paiement ne dépasse jamais le reste dû. Numéro de reçu `R-AAAA-000001` (compteur atomique par école et par année).
"""
from __future__ import annotations

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .eleves import _eleve_visible, _public as _fiche, total_paye
from .tarifs import arrondi

routeur = APIRouter()


def _ecole() -> dict:
    return db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}


def _public(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in ("_id", "ecole_id")}


@routeur.post("/eleves/{eleve_id}/paiements")
def encaisser(eleve_id: str, corps: dict, u: dict = Depends(exiger_roles(roles.ENCAISSEMENT))):
    """Enregistre un encaissement : montant > 0 et ≤ reste dû, mode dans la liste de l'école, référence obligatoire pour mobile money / virement / chèque / carte."""
    e = _eleve_visible(eleve_id, u)
    ecole = _ecole()
    modes = {m["cle"]: m["libelle"] for m in ecole.get("modes_paiement", [])}
    mode = validation.choix(corps, "mode", "Mode de paiement", modes, obligatoire=True)
    montant = validation.nombre(corps, "montant", "Montant", 0.01, 1_000_000_000)
    if montant is None:
        validation.erreur("Montant : obligatoire")
    montant = arrondi(montant)
    reference = validation.texte(corps, "reference", "Référence (transaction, chèque…)", False, 60)
    if mode != "especes" and not reference:
        validation.erreur("Référence obligatoire pour ce mode de paiement (n° de transaction, de chèque ou de virement)")
    reste = arrondi(e["net_a_payer"] - total_paye(eleve_id))
    if montant > reste:
        raise HTTPException(409, f"Le montant dépasse le reste dû ({reste})")
    date_p = validation.date_iso(corps, "date", "Date du paiement", False, futur_ok=False) or date.today().isoformat()
    n = db.numero_suivant(f"recu-{date_p[:4]}")
    p = {"id": __import__("uuid").uuid4().hex, "recu": f"R-{date_p[:4]}-{n:06d}", "eleve_id": eleve_id, "matricule": e["matricule"], "eleve_nom": f"{e['nom']} {e['prenom']}",
         "agence_id": e["agence_id"], "montant": montant, "mode": mode, "mode_libelle": modes[mode], "reference": reference, "date": date_p,
         "motif": validation.texte(corps, "motif", "Motif", False, 120) or "Frais de formation", "encaisse_par": u["login"], "cree_le": db.maintenant(), "annule": False}
    db.base().paiements.insert_one(p)
    journaliser("paiement_encaisse", u, f"{p['recu']} {montant} {e['matricule']}")
    return _public(p)


@routeur.post("/paiements/{id_}/annuler")
def annuler(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ANNULATION_PAIEMENT))):
    """Annule un paiement (motif obligatoire) : il reste visible, barré, et ne compte plus. Le numéro de reçu n'est jamais réutilisé."""
    p = db.base().paiements.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Paiement introuvable")
    if p.get("annule"):
        raise HTTPException(409, "Ce paiement est déjà annulé")
    motif = validation.texte(corps, "motif", "Motif de l'annulation", True, 200)
    db.base().paiements.update_one({"id": id_}, {"$set": {"annule": True, "annule_le": db.maintenant(), "annule_par": u["login"], "motif_annulation": motif}})
    journaliser("paiement_annule", u, f"{p['recu']} : {motif[:80]}")
    return _public(db.base().paiements.find_one({"id": id_}))


@routeur.get("/paiements")
def lister(du: str = "", au: str = "", mode: str = "", limite: int = 300, u: dict = Depends(exiger_roles(roles.LECTURE_FINANCE))):
    """Paiements d'une période (aujourd'hui par défaut) avec totaux par mode ; un compte d'agence ne voit que son agence."""
    du = du or date.today().isoformat()
    au = au or du
    f: dict = {"date": {"$gte": du, "$lte": au}}
    if mode:
        f["mode"] = mode
    if u["agence_id"]:
        f["agence_id"] = u["agence_id"]
    lignes = [_public(p) for p in db.base().paiements.find(f, {"_id": 0}).sort([("date", -1), ("recu", -1)]).limit(max(1, min(limite, 2000)))]
    valides = [p for p in lignes if not p["annule"]]
    par_mode: dict = {}
    for p in valides:
        par_mode[p["mode_libelle"]] = arrondi(par_mode.get(p["mode_libelle"], 0) + p["montant"])
    return {"du": du, "au": au, "paiements": lignes, "total": arrondi(sum(p["montant"] for p in valides)), "nombre": len(valides), "par_mode": par_mode}


@routeur.get("/impayes")
def impayes(u: dict = Depends(exiger_roles(roles.LECTURE_FINANCE))):
    """Élèves avec un reste dû ; RETARD = échéances dépassées non couvertes par les paiements (les paiements couvrent les échéances de la plus ancienne à la plus récente)."""
    aujourdhui = date.today().isoformat()
    paye: dict = {}
    for p in db.base().paiements.find({"annule": {"$ne": True}}, {"eleve_id": 1, "montant": 1}):
        paye[p["eleve_id"]] = paye.get(p["eleve_id"], 0) + p["montant"]
    f = {"statut": {"$nin": ["abandon", "transfere"]}}
    if u["agence_id"]:
        f["agence_id"] = u["agence_id"]
    out = []
    for e in db.base().eleves.find(f, {"_id": 0}):
        deja = paye.get(e["id"], 0)
        reste = arrondi(e["net_a_payer"] - deja)
        if reste <= 0:
            continue
        du_echu = sum(x["montant"] for x in e.get("echeances", []) if x["date"] < aujourdhui)
        retard = arrondi(max(0, du_echu - deja))
        prochaine = next((x for x in e.get("echeances", []) if x["date"] >= aujourdhui), None)
        out.append({"id": e["id"], "matricule": e["matricule"], "nom": f"{e['nom']} {e['prenom']}", "telephone": e["telephone"], "agence_nom": e.get("agence_nom", ""),
                    "net_a_payer": e["net_a_payer"], "paye": arrondi(deja), "reste_du": reste, "retard": retard, "prochaine_echeance": prochaine})
    out.sort(key=lambda x: (-x["retard"], -x["reste_du"]))
    return {"impayes": out, "total_reste": arrondi(sum(x["reste_du"] for x in out)), "total_retard": arrondi(sum(x["retard"] for x in out))}


@routeur.get("/paiements/{id_}/recu")
def recu_pdf(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_FINANCE))):
    """Reçu PDF (A5) sur papier à en-tête de l'école, servi en ligne (affiché, jamais téléchargé de force) ; mention ANNULÉ si besoin."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.pdfgen import canvas
    p = db.base().paiements.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Paiement introuvable")
    if u["agence_id"] and p["agence_id"] != u["agence_id"]:
        raise HTTPException(404, "Paiement introuvable")
    e = _ecole()
    el = db.base().eleves.find_one({"id": p["eleve_id"]}) or {}
    paye = total_paye(p["eleve_id"])
    devise = e.get("devise", "")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    larg, haut = A5
    c.setFillColor(colors.HexColor("#0A1E3D")); c.rect(0, haut - 70, larg, 70, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 15); c.drawString(24, haut - 32, e.get("nom", "")[:48])
    c.setFont("Helvetica", 8); c.drawString(24, haut - 48, " · ".join(x for x in (e.get("adresse"), e.get("ville"), e.get("telephone")) if x)[:90])
    c.drawString(24, haut - 60, " · ".join(x for x in (e.get("identifiant_fiscal") and f"IFU/RCCM {e['identifiant_fiscal']}", e.get("agrement") and f"Agrément {e['agrement']}") if x)[:90])
    c.setFillColor(colors.HexColor("#FF7A0A")); c.setFont("Helvetica-Bold", 13); c.drawString(24, haut - 100, f"REÇU N° {p['recu']}")
    c.setFillColor(colors.black); c.setFont("Helvetica", 10)
    lignes = [("Date", p["date"]), ("Élève", f"{p['eleve_nom']} ({p['matricule']})"), ("Catégorie", el.get("categorie", "")), ("Motif", p["motif"]),
              ("Mode de paiement", p["mode_libelle"] + (f" — réf. {p['reference']}" if p["reference"] else "")), ("Encaissé par", p["encaisse_par"])]
    y = haut - 128
    for k, v in lignes:
        c.setFont("Helvetica-Bold", 9); c.drawString(24, y, k); c.setFont("Helvetica", 10); c.drawString(130, y, str(v)[:60]); y -= 18
    c.setFont("Helvetica-Bold", 16); c.drawRightString(larg - 24, y - 14, f"Montant : {p['montant']:,} {devise}".replace(",", " "))
    c.setFont("Helvetica", 9)
    c.drawRightString(larg - 24, y - 34, f"Total payé à ce jour : {arrondi(paye):,} {devise}".replace(",", " "))
    c.drawRightString(larg - 24, y - 48, f"Reste dû : {arrondi(max(0, el.get('net_a_payer', 0) - paye)):,} {devise}".replace(",", " "))
    c.setFont("Helvetica-Oblique", 8); c.drawString(24, 40, "Signature et cachet de l'auto-école"); c.line(24, 36, 200, 36)
    if p.get("annule"):
        c.saveState(); c.setFillColor(colors.HexColor("#C62828")); c.setFont("Helvetica-Bold", 60); c.translate(larg / 2, haut / 2); c.rotate(30); c.drawCentredString(0, 0, "ANNULÉ"); c.restoreState()
    c.showPage(); c.save()
    journaliser("recu_consulte", u, p["recu"])
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{p["recu"]}.pdf"', "Cache-Control": "no-store"})
