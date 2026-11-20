"""
EXAMENS internes (blancs, passés dans l'auto-école) et externes (officiels) : sessions, inscriptions des élèves avec contrôle d'éligibilité, convocations et listes de présence (PDF),
résultats, plannings (calendrier), statistiques de réussite.

Règles (paramétrables par école) :
- L'ORDRE des épreuves est celui de la liste « Épreuves d'examen » des paramètres : une épreuve exige d'avoir été ADMIS à la précédente (même catégorie).
- Un élève est éligible si : statut actif, catégorie identique à celle de la session, dossier complet (pièces obligatoires), pas d'impayé en RETARD (un responsable peut `forcer`
  pour un examen interne ; l'examen EXTERNE exige toujours un dossier complet), pas déjà inscrit à la session, places disponibles.
- Admis à la DERNIÈRE épreuve : l'élève passe « Permis obtenu ». Les tentatives (ajourné, absent) sont comptées par épreuve.
"""
from __future__ import annotations

import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .eleves import STATUTS_ACTIFS, _eleve_visible, _public as _fiche_eleve, total_paye
from .tarifs import arrondi

routeur = APIRouter()

TYPES = {"interne": "Examen interne (blanc)", "externe": "Examen externe (officiel)"}
RESULTATS = {"inscrit": "Inscrit", "absent": "Absent", "admis": "Admis", "ajourne": "Ajourné", "retire": "Retiré"}
STATUTS_SESSION = {"planifiee": "Planifiée", "terminee": "Terminée", "annulee": "Annulée"}


def _ecole() -> dict:
    return db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


def _session(id_: str, u: dict) -> dict:
    s = db.base().sessions_examen.find_one({"id": id_})
    if not s or (u["agence_id"] and s.get("agence_id") not in (None, "", u["agence_id"])):
        raise HTTPException(404, "Session introuvable")
    return s


def _resume(s: dict, inscrits: list | None = None) -> dict:
    ins = inscrits if inscrits is not None else list(db.base().inscriptions_examen.find({"session_id": s["id"]}, {"statut": 1}))
    actifs = [i for i in ins if i["statut"] != "retire"]
    return {**_public(s), "type_libelle": TYPES[s["type"]], "statut_libelle": STATUTS_SESSION[s["statut"]], "inscrits": len(actifs), "places_restantes": max(0, s["capacite"] - len(actifs)),
            "admis": sum(1 for i in ins if i["statut"] == "admis"), "ajournes": sum(1 for i in ins if i["statut"] == "ajourne"), "absents": sum(1 for i in ins if i["statut"] == "absent")}


# ---------- sessions ----------

