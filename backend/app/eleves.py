"""
ÉLÈVES : inscription (matricule unique, contrôle de l'âge minimum de la catégorie, détection de doublon, prix et remise COPIÉS du tarif), dossier (pièces reçues),
échéancier, statuts de formation, recherche paginée et triée côté serveur. Un compte limité à une agence ne voit que les élèves de son agence.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, validation
from .auth import exiger_roles, journaliser, utilisateur_courant
from .tarifs import arrondi, promotion_valide, remise_pour

routeur = APIRouter()

STATUTS = {"inscrit": "Inscrit", "en_formation": "En formation", "pret_examen": "Prêt pour l'examen", "diplome": "Permis obtenu", "abandon": "Abandon", "transfere": "Transféré"}
STATUTS_ACTIFS = ["inscrit", "en_formation", "pret_examen"]
CHAMPS_TRI = {"matricule": "matricule", "nom": "nom_norm", "date": "date_inscription", "statut": "statut", "categorie": "categorie", "net": "net_a_payer"}


def _ecole() -> dict:
    return db.brut().ecoles.find_one({"id": db.ecole_courante.get()}) or {}


def total_paye(eleve_id: str) -> float:
    """Somme des paiements VALIDES (non annulés) d'un élève."""
    return sum(p["montant"] for p in db.base().paiements.find({"eleve_id": eleve_id, "annule": {"$ne": True}}, {"montant": 1}))


def _public(e: dict, paye: float | None = None) -> dict:
    """Fiche sans champs techniques ; ajoute payé, reste dû et complétude du dossier."""
    out = {k: v for k, v in e.items() if k not in ("_id", "ecole_id", "nom_norm", "prenom_norm")}
    if paye is not None:
        out["paye"] = arrondi(paye)
        out["reste_du"] = arrondi(max(0, e.get("net_a_payer", 0) - paye))
    manquantes = [p["cle"] for p in (_ecole().get("pieces") or []) if p.get("obligatoire") and not (e.get("pieces") or {}).get(p["cle"])]
    out["pieces_manquantes"] = manquantes
    out["dossier_complet"] = not manquantes
    return out


def _filtre_agence(u: dict) -> dict:
    return {"agence_id": u["agence_id"]} if u["agence_id"] else {}


def _eleve_visible(id_: str, u: dict) -> dict:
    e = db.base().eleves.find_one({"id": id_, **_filtre_agence(u)})
    if not e:
        raise HTTPException(404, "Élève introuvable")
    return e


def _echeances(corps: dict, net: float) -> list:
    """Échéancier : liste {date, montant} dont le total ne dépasse pas le net à payer."""
    v = corps.get("echeances")
    if v is None:
        return None
    if not isinstance(v, list) or len(v) > 24:
        validation.erreur("Échéancier : 24 échéances au plus")
    out, total = [], 0
    for x in v:
        d = validation.date_iso({"d": x.get("date")}, "d", "Date d'échéance", True)
        m = validation.nombre({"m": x.get("montant")}, "m", "Montant d'échéance", 0.01, 1_000_000_000)
        if m is None:
            validation.erreur("Échéancier : montant obligatoire")
        out.append({"date": d, "montant": arrondi(m)})
        total += m
    if total > net + 0.001:
        validation.erreur("Le total de l'échéancier dépasse le montant à payer")
    return sorted(out, key=lambda e: e["date"])


def _identite(corps: dict) -> dict:
    """Champs d'identité et de contact validés (inscription ET modification)."""
    nom, prenom = validation.texte(corps, "nom", "Nom", True, 60).upper(), validation.texte(corps, "prenom", "Prénom(s)", True, 80)
    tel = re.sub(r"[^\d+]", "", validation.texte(corps, "telephone", "Téléphone", True, 25))
    if len(tel) < 6:
        validation.erreur("Téléphone : numéro invalide")
    email = validation.texte(corps, "email", "E-mail", False, 120).lower()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        validation.erreur("E-mail : adresse invalide")
    return {"nom": nom, "prenom": prenom, "nom_norm": validation.normaliser(nom), "prenom_norm": validation.normaliser(prenom),
            "date_naissance": validation.date_iso(corps, "date_naissance", "Date de naissance", True, futur_ok=False), "sexe": validation.choix(corps, "sexe", "Sexe", ["M", "F"]),
            "telephone": tel, "email": email, "adresse": validation.texte(corps, "adresse", "Adresse", False, 160), "profession": validation.texte(corps, "profession", "Profession", False, 80),
            "piece_identite": validation.texte(corps, "piece_identite", "N° pièce d'identité", False, 40), "personne_a_prevenir": validation.texte(corps, "personne_a_prevenir", "Personne à prévenir", False, 120),
            "remarque": validation.texte(corps, "remarque", "Remarque", False, 400)}


