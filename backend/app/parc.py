"""
PARC AUTOMOBILE : véhicules (statut, échéances de documents), kilométrage (jamais en recul), carburant (consommation aux 100 km, anomalies), pannes, interventions
(entretien, réparation, contrôle ; consomment les pièces du stock), alertes d'échéances, coûts par véhicule.

Règles :
- Le kilométrage ne recule JAMAIS (anti-erreur et anti-fraude) : un relevé inférieur au dernier est refusé ; seul un responsable corrige, avec motif (journalisé).
- Consommation : calculée entre deux pleins COMPLETS consécutifs (litres du plein ÷ km parcourus × 100). Anomalie = plus de 40 % au-dessus de la moyenne du véhicule.
- Une panne « immobilisante » met le véhicule « en panne » ; il redevient « en service » quand plus aucune panne immobilisante n'est ouverte.
- Les MONTANTS (carburant, pièces, interventions) ne sont vus que de la comptabilité, du mécanicien et des responsables : le serveur les retire pour les autres rôles.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .tarifs import arrondi

routeur = APIRouter()

TYPES = {"voiture": "Voiture", "moto": "Moto", "camion": "Poids lourd", "bus": "Autocar", "remorque": "Remorque"}
CARBURANTS = {"essence": "Essence", "diesel": "Gasoil", "hybride": "Hybride", "electrique": "Électrique", "gpl": "GPL"}
STATUTS = {"en_service": "En service", "en_panne": "En panne", "en_maintenance": "En maintenance", "reforme": "Réformé"}
GRAVITES = {"mineure": "Mineure", "majeure": "Majeure", "immobilisante": "Immobilisante"}
TYPES_INTERVENTION = {"entretien": "Entretien", "reparation": "Réparation", "controle": "Contrôle / visite", "autre": "Autre"}
ECHEANCES = {"assurance_expire": "Assurance", "visite_expire": "Visite technique", "taxe_expire": "Vignette / taxe", "carte_grise_expire": "Carte grise"}
SEUIL_ANOMALIE = 1.4
JOURS_ALERTE = 30


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


def _couts_visibles(u: dict) -> bool:
    return u["role"] in roles.COUTS_PARC


def _vehicule(id_: str, u: dict) -> dict:
    v = db.base().vehicules.find_one({"id": id_})
    if not v or (u["agence_id"] and v.get("agence_id") not in (None, "", u["agence_id"])):
        raise HTTPException(404, "Véhicule introuvable")
    return v


def _masquer(d: dict, u: dict, champs=("montant", "prix_litre", "cout", "cout_main_oeuvre", "cout_pieces", "cout_total", "prix_achat")) -> dict:
    return d if _couts_visibles(u) else {k: v for k, v in d.items() if k not in champs}


# ---------- véhicules ----------

def _champs_vehicule(corps: dict, creation: bool, u: dict) -> dict:
    ag = str(corps.get("agence_id") or "").strip() or None
    if ag and not db.base().agences.find_one({"id": ag}):
        validation.erreur("Agence inconnue")
    d = {"marque": validation.texte(corps, "marque", "Marque", True, 40), "modele": validation.texte(corps, "modele", "Modèle", True, 40),
         "annee": int(validation.nombre(corps, "annee", "Année", 1980, date.today().year + 1) or 0) or None, "type": validation.choix(corps, "type", "Type", TYPES, "voiture"),
         "carburant": validation.choix(corps, "carburant", "Carburant", CARBURANTS, "essence"), "categorie_permis": validation.texte(corps, "categorie_permis", "Catégorie de permis préparée", False, 6).upper(),
         "numero_chassis": validation.texte(corps, "numero_chassis", "N° de châssis", False, 30), "agence_id": ag, "moniteur_login": validation.texte(corps, "moniteur_login", "Moniteur attitré", False, 40) or None,
         "date_achat": validation.date_iso(corps, "date_achat", "Date d'achat"), "intervalle_entretien_km": int(validation.nombre(corps, "intervalle_entretien_km", "Intervalle d'entretien (km)", 500, 100000) or 10000),
         "notes": validation.texte(corps, "notes", "Notes", False, 300)}
    for cle, lib in ECHEANCES.items():
        d[cle] = validation.date_iso(corps, cle, lib)
    if _couts_visibles(u):
        prix = validation.nombre(corps, "prix_achat", "Prix d'achat", 0, 10_000_000_000)
        if prix is not None:
            d["prix_achat"] = arrondi(prix)
    return d


@routeur.get("/parc/vehicules")
def lister(statut: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    """Véhicules (un compte d'agence ne voit que ceux de son agence ou sans agence), avec le nombre de pannes ouvertes et les échéances proches."""
    f: dict = {"statut": statut} if statut else {}
    if u["agence_id"]:
        f["agence_id"] = {"$in": [None, "", u["agence_id"]]}
    veh = list(db.base().vehicules.find(f, {"_id": 0}).sort("immatriculation", 1))
    ouvertes: dict = {}
    for p in db.base().pannes.find({"statut": {"$ne": "resolue"}}, {"vehicule_id": 1}):
        ouvertes[p["vehicule_id"]] = ouvertes.get(p["vehicule_id"], 0) + 1
    limite = (date.today() + timedelta(days=JOURS_ALERTE)).isoformat()
    out = []
    for v in veh:
        proches = [ECHEANCES[c] for c in ECHEANCES if v.get(c) and v[c] <= limite]
        out.append(_masquer({**_public(v), "statut_libelle": STATUTS[v["statut"]], "type_libelle": TYPES.get(v["type"], ""), "pannes_ouvertes": ouvertes.get(v["id"], 0), "echeances_proches": proches}, u))
    return out


@routeur.post("/parc/vehicules")
def creer(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Nouveau véhicule (immatriculation unique dans l'école)."""
    immat = validation.texte(corps, "immatriculation", "Immatriculation", True, 20).upper().replace(" ", "")
    if db.base().vehicules.find_one({"immatriculation": immat}):
        raise HTTPException(409, "Cette immatriculation existe déjà")
    km = int(validation.nombre(corps, "km_actuel", "Kilométrage actuel", 0, 5_000_000) or 0)
    v = {"id": str(uuid.uuid4()), "immatriculation": immat, "statut": "en_service", "km_actuel": km, "cree_le": db.maintenant(), **_champs_vehicule(corps, True, u)}
    db.base().vehicules.insert_one(v)
    if km:
        db.base().releves_km.insert_one({"id": str(uuid.uuid4()), "vehicule_id": v["id"], "date": date.today().isoformat(), "km": km, "motif": "Kilométrage initial", "par": u["login"], "cree_le": db.maintenant()})
    journaliser("vehicule_cree", u, immat)
    return _masquer(_public(v), u)


@routeur.put("/parc/vehicules/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Modifie la fiche (le kilométrage passe par ses relevés) ; `statut` = en_service, en_maintenance ou reforme (« en panne » est posé par les pannes)."""
    v = _vehicule(id_, u)
    maj = _champs_vehicule({**v, **corps}, False, u)
    if "statut" in corps:
        s = validation.choix(corps, "statut", "Statut", ["en_service", "en_maintenance", "reforme"], obligatoire=True)
        if s == "en_service" and db.base().pannes.find_one({"vehicule_id": id_, "statut": {"$ne": "resolue"}, "gravite": "immobilisante"}):
            raise HTTPException(409, "Une panne immobilisante est encore ouverte")
        maj["statut"] = s
    db.base().vehicules.update_one({"id": id_}, {"$set": maj})
    journaliser("vehicule_modifie", u, v["immatriculation"])
    return _masquer(_public(db.base().vehicules.find_one({"id": id_})), u)


# ---------- kilométrage ----------

@routeur.post("/parc/vehicules/{id_}/km")
def releve_km(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.SAISIE_TERRAIN))):
    """Relevé de kilométrage : jamais inférieur au dernier (409) ; un responsable peut corriger avec `correction` + motif."""
    v = _vehicule(id_, u)
    km = validation.nombre(corps, "km", "Kilométrage", 0, 5_000_000)
    if km is None:
        validation.erreur("Kilométrage : obligatoire")
    km = int(km)
    if km < v["km_actuel"]:
        if not (corps.get("correction") and u["role"] in roles.GESTION and str(corps.get("motif") or "").strip()):
            raise HTTPException(409, f"Le kilométrage ne peut pas reculer (dernier relevé : {v['km_actuel']} km). Un responsable peut corriger avec un motif.")
    r = {"id": str(uuid.uuid4()), "vehicule_id": id_, "date": validation.date_iso(corps, "date", "Date", False, futur_ok=False) or date.today().isoformat(), "km": km,
         "motif": validation.texte(corps, "motif", "Motif", False, 120), "par": u["login"], "correction": km < v["km_actuel"], "cree_le": db.maintenant()}
    db.base().releves_km.insert_one(r)
    db.base().vehicules.update_one({"id": id_}, {"$set": {"km_actuel": km}})
    journaliser("km_correction" if r["correction"] else "km_releve", u, f"{v['immatriculation']} {km}")
    return _public(r)


@routeur.get("/parc/vehicules/{id_}/km")
def historique_km(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    _vehicule(id_, u)
    return [_public(r) for r in db.base().releves_km.find({"vehicule_id": id_}, {"_id": 0}).sort([("date", -1), ("cree_le", -1)]).limit(200)]


# ---------- carburant ----------

def _consommations(pleins: list[dict]) -> list[dict]:
    """Ajoute à chaque plein COMPLET sa consommation (L/100 km) depuis le plein complet précédent ; marque les anomalies (> moyenne × 1,4). Liste en ordre chronologique."""
    complets = [p for p in pleins if p.get("plein_complet")]
    conso = {}
    for prec, p in zip(complets, complets[1:]):
        km = p["km"] - prec["km"]
        if km > 0:
            conso[p["id"]] = round(p["litres"] * 100 / km, 2)
    moyenne = sum(conso.values()) / len(conso) if conso else None
    return [{**p, "conso_100km": conso.get(p["id"]), "anomalie": bool(moyenne and conso.get(p["id"]) and conso[p["id"]] > moyenne * SEUIL_ANOMALIE)} for p in pleins]


@routeur.post("/parc/vehicules/{id_}/pleins")
def plein(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.SAISIE_TERRAIN))):
    """Approvisionnement en carburant : litres, montant (ou prix au litre), kilométrage au compteur (≥ dernier relevé, mis à jour), station, plein complet ou non."""
    v = _vehicule(id_, u)
    litres = validation.nombre(corps, "litres", "Litres", 0.5, 2000)
    km = validation.nombre(corps, "km", "Kilométrage au compteur", 0, 5_000_000)
    if litres is None or km is None:
        validation.erreur("Litres et kilométrage : obligatoires")
    if int(km) < v["km_actuel"]:
        raise HTTPException(409, f"Le kilométrage ne peut pas reculer (dernier relevé : {v['km_actuel']} km)")
    montant = validation.nombre(corps, "montant", "Montant", 0, 100_000_000)
    prix_l = validation.nombre(corps, "prix_litre", "Prix au litre", 0, 100_000)
    if montant is None and prix_l is not None:
        montant = prix_l * litres
    p = {"id": str(uuid.uuid4()), "vehicule_id": id_, "date": validation.date_iso(corps, "date", "Date", False, futur_ok=False) or date.today().isoformat(), "litres": litres, "km": int(km),
         "montant": arrondi(montant) if montant is not None else None, "station": validation.texte(corps, "station", "Station", False, 80), "plein_complet": bool(corps.get("plein_complet", True)),
         "par": u["login"], "cree_le": db.maintenant()}
    db.base().pleins.insert_one(p)
    if p["km"] > v["km_actuel"]:
        db.base().vehicules.update_one({"id": id_}, {"$set": {"km_actuel": p["km"]}})
        db.base().releves_km.insert_one({"id": str(uuid.uuid4()), "vehicule_id": id_, "date": p["date"], "km": p["km"], "motif": "Plein de carburant", "par": u["login"], "cree_le": db.maintenant()})
    journaliser("plein_enregistre", u, f"{v['immatriculation']} {litres} L")
    return _masquer(_public(p), u)


@routeur.get("/parc/vehicules/{id_}/pleins")
def lister_pleins(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    """Pleins du véhicule (récents d'abord) avec consommation et anomalies ; moyenne de consommation."""
    _vehicule(id_, u)
    chrono = list(db.base().pleins.find({"vehicule_id": id_}, {"_id": 0}).sort([("date", 1), ("km", 1)]))
    lignes = _consommations(chrono)
    cs = [p["conso_100km"] for p in lignes if p["conso_100km"]]
    return {"pleins": [_masquer(_public(p), u) for p in reversed(lignes)], "conso_moyenne": round(sum(cs) / len(cs), 2) if cs else None, "litres_total": round(sum(p["litres"] for p in lignes), 1)}


# ---------- pannes ----------

@routeur.post("/parc/vehicules/{id_}/pannes")
def declarer_panne(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.SAISIE_TERRAIN))):
    """Signalement d'une panne (moniteur, mécanicien…). Immobilisante : le véhicule passe « en panne »."""
    v = _vehicule(id_, u)
    p = {"id": str(uuid.uuid4()), "vehicule_id": id_, "date": validation.date_iso(corps, "date", "Date", False, futur_ok=False) or date.today().isoformat(), "description": validation.texte(corps, "description", "Description", True, 300),
         "gravite": validation.choix(corps, "gravite", "Gravité", GRAVITES, "mineure"), "statut": "ouverte", "km": v["km_actuel"], "signale_par": u["nom"], "cree_le": db.maintenant()}
    db.base().pannes.insert_one(p)
    if p["gravite"] == "immobilisante" and v["statut"] == "en_service":
        db.base().vehicules.update_one({"id": id_}, {"$set": {"statut": "en_panne"}})
    journaliser("panne_declaree", u, f"{v['immatriculation']} {p['gravite']}")
    return _public(p)