@routeur.get("/examens/sessions")
def lister_sessions(du: str = "", au: str = "", type: str = "", statut: str = "", epreuve: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Sessions (par défaut : à partir d'aujourd'hui, prochaines d'abord) avec leurs effectifs ; une seule lecture groupée des inscriptions (pas de boucle N+1)."""
    f: dict = {"date": {"$gte": du or date.today().isoformat()}}
    if au:
        f["date"]["$lte"] = au
    for cle, val in (("type", type), ("statut", statut), ("epreuve", epreuve)):
        if val:
            f[cle] = val
    if u["agence_id"]:
        f["agence_id"] = {"$in": [None, "", u["agence_id"]]}
    sessions = list(db.base().sessions_examen.find(f, {"_id": 0}).sort([("date", 1), ("heure", 1)]))
    par: dict = {}
    for i in db.base().inscriptions_examen.find({"session_id": {"$in": [s["id"] for s in sessions]}}, {"session_id": 1, "statut": 1}):
        par.setdefault(i["session_id"], []).append(i)
    return [_resume(s, par.get(s["id"], [])) for s in sessions]


@routeur.post("/examens/sessions")
def creer_session(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """Planifie une session d'examen (date, heure, lieu, capacité, épreuve et catégorie parmi celles de l'école)."""
    e = _ecole()
    cats = {c["code"] for c in e.get("categories", [])}
    epr = {x["code"]: x["libelle"] for x in e.get("epreuves", [])}
    s = {"id": str(uuid.uuid4()), "type": validation.choix(corps, "type", "Type d'examen", TYPES, obligatoire=True), "epreuve": validation.choix(corps, "epreuve", "Épreuve", epr, obligatoire=True),
         "categorie": validation.choix(corps, "categorie", "Catégorie de permis", cats, obligatoire=True), "date": validation.date_iso(corps, "date", "Date", True),
         "heure": validation.heure(corps, "heure", "Heure"), "lieu": validation.texte(corps, "lieu", "Lieu", True, 120), "organisme": validation.texte(corps, "organisme", "Organisme / centre d'examen", False, 120),
         "capacite": int(validation.nombre(corps, "capacite", "Capacité", 1, 500) or 20), "agence_id": str(corps.get("agence_id") or "") or None, "examinateur": validation.texte(corps, "examinateur", "Examinateur", False, 80),
         "notes": validation.texte(corps, "notes", "Notes", False, 300), "statut": "planifiee", "cree_le": db.maintenant(), "cree_par": u["login"]}
    s["epreuve_libelle"] = epr[s["epreuve"]]
    if s["agence_id"] and not db.base().agences.find_one({"id": s["agence_id"]}):
        validation.erreur("Agence inconnue")
    db.base().sessions_examen.insert_one(s)
    journaliser("session_examen_creee", u, f"{s['type']} {s['epreuve']} {s['date']}")
    return _resume(s, [])


@routeur.put("/examens/sessions/{id_}")
def modifier_session(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """Modifie date, heure, lieu, capacité (jamais en dessous du nombre d'inscrits), notes ; annule la session (les inscrits sont prévenus par l'écran)."""
    s = _session(id_, u)
    if s["statut"] == "terminee":
        raise HTTPException(409, "Session terminée : plus modifiable")
    maj: dict = {}
    for cle, lib, lon in (("lieu", "Lieu", 120), ("organisme", "Organisme", 120), ("examinateur", "Examinateur", 80), ("notes", "Notes", 300)):
        if cle in corps:
            maj[cle] = validation.texte(corps, cle, lib, cle == "lieu", lon)
    if "date" in corps:
        maj["date"] = validation.date_iso(corps, "date", "Date", True)
    if "heure" in corps:
        maj["heure"] = validation.heure(corps, "heure", "Heure")
    if "capacite" in corps:
        cap = int(validation.nombre(corps, "capacite", "Capacité", 1, 500) or 1)
        if cap < db.base().inscriptions_examen.count_documents({"session_id": id_, "statut": {"$ne": "retire"}}):
            raise HTTPException(409, "La capacité ne peut pas être inférieure au nombre d'inscrits")
        maj["capacite"] = cap
    if corps.get("statut") == "annulee":
        maj["statut"] = "annulee"
    if maj:
        db.base().sessions_examen.update_one({"id": id_}, {"$set": maj})
        journaliser("session_examen_modifiee", u, f"{s['epreuve']} {s['date']}")
    return _resume(db.base().sessions_examen.find_one({"id": id_}))


# ---------- éligibilité et inscriptions ----------

def controle_eligibilite(eleve: dict, session: dict, forcer: bool = False) -> list[str]:
    """Liste des MOTIFS de refus (vide = éligible). Le contrôle est refait par le serveur à l'inscription ; l'écran l'affiche à l'avance."""
    motifs = []
    if eleve["statut"] not in STATUTS_ACTIFS:
        motifs.append("L'élève n'est plus en formation")
    if eleve["categorie"] != session["categorie"]:
        motifs.append(f"Catégorie différente (élève : {eleve['categorie']}, session : {session['categorie']})")
    if _fiche_eleve(eleve)["pieces_manquantes"]:
        motifs.append("Dossier incomplet : pièces obligatoires manquantes")
    aujourdhui = date.today().isoformat()
    du_echu = sum(x["montant"] for x in eleve.get("echeances", []) if x["date"] < aujourdhui)
    if du_echu > total_paye(eleve["id"]) and not (forcer and session["type"] == "interne"):
        motifs.append("Impayé en retard d'échéancier")
    epreuves = [x["code"] for x in _ecole().get("epreuves", [])]
    if session["epreuve"] in epreuves and epreuves.index(session["epreuve"]) > 0:
        prec = epreuves[epreuves.index(session["epreuve"]) - 1]
        ok = db.base().inscriptions_examen.find_one({"eleve_id": eleve["id"], "epreuve": prec, "categorie": session["categorie"], "statut": "admis"})
        if not ok:
            motifs.append(f"Épreuve précédente non réussie ({prec})")
    if db.base().inscriptions_examen.find_one({"eleve_id": eleve["id"], "session_id": session["id"], "statut": {"$ne": "retire"}}):
        motifs.append("Déjà inscrit à cette session")
    return motifs


@routeur.get("/examens/sessions/{id_}")
def detail_session(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Session avec la liste de ses inscrits (nom, matricule, résultat, tentative)."""
    s = _session(id_, u)
    ins = [_public(i) for i in db.base().inscriptions_examen.find({"session_id": id_}, {"_id": 0}).sort("eleve_nom", 1)]
    return {**_resume(s, ins), "inscriptions": ins}


@routeur.get("/examens/sessions/{id_}/eligibles")
def eligibles(id_: str, q: str = "", u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """Élèves de la catégorie de la session avec leur éligibilité et les motifs de refus (aide à l'inscription)."""
    s = _session(id_, u)
    f: dict = {"categorie": s["categorie"], "statut": {"$in": STATUTS_ACTIFS}}
    if u["agence_id"]:
        f["agence_id"] = u["agence_id"]
    if q.strip():
        n = validation.normaliser(q)
        f["$or"] = [{"nom_norm": {"$regex": n}}, {"prenom_norm": {"$regex": n}}, {"matricule": {"$regex": q.strip().upper()}}]
    return [{"id": e["id"], "matricule": e["matricule"], "nom": f"{e['nom']} {e['prenom']}", "motifs": controle_eligibilite(e, s)} for e in db.base().eleves.find(f).sort("nom_norm", 1).limit(100)]


@routeur.post("/examens/sessions/{id_}/inscriptions")
def inscrire(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """Inscrit un élève à la session (contrôles d'éligibilité refaits ici ; `forcer` réservé aux responsables, examen interne seulement)."""
    s = _session(id_, u)
    if s["statut"] != "planifiee":
        raise HTTPException(409, "Cette session n'accepte plus d'inscriptions")
    e = _eleve_visible(str(corps.get("eleve_id") or ""), u)
    forcer = bool(corps.get("forcer")) and u["role"] in roles.GESTION
    motifs = controle_eligibilite(e, s, forcer)
    if db.base().inscriptions_examen.count_documents({"session_id": id_, "statut": {"$ne": "retire"}}) >= s["capacite"]:
        motifs.append("Session complète")
    if motifs:
        raise HTTPException(409, " ; ".join(motifs))
    tentative = 1 + db.base().inscriptions_examen.count_documents({"eleve_id": e["id"], "epreuve": s["epreuve"], "categorie": s["categorie"], "statut": {"$in": ["ajourne", "absent"]}})
    i = {"id": str(uuid.uuid4()), "session_id": id_, "eleve_id": e["id"], "eleve_nom": f"{e['nom']} {e['prenom']}", "matricule": e["matricule"], "epreuve": s["epreuve"], "categorie": s["categorie"],
         "type": s["type"], "date": s["date"], "statut": "inscrit", "note": None, "observations": "", "tentative": tentative, "cree_le": db.maintenant(), "cree_par": u["login"]}
    db.base().inscriptions_examen.insert_one(i)
    journaliser("examen_inscription", u, f"{e['matricule']} → {s['epreuve']} {s['date']}")
    from .messagerie import notifier
    notifier("examen_inscription", e, {"examen": s["epreuve_libelle"], "date_examen": s["date"], "heure_examen": s.get("heure", ""), "lieu_examen": s["lieu"]})
    return _public(i)


@routeur.post("/examens/inscriptions/{id_}/retirer")
def retirer(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """Retire un inscrit d'une session non terminée (le résultat enregistré, lui, ne se retire plus)."""
    i = db.base().inscriptions_examen.find_one({"id": id_})
    if not i:
        raise HTTPException(404, "Inscription introuvable")
    if i["statut"] != "inscrit":
        raise HTTPException(409, "Un résultat est déjà enregistré")
    db.base().inscriptions_examen.update_one({"id": id_}, {"$set": {"statut": "retire", "observations": validation.texte(corps, "motif", "Motif", False, 200)}})
    journaliser("examen_inscription_retiree", u, i["matricule"])
    return {"ok": True}


@routeur.post("/examens/sessions/{id_}/resultats")
def enregistrer_resultats(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_EXAMEN))):
    """
    Enregistre les résultats (liste `resultats` de {inscription_id, statut: admis|ajourne|absent, note?, observations?}) et, avec `cloturer`, termine la session.
    Admis à la dernière épreuve de l'école → l'élève passe « Permis obtenu » (daté dans l'historique de son dossier).
    """
    s = _session(id_, u)
    if s["statut"] == "annulee":
        raise HTTPException(409, "Session annulée")
    lignes = corps.get("resultats")
    if not isinstance(lignes, list) or not lignes:
        validation.erreur("Résultats : liste obligatoire")
    epreuves = [x["code"] for x in _ecole().get("epreuves", [])]
    dernier = epreuves[-1] if epreuves else None
    diplomes = 0
    for r in lignes:
        i = db.base().inscriptions_examen.find_one({"id": str(r.get("inscription_id") or ""), "session_id": id_})
        if not i or i["statut"] == "retire":
            validation.erreur("Inscription inconnue dans cette session")
        statut = validation.choix(r, "statut", "Résultat", ["admis", "ajourne", "absent"], obligatoire=True)
        note = validation.nombre(r, "note", "Note", 0, 1000)
        db.base().inscriptions_examen.update_one({"id": i["id"]}, {"$set": {"statut": statut, "note": note, "observations": validation.texte(r, "observations", "Observations", False, 200), "resultat_le": db.maintenant()}})
        if statut == "admis" and s["epreuve"] == dernier:
            e = db.base().eleves.find_one({"id": i["eleve_id"]})
            if e and e["statut"] != "diplome":
                ligne = {"quand": db.maintenant(), "de": e["statut"], "a": "diplome", "par": u["login"], "motif": f"Admis à l'épreuve {s['epreuve']} le {s['date']}"}
                db.base().eleves.update_one({"id": e["id"]}, {"$set": {"statut": "diplome", "date_permis": s["date"]}, "$push": {"historique_statuts": ligne}})
                diplomes += 1
    if corps.get("cloturer"):
        db.base().sessions_examen.update_one({"id": id_}, {"$set": {"statut": "terminee", "cloturee_le": db.maintenant()}})
    journaliser("examen_resultats", u, f"{s['epreuve']} {s['date']} ({len(lignes)} résultat(s))")
    return {**_resume(db.base().sessions_examen.find_one({"id": id_})), "nouveaux_diplomes": diplomes}


@routeur.get("/eleves/{eleve_id}/examens")
def examens_eleve(eleve_id: str, u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Parcours d'examens d'un élève (toutes tentatives)."""
    _eleve_visible(eleve_id, u)
    return [_public(i) for i in db.base().inscriptions_examen.find({"eleve_id": eleve_id}, {"_id": 0}).sort("date", -1)]


# ---------- planning ----------

@routeur.get("/examens/planning")
def planning(mois: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Planning d'un mois (AAAA-MM, mois courant par défaut) : sessions regroupées par jour, pour le calendrier."""
    mois = mois or date.today().strftime("%Y-%m")
    sessions = lister_sessions(du=mois + "-01", au=mois + "-31", u=u)
    jours: dict = {}
    for s in sessions:
        jours.setdefault(s["date"], []).append(s)
    return {"mois": mois, "jours": [{"date": d, "sessions": v} for d, v in sorted(jours.items())], "total_sessions": len(sessions)}


# ---------- PDF : convocation et liste de présence ----------

def _entete_pdf(c, e: dict, titre: str, larg: float, haut: float):
    from reportlab.lib import colors
    c.setFillColor(colors.HexColor("#0A1E3D")); c.rect(0, haut - 60, larg, 60, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 14); c.drawString(30, haut - 30, e.get("nom", "")[:55])
    c.setFont("Helvetica", 8); c.drawString(30, haut - 46, " · ".join(x for x in (e.get("adresse"), e.get("ville"), e.get("telephone")) if x)[:110])
    c.setFillColor(colors.HexColor("#FF7A0A")); c.setFont("Helvetica-Bold", 14); c.drawString(30, haut - 90, titre); c.setFillColor(colors.black)


@routeur.get("/examens/inscriptions/{id_}/convocation")
def convocation(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Convocation PDF (A5) d'un élève : épreuve, date, heure, lieu, pièces à apporter. Servie en ligne."""
    from reportlab.lib.pagesizes import A5
    from reportlab.pdfgen import canvas
    i = db.base().inscriptions_examen.find_one({"id": id_})
    if not i:
        raise HTTPException(404, "Inscription introuvable")
    _eleve_visible(i["eleve_id"], u)
    s = db.base().sessions_examen.find_one({"id": i["session_id"]}) or {}
    e = _ecole()
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A5); larg, haut = A5
    _entete_pdf(c, e, "CONVOCATION À L'EXAMEN", larg, haut)
    y = haut - 125
    for k, v in (("Candidat", i["eleve_nom"]), ("Matricule", i["matricule"]), ("Examen", f"{TYPES.get(s.get('type'), '')} — {s.get('epreuve_libelle', i['epreuve'])}"), ("Catégorie", i["categorie"]),
                 ("Date", s.get("date", "")), ("Heure", s.get("heure", "")), ("Lieu", s.get("lieu", "")), ("Tentative n°", str(i["tentative"]))):
        c.setFont("Helvetica-Bold", 9); c.drawString(30, y, k); c.setFont("Helvetica", 10); c.drawString(130, y, str(v)[:55]); y -= 18
    c.setFont("Helvetica-Oblique", 9); c.drawString(30, y - 12, "À présenter le jour de l'examen : cette convocation et une pièce d'identité en cours de validité.")
    c.showPage(); c.save()
    journaliser("convocation_consultee", u, i["matricule"])
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="convocation.pdf"', "Cache-Control": "no-store"})


@routeur.get("/examens/sessions/{id_}/presence")
def liste_presence(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_EXAMEN))):
    """Liste de présence PDF (A4) de la session : nom, matricule, tentative, case de signature."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    s = _session(id_, u)
    ins = list(db.base().inscriptions_examen.find({"session_id": id_, "statut": {"$ne": "retire"}}).sort("eleve_nom", 1))
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); larg, haut = A4
    _entete_pdf(c, _ecole(), "LISTE DE PRÉSENCE", larg, haut)
    c.setFont("Helvetica", 10); c.drawString(30, haut - 112, f"{TYPES[s['type']]} — {s['epreuve_libelle']} — catégorie {s['categorie']} — {s['date']} {s.get('heure', '')} — {s['lieu']}"[:110])
    y = haut - 140
    c.setFont("Helvetica-Bold", 9); c.drawString(30, y, "N°"); c.drawString(55, y, "Candidat"); c.drawString(270, y, "Matricule"); c.drawString(370, y, "Tent."); c.drawString(420, y, "Signature")
    c.setFont("Helvetica", 10)
    for n, i in enumerate(ins, 1):
        y -= 24
        if y < 60:
            c.showPage(); y = haut - 60
        c.drawString(30, y, str(n)); c.drawString(55, y, i["eleve_nom"][:34]); c.drawString(270, y, i["matricule"]); c.drawString(375, y, str(i["tentative"])); c.line(420, y - 3, larg - 30, y - 3)
    c.showPage(); c.save()
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="presence.pdf"', "Cache-Control": "no-store"})


# ---------- statistiques ----------

@routeur.get("/statistiques/examens")
def statistiques(du: str = "", au: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_STATS))):
    """
    Taux de réussite (admis / présents) par épreuve, type d'examen, catégorie et mois, tentatives moyennes pour réussir et délai moyen inscription → permis.
    Les absents ne comptent pas dans le taux (ils sont comptés à part). Période : 12 derniers mois par défaut.
    """
    au = au or date.today().isoformat()
    du = du or f"{int(au[:4]) - 1}{au[4:]}"
    ins = list(db.base().inscriptions_examen.find({"date": {"$gte": du, "$lte": au}, "statut": {"$in": ["admis", "ajourne", "absent"]}}, {"_id": 0}))

    def groupe(cle):
        g: dict = {}
        for i in ins:
            k = cle(i)
            a = g.setdefault(k, {"passes": 0, "admis": 0, "absents": 0})
            if i["statut"] == "absent":
                a["absents"] += 1
            else:
                a["passes"] += 1
                a["admis"] += i["statut"] == "admis"
        return [{"cle": k, **v, "taux": round(100 * v["admis"] / v["passes"], 1) if v["passes"] else None} for k, v in sorted(g.items())]
    admis = [i for i in ins if i["statut"] == "admis"]
    diplomes = list(db.base().eleves.find({"statut": "diplome", "date_permis": {"$gte": du, "$lte": au}}, {"date_inscription": 1, "date_permis": 1}))
    delais = [(date.fromisoformat(e["date_permis"]) - date.fromisoformat(e["date_inscription"])).days for e in diplomes if e.get("date_permis")]
    total_p = sum(1 for i in ins if i["statut"] != "absent")
    return {"du": du, "au": au, "passes": total_p, "admis": len(admis), "taux_global": round(100 * len(admis) / total_p, 1) if total_p else None,
            "tentatives_moyennes_pour_reussir": round(sum(i["tentative"] for i in admis) / len(admis), 2) if admis else None,
            "delai_moyen_permis_jours": round(sum(delais) / len(delais)) if delais else None, "permis_obtenus": len(diplomes),
            "par_epreuve": groupe(lambda i: i["epreuve"]), "par_type": groupe(lambda i: i["type"]), "par_categorie": groupe(lambda i: i["categorie"]), "par_mois": groupe(lambda i: i["date"][:7])}