@routeur.get("/eleves")
def lister(q: str = "", statut: str = "", agence_id: str = "", categorie: str = "", impaye: bool = False, page: int = 1, limite: int = 30, tri: str = "date", sens: str = "desc",
           u: dict = Depends(exiger_roles(roles.LECTURE_ELEVE))):
    """Recherche paginée (nom, matricule, téléphone) ; tri côté serveur sur toutes les lignes filtrées AVANT la pagination."""
    f: dict = _filtre_agence(u)
    if agence_id and not u["agence_id"]:
        f["agence_id"] = agence_id
    if statut:
        f["statut"] = statut if statut != "actifs" else {"$in": STATUTS_ACTIFS}
    if categorie:
        f["categorie"] = categorie
    if q.strip():
        n = re.escape(validation.normaliser(q))
        f["$or"] = [{"nom_norm": {"$regex": n}}, {"prenom_norm": {"$regex": n}}, {"matricule": {"$regex": re.escape(q.strip().upper())}}, {"telephone": {"$regex": re.escape(re.sub(r"[^\d+]", "", q))}} if re.sub(r"[^\d+]", "", q) else {"nom_norm": "\0"}]
    # Paiements groupés en UNE lecture (pas de boucle N+1) ; le filtre « impayés » se fait sur le calcul, donc avant la pagination.
    paye = {}
    for p in db.base().paiements.find({"annule": {"$ne": True}}, {"eleve_id": 1, "montant": 1}):
        paye[p["eleve_id"]] = paye.get(p["eleve_id"], 0) + p["montant"]
    cle = CHAMPS_TRI.get(tri, "date_inscription")
    lignes = list(db.base().eleves.find(f, {"_id": 0}))
    lignes.sort(key=lambda e: (e.get(cle) is None, e.get(cle) if e.get(cle) is not None else ""), reverse=(sens == "desc"))
    sorties = [_public(e, paye.get(e["id"], 0)) for e in lignes]
    if impaye and u["role"] != roles.MONITEUR:
        sorties = [e for e in sorties if e["reste_du"] > 0]
    if u["role"] == roles.MONITEUR:
        # Le moniteur n'a pas accès aux montants : le serveur les retire (l'écran ne fait pas le tri des droits).
        sorties = [{k: v for k, v in e.items() if k not in ("prix", "remise", "net_a_payer", "paye", "reste_du", "promotion", "echeances")} for e in sorties]
    total = len(sorties)
    limite = max(1, min(limite, 200))
    debut = (max(1, page) - 1) * limite
    return {"total": total, "page": page, "limite": limite, "eleves": sorties[debut:debut + limite],
            "totaux": None if u["role"] == roles.MONITEUR else {"net": arrondi(sum(e.get("net_a_payer", 0) for e in sorties)), "paye": arrondi(sum(e["paye"] for e in sorties)), "reste_du": arrondi(sum(e["reste_du"] for e in sorties))}}