def _liberer_si_possible(vehicule_id: str) -> None:
    """Le véhicule « en panne » redevient « en service » quand plus aucune panne immobilisante n'est ouverte."""
    if not db.base().pannes.find_one({"vehicule_id": vehicule_id, "statut": {"$ne": "resolue"}, "gravite": "immobilisante"}):
        db.base().vehicules.update_one({"id": vehicule_id, "statut": "en_panne"}, {"$set": {"statut": "en_service"}})


@routeur.get("/parc/pannes")
def lister_pannes(statut: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    """Pannes de tout le parc (ouvertes d'abord), avec l'immatriculation."""
    f = {"statut": statut} if statut else {}
    veh = {v["id"]: v for v in db.base().vehicules.find({}, {"id": 1, "immatriculation": 1, "agence_id": 1})}
    out = [{**_public(p), "immatriculation": veh.get(p["vehicule_id"], {}).get("immatriculation", "")} for p in db.base().pannes.find(f, {"_id": 0}).sort("date", -1).limit(500)
           if not u["agence_id"] or veh.get(p["vehicule_id"], {}).get("agence_id") in (None, "", u["agence_id"])]
    out.sort(key=lambda p: p["statut"] == "resolue")
    return out


@routeur.put("/parc/pannes/{id_}")
def modifier_panne(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Prend en charge (en_cours) ou résout une panne (cause et résolution notées) ; libère le véhicule si possible."""
    p = db.base().pannes.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Panne introuvable")
    s = validation.choix(corps, "statut", "Statut", ["ouverte", "en_cours", "resolue"], obligatoire=True)
    maj = {"statut": s, "cause": validation.texte(corps, "cause", "Cause", False, 200), "resolution": validation.texte(corps, "resolution", "Résolution", False, 300)}
    if s == "resolue":
        maj["resolue_le"] = date.today().isoformat()
    db.base().pannes.update_one({"id": id_}, {"$set": maj})
    if s == "resolue":
        _liberer_si_possible(p["vehicule_id"])
    journaliser("panne_mise_a_jour", u, f"{p['description'][:60]} → {s}")
    return _public(db.base().pannes.find_one({"id": id_}))


# ---------- interventions ----------

@routeur.post("/parc/vehicules/{id_}/interventions")
def creer_intervention(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Planifie une intervention (entretien, réparation, contrôle) éventuellement liée à une panne, avec les pièces prévues (liste {piece_id, quantite}) ; rien n'est décompté avant la fin."""
    v = _vehicule(id_, u)
    pieces = []
    for x in corps.get("pieces") or []:
        pc = db.base().pieces.find_one({"id": str(x.get("piece_id") or "")})
        q = validation.nombre({"q": x.get("quantite")}, "q", "Quantité", 0.01, 100000)
        if not pc or q is None:
            validation.erreur("Pièce inconnue ou quantité manquante")
        pieces.append({"piece_id": pc["id"], "reference": pc["reference"], "designation": pc["designation"], "quantite": q})
    panne = str(corps.get("panne_id") or "") or None
    if panne and not db.base().pannes.find_one({"id": panne, "vehicule_id": id_}):
        validation.erreur("Panne inconnue pour ce véhicule")
    i = {"id": str(uuid.uuid4()), "vehicule_id": id_, "immatriculation": v["immatriculation"], "type": validation.choix(corps, "type", "Type", TYPES_INTERVENTION, "entretien"), "panne_id": panne,
         "description": validation.texte(corps, "description", "Description", True, 300), "date": validation.date_iso(corps, "date", "Date prévue") or date.today().isoformat(), "pieces": pieces,
         "prestataire": validation.texte(corps, "prestataire", "Prestataire (garage, mécanicien)", False, 80), "statut": "planifiee", "cree_le": db.maintenant(), "cree_par": u["login"]}
    db.base().interventions.insert_one(i)
    journaliser("intervention_creee", u, f"{v['immatriculation']} {i['type']}")
    return _masquer(_public(i), u)


@routeur.get("/parc/interventions")
def lister_interventions(statut: str = "", vehicule_id: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    f: dict = {}
    if statut:
        f["statut"] = statut
    if vehicule_id:
        f["vehicule_id"] = vehicule_id
    return [_masquer(_public(i), u) for i in db.base().interventions.find(f, {"_id": 0}).sort("date", -1).limit(500)]


@routeur.post("/parc/interventions/{id_}/demarrer")
def demarrer(id_: str, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Démarre l'intervention : le véhicule passe « en maintenance » (refusé s'il est réformé)."""
    i = db.base().interventions.find_one({"id": id_})
    if not i or i["statut"] != "planifiee":
        raise HTTPException(409, "Intervention introuvable ou déjà démarrée")
    v = _vehicule(i["vehicule_id"], u)
    if v["statut"] == "reforme":
        raise HTTPException(409, "Véhicule réformé")
    db.base().interventions.update_one({"id": id_}, {"$set": {"statut": "en_cours", "demarree_le": db.maintenant()}})
    db.base().vehicules.update_one({"id": v["id"]}, {"$set": {"statut": "en_maintenance"}})
    journaliser("intervention_demarree", u, v["immatriculation"])
    return {"ok": True}


@routeur.post("/parc/interventions/{id_}/terminer")
def terminer(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """
    Termine l'intervention : décompte les pièces du stock (409 si le stock d'une pièce est insuffisant : rien n'est décompté), calcule le coût (main-d'œuvre + pièces au dernier prix),
    résout la panne liée, remet le véhicule « en service » et programme le prochain entretien (km et date) s'il s'agit d'un entretien.
    """
    i = db.base().interventions.find_one({"id": id_})
    if not i or i["statut"] not in ("planifiee", "en_cours"):
        raise HTTPException(409, "Intervention introuvable ou déjà terminée")
    v = _vehicule(i["vehicule_id"], u)
    manques = [f"{x['designation']} (stock {pc['stock']}, besoin {x['quantite']})" for x in i["pieces"] if (pc := db.base().pieces.find_one({"id": x["piece_id"]})) and pc["stock"] < x["quantite"]]
    if manques:
        raise HTTPException(409, "Stock insuffisant : " + " ; ".join(manques))
    cout_pieces = 0
    for x in i["pieces"]:
        pc = db.base().pieces.find_one({"id": x["piece_id"]})
        cout_pieces += (pc.get("prix_unitaire") or 0) * x["quantite"]
        db.base().pieces.update_one({"id": pc["id"]}, {"$inc": {"stock": -x["quantite"]}})
        db.base().mouvements_pieces.insert_one({"id": str(uuid.uuid4()), "piece_id": pc["id"], "type": "sortie", "quantite": x["quantite"], "date": date.today().isoformat(), "intervention_id": id_,
                                                "cout_unitaire": pc.get("prix_unitaire"), "par": u["login"], "cree_le": db.maintenant()})
    mo = arrondi(validation.nombre(corps, "cout_main_oeuvre", "Coût de main-d'œuvre", 0, 100_000_000) or 0)
    km = validation.nombre(corps, "km", "Kilométrage", 0, 5_000_000)
    km = int(km) if km is not None else v["km_actuel"]
    maj = {"statut": "terminee", "terminee_le": db.maintenant(), "date_fin": date.today().isoformat(), "km": km, "cout_main_oeuvre": mo, "cout_pieces": arrondi(cout_pieces), "cout_total": arrondi(mo + cout_pieces),
           "compte_rendu": validation.texte(corps, "compte_rendu", "Compte rendu", False, 400)}
    db.base().interventions.update_one({"id": id_}, {"$set": maj})
    vmaj: dict = {"km_actuel": max(km, v["km_actuel"])}
    if i["type"] == "entretien":
        vmaj.update({"dernier_entretien_km": km, "dernier_entretien_date": date.today().isoformat()})
    if v["statut"] == "en_maintenance":
        vmaj["statut"] = "en_service"
    db.base().vehicules.update_one({"id": v["id"]}, {"$set": vmaj})
    if i.get("panne_id"):
        db.base().pannes.update_one({"id": i["panne_id"]}, {"$set": {"statut": "resolue", "resolue_le": date.today().isoformat(), "resolution": i["description"][:300]}})
        _liberer_si_possible(v["id"])
    journaliser("intervention_terminee", u, f"{v['immatriculation']} {i['type']}")
    return _masquer(_public(db.base().interventions.find_one({"id": id_})), u)


@routeur.post("/parc/interventions/{id_}/annuler")
def annuler_intervention(id_: str, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Annule une intervention non terminée (le véhicule en maintenance est remis en service)."""
    i = db.base().interventions.find_one({"id": id_})
    if not i or i["statut"] in ("terminee", "annulee"):
        raise HTTPException(409, "Intervention introuvable ou déjà clôturée")
    db.base().interventions.update_one({"id": id_}, {"$set": {"statut": "annulee"}})
    db.base().vehicules.update_one({"id": i["vehicule_id"], "statut": "en_maintenance"}, {"$set": {"statut": "en_service"}})
    return {"ok": True}


# ---------- alertes et coûts ----------

def calculer_alertes(u: dict) -> list[dict]:
    """Échéances de documents (expirées ou dans 30 jours), entretien dû (km ou 12 mois), pannes ouvertes, pièces sous le seuil, consommations anormales. Lectures en bloc."""
    auj = date.today().isoformat()
    limite = (date.today() + timedelta(days=JOURS_ALERTE)).isoformat()
    f: dict = {"statut": {"$ne": "reforme"}}
    if u["agence_id"]:
        f["agence_id"] = {"$in": [None, "", u["agence_id"]]}
    veh = list(db.base().vehicules.find(f, {"_id": 0}))
    al = []
    for v in veh:
        for c, lib in ECHEANCES.items():
            if v.get(c) and v[c] <= limite:
                al.append({"niveau": "rouge" if v[c] < auj else "orange", "type": "echeance", "vehicule_id": v["id"], "immatriculation": v["immatriculation"],
                           "message": f"{lib} {'expirée' if v[c] < auj else 'expire'} le {v[c]}"})
        derniers = v.get("dernier_entretien_km", 0)
        if v["km_actuel"] - derniers >= v["intervalle_entretien_km"] and v["km_actuel"] > 0:
            al.append({"niveau": "orange", "type": "entretien", "vehicule_id": v["id"], "immatriculation": v["immatriculation"], "message": f"Entretien dû ({v['km_actuel'] - derniers} km depuis le dernier, intervalle {v['intervalle_entretien_km']} km)"})
    ids = {v["id"]: v for v in veh}
    for p in db.base().pannes.find({"statut": {"$ne": "resolue"}, "vehicule_id": {"$in": list(ids)}}):
        al.append({"niveau": "rouge" if p["gravite"] == "immobilisante" else "orange", "type": "panne", "vehicule_id": p["vehicule_id"], "immatriculation": ids[p["vehicule_id"]]["immatriculation"], "message": f"Panne {p['gravite']} : {p['description'][:80]}"})
    for pc in db.base().pieces.find({"actif": {"$ne": False}}):
        if pc["stock"] <= pc.get("seuil_alerte", 0) and pc.get("seuil_alerte", 0) > 0:
            al.append({"niveau": "rouge" if pc["stock"] <= 0 else "orange", "type": "stock", "vehicule_id": None, "immatriculation": "", "message": f"Pièce {pc['designation']} : stock {pc['stock']} (seuil {pc['seuil_alerte']})"})
    par_veh: dict = {}
    for p in db.base().pleins.find({"vehicule_id": {"$in": list(ids)}}, {"_id": 0}).sort([("date", 1), ("km", 1)]):
        par_veh.setdefault(p["vehicule_id"], []).append(p)
    limite_conso = (date.today() - timedelta(days=60)).isoformat()
    for vid, pl in par_veh.items():
        for p in _consommations(pl):
            if p["anomalie"] and p["date"] >= limite_conso:
                al.append({"niveau": "orange", "type": "carburant", "vehicule_id": vid, "immatriculation": ids[vid]["immatriculation"], "message": f"Consommation anormale le {p['date']} : {p['conso_100km']} L/100 km"})
    ordre = {"rouge": 0, "orange": 1}
    return sorted(al, key=lambda a: ordre[a["niveau"]])


@routeur.get("/parc/alertes")
def alertes(u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    """Alertes du parc triées par gravité (rouge puis orange)."""
    return calculer_alertes(u)


@routeur.get("/parc/synthese")
def synthese(mois: str = "", u: dict = Depends(exiger_roles(roles.COUTS_PARC))):
    """
    Coûts du parc : par véhicule (carburant + interventions terminées + pièces), coût au km sur la période. `mois` AAAA-MM (tous les mois si vide).
    Réservé à la comptabilité, au mécanicien et aux responsables.
    """
    ok = (lambda d: d.startswith(mois)) if mois else (lambda d: True)
    veh = list(db.base().vehicules.find({}, {"_id": 0, "id": 1, "immatriculation": 1, "marque": 1, "modele": 1, "km_actuel": 1}))
    carb: dict = {}
    litres: dict = {}
    for p in db.base().pleins.find({}, {"vehicule_id": 1, "montant": 1, "litres": 1, "date": 1}):
        if ok(p["date"]):
            carb[p["vehicule_id"]] = carb.get(p["vehicule_id"], 0) + (p.get("montant") or 0)
            litres[p["vehicule_id"]] = litres.get(p["vehicule_id"], 0) + p["litres"]
    maint: dict = {}
    for i in db.base().interventions.find({"statut": "terminee"}, {"vehicule_id": 1, "cout_total": 1, "date_fin": 1}):
        if ok(i.get("date_fin") or ""):
            maint[i["vehicule_id"]] = maint.get(i["vehicule_id"], 0) + (i.get("cout_total") or 0)
    km: dict = {}
    for r in db.base().releves_km.find({}, {"vehicule_id": 1, "km": 1, "date": 1}).sort("date", 1):
        if ok(r["date"]):
            a = km.setdefault(r["vehicule_id"], [r["km"], r["km"]])
            a[0], a[1] = min(a[0], r["km"]), max(a[1], r["km"])
    lignes = []
    for v in veh:
        c, m = arrondi(carb.get(v["id"], 0)), arrondi(maint.get(v["id"], 0))
        parcourus = (km[v["id"]][1] - km[v["id"]][0]) if v["id"] in km else 0
        lignes.append({**v, "carburant": c, "litres": round(litres.get(v["id"], 0), 1), "maintenance": m, "total": arrondi(c + m), "km_periode": parcourus, "cout_au_km": arrondi((c + m) / parcourus) if parcourus else None})
    return {"mois": mois, "vehicules": lignes, "total_carburant": arrondi(sum(l["carburant"] for l in lignes)), "total_maintenance": arrondi(sum(l["maintenance"] for l in lignes))}