@routeur.post("/eleves")
def inscrire(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_ELEVE))):
    """
    Inscription : contrôle de l'âge minimum de la catégorie, doublon (même nom, prénom et date de naissance → 409 sauf `confirmer_doublon`), tarif actif, promotion valide,
    matricule `PRÉFIXE-AA-000001` (compteur atomique de l'école). Prix, remise et net sont COPIÉS : une modification ultérieure du tarif ne change pas ce dossier.
    """
    e = _ecole()
    ident = _identite(corps)
    cats = {c["code"]: c for c in e.get("categories", [])}
    categorie = validation.choix(corps, "categorie", "Catégorie de permis", cats, obligatoire=True)
    age = validation.age(ident["date_naissance"])
    if age is not None and age < cats[categorie].get("age_min", 18):
        validation.erreur(f"Âge minimum pour la catégorie {categorie} : {cats[categorie].get('age_min', 18)} ans")
    if not corps.get("confirmer_doublon") and db.base().eleves.find_one({"nom_norm": ident["nom_norm"], "prenom_norm": ident["prenom_norm"], "date_naissance": ident["date_naissance"]}):
        raise HTTPException(409, "Un élève de même nom, prénom et date de naissance existe déjà : confirmez pour créer quand même")
    tarif = db.base().tarifs.find_one({"id": str(corps.get("tarif_id") or ""), "actif": True})
    if not tarif or tarif["categorie"] != categorie:
        validation.erreur("Tarif : choisissez un forfait actif de la même catégorie")
    promo = None
    if str(corps.get("promotion") or "").strip():
        promo = promotion_valide(corps["promotion"])
        if not promo:
            validation.erreur("Promotion inconnue, inactive ou hors période")
    agence = str(corps.get("agence_id") or u["agence_id"] or "").strip()
    ag = db.base().agences.find_one({"id": agence, "actif": True}) if agence else db.base().agences.find_one({"principale": True})
    if not ag:
        validation.erreur("Agence inconnue ou désactivée")
    if u["agence_id"] and ag["id"] != u["agence_id"]:
        raise HTTPException(403, "Vous ne pouvez inscrire que dans votre agence")
    remise = remise_pour(tarif["prix"], promo)
    n = db.numero_suivant(f"matricule-{date.today().year}")
    pieces = {p["cle"]: bool((corps.get("pieces") or {}).get(p["cle"])) for p in e.get("pieces", [])}
    fiche = {"id": str(uuid.uuid4()), "matricule": f"{e['prefixe']}-{str(date.today().year)[2:]}-{n:06d}", **ident, "categorie": categorie, "agence_id": ag["id"], "agence_nom": ag["nom"],
             "tarif_id": tarif["id"], "tarif_libelle": tarif["libelle"], "prix": tarif["prix"], "promotion": promo["code"] if promo else "", "remise": remise,
             "net_a_payer": arrondi(tarif["prix"] - remise), "heures_conduite_prevues": tarif["heures_conduite"], "seances_code_prevues": tarif["seances_code"],
             "statut": "inscrit", "pieces": pieces, "echeances": [], "date_inscription": date.today().isoformat(), "inscrit_par": u["login"], "cree_le": db.maintenant()}
    ech = _echeances(corps, fiche["net_a_payer"])
    if ech:
        fiche["echeances"] = ech
    db.base().eleves.insert_one(fiche)
    journaliser("eleve_inscrit", u, fiche["matricule"])
    from .messagerie import notifier
    notifier("inscription", fiche)                       # message de bienvenue (option par école ; ne bloque jamais l'inscription)
    return _public(fiche, 0)


@routeur.get("/eleves/{id_}")
def fiche(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_ELEVE))):
    """Dossier complet : identité, pièces, échéancier, paiements (le moniteur ne voit pas les montants encaissés : seulement le statut de paiement)."""
    e = _eleve_visible(id_, u)
    pay = [{k: v for k, v in p.items() if k not in ("_id", "ecole_id")} for p in db.base().paiements.find({"eleve_id": id_}, {"_id": 0}).sort("date", -1)]
    sortie = _public(e, sum(p["montant"] for p in pay if not p.get("annule")))
    if u["role"] == roles.MONITEUR:
        sortie = {k: v for k, v in sortie.items() if k not in ("prix", "remise", "net_a_payer", "paye", "reste_du", "echeances", "promotion")}
        return sortie
    return {**sortie, "paiements": pay}


@routeur.put("/eleves/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_ELEVE))):
    """Corrige l'identité, les pièces reçues, l'échéancier ; le prix, la catégorie et le tarif ne changent pas ici (annulez et réinscrivez)."""
    e = _eleve_visible(id_, u)
    maj = _identite({**e, **corps})
    if "pieces" in corps:
        autorisees = {p["cle"] for p in _ecole().get("pieces", [])}
        maj["pieces"] = {**(e.get("pieces") or {}), **{k: bool(v) for k, v in (corps["pieces"] or {}).items() if k in autorisees}}
    ech = _echeances(corps, e["net_a_payer"])
    if ech is not None:
        maj["echeances"] = ech
    db.base().eleves.update_one({"id": id_}, {"$set": maj})
    journaliser("eleve_modifie", u, e["matricule"])
    return _public(db.base().eleves.find_one({"id": id_}), total_paye(id_))


@routeur.post("/eleves/{id_}/statut")
def changer_statut(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_ELEVE))):
    """Change le statut de formation (liste finie) ; « prêt pour l'examen » exige un dossier complet. Chaque changement est daté dans l'historique du dossier."""
    e = _eleve_visible(id_, u)
    s = validation.choix(corps, "statut", "Statut", STATUTS, obligatoire=True)
    if s == e["statut"]:
        return _public(e, total_paye(id_))
    if s == "pret_examen" and _public(e)["pieces_manquantes"]:
        raise HTTPException(409, "Dossier incomplet : pièces obligatoires manquantes")
    ligne = {"quand": db.maintenant(), "de": e["statut"], "a": s, "par": u["login"], "motif": validation.texte(corps, "motif", "Motif", False, 200)}
    db.base().eleves.update_one({"id": id_}, {"$set": {"statut": s}, "$push": {"historique_statuts": ligne}})
    journaliser("eleve_statut", u, f"{e['matricule']} {e['statut']} → {s}")
    return _public(db.base().eleves.find_one({"id": id_}), total_paye(id_))
