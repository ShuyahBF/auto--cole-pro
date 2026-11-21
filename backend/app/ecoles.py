"""
AUTO-ÉCOLES (locataires de la plateforme) et AGENCES (sites d'une auto-école), avec leur PARAMÉTRAGE : pays et devise, catégories de permis, épreuves d'examen,
pièces à fournir, modes de paiement. Tout est paramétrable par école : rien n'est figé pour un pays (les valeurs proposées par pays sont des POINTS DE DÉPART à valider
par l'auto-école selon la réglementation en vigueur chez elle).

Droits : le super administrateur crée et active les auto-écoles ; le directeur règle SON école et ses agences.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, securite, validation
from .auth import exiger_roles, journaliser, utilisateur_courant

routeur = APIRouter()

# Points de départ par pays (devise, nombre de décimales, indicatif téléphonique). Le directeur peut tout modifier.
PAYS = {
    "BF": {"nom": "Burkina Faso", "devise": "FCFA", "decimales": 0, "indicatif": "226"},
    "CI": {"nom": "Côte d'Ivoire", "devise": "FCFA", "decimales": 0, "indicatif": "225"},
    "SN": {"nom": "Sénégal", "devise": "FCFA", "decimales": 0, "indicatif": "221"},
    "ML": {"nom": "Mali", "devise": "FCFA", "decimales": 0, "indicatif": "223"},
    "NE": {"nom": "Niger", "devise": "FCFA", "decimales": 0, "indicatif": "227"},
    "TG": {"nom": "Togo", "devise": "FCFA", "decimales": 0, "indicatif": "228"},
    "BJ": {"nom": "Bénin", "devise": "FCFA", "decimales": 0, "indicatif": "229"},
    "CM": {"nom": "Cameroun", "devise": "FCFA", "decimales": 0, "indicatif": "237"},
    "GA": {"nom": "Gabon", "devise": "FCFA", "decimales": 0, "indicatif": "241"},
    "FR": {"nom": "France", "devise": "EUR", "decimales": 2, "indicatif": "33"},
    "MA": {"nom": "Maroc", "devise": "MAD", "decimales": 2, "indicatif": "212"},
    "TN": {"nom": "Tunisie", "devise": "TND", "decimales": 3, "indicatif": "216"},
}
CATEGORIES_PAR_DEFAUT = [
    {"code": "A1", "libelle": "Motocyclette légère", "age_min": 16}, {"code": "A", "libelle": "Motocyclette", "age_min": 18},
    {"code": "B", "libelle": "Voiture de tourisme", "age_min": 18}, {"code": "BE", "libelle": "Voiture avec remorque", "age_min": 18},
    {"code": "C", "libelle": "Poids lourd", "age_min": 21}, {"code": "CE", "libelle": "Poids lourd avec remorque", "age_min": 21},
    {"code": "D", "libelle": "Transport en commun", "age_min": 21},
]
EPREUVES_PAR_DEFAUT = [{"code": "code", "libelle": "Épreuve théorique (code de la route)"}, {"code": "conduite", "libelle": "Épreuve pratique (conduite)"}]
PIECES_PAR_DEFAUT = [
    {"cle": "identite", "libelle": "Pièce d'identité", "obligatoire": True}, {"cle": "photos", "libelle": "Photos d'identité", "obligatoire": True},
    {"cle": "naissance", "libelle": "Extrait d'acte de naissance", "obligatoire": True}, {"cle": "medical", "libelle": "Certificat médical", "obligatoire": True},
    {"cle": "residence", "libelle": "Justificatif de résidence", "obligatoire": False}, {"cle": "autorisation", "libelle": "Autorisation parentale (mineur)", "obligatoire": False},
]
MODES_PAR_DEFAUT = [{"cle": "especes", "libelle": "Espèces"}, {"cle": "mobile_money", "libelle": "Mobile money"}, {"cle": "virement", "libelle": "Virement"},
                    {"cle": "cheque", "libelle": "Chèque"}, {"cle": "carte", "libelle": "Carte bancaire"}]
CHAMPS_PRESENTATION = [("nom", "Nom de l'auto-école", True, 80), ("telephone", "Téléphone", False, 40), ("email", "E-mail", False, 120), ("adresse", "Adresse", False, 160),
                       ("ville", "Ville", False, 80), ("identifiant_fiscal", "IFU / RCCM", False, 60), ("agrement", "N° d'agrément", False, 60), ("responsable", "Responsable", False, 80)]


def _public(e: dict) -> dict:
    return {k: v for k, v in e.items() if k != "_id"}


def _liste_de_dicts(corps: dict, cle: str, libelle: str, requis: list[str], maximum: int = 40) -> list[dict] | None:
    """Liste de petits objets saisie dans l'écran (catégories, épreuves, pièces…) : None si absente du corps ; erreur 422 si mal formée."""
    if cle not in corps:
        return None
    v = corps[cle]
    if not isinstance(v, list) or len(v) > maximum:
        validation.erreur(f"{libelle} : une liste de {maximum} éléments au plus est attendue")
    propres = []
    for x in v:
        if not isinstance(x, dict) or any(not str(x.get(r) or "").strip() for r in requis[:2]):
            validation.erreur(f"{libelle} : chaque ligne doit avoir un code et un libellé")
        propres.append(x)
    return propres


def _config_depuis_corps(corps: dict) -> dict:
    """Champs de paramétrage d'une école reçus dans le corps (présentation, catégories, épreuves, pièces, modes de paiement) : validés, nettoyés."""
    maj: dict = {}
    for cle, libelle, obligatoire, longueur in CHAMPS_PRESENTATION:
        if cle in corps:
            maj[cle] = validation.texte(corps, cle, libelle, obligatoire, longueur, majuscules=(cle == "nom"))   # intitulé de l'auto-école : MAJUSCULES
    cats = _liste_de_dicts(corps, "categories", "Catégories de permis", ["code", "libelle"])
    if cats is not None:
        vus = set()
        propres = []
        for c in cats:
            code = str(c["code"]).strip().upper()
            if not re.fullmatch(r"[A-Z0-9]{1,6}", code) or code in vus:
                validation.erreur(f"Catégorie « {code} » : code de 1 à 6 lettres ou chiffres, sans doublon")
            vus.add(code)
            age = validation.nombre({"a": c.get("age_min")}, "a", "Âge minimum", 14, 30)
            propres.append({"code": code, "libelle": str(c["libelle"]).strip()[:80], "age_min": int(age) if age else 18})
        maj["categories"] = propres
    epr = _liste_de_dicts(corps, "epreuves", "Épreuves d'examen", ["code", "libelle"], 12)
    if epr is not None:
        vus = set()
        propres = []
        for e in epr:
            code = re.sub(r"[^a-z0-9_]", "", validation.normaliser(e["code"]).replace(" ", "_"))[:20]
            if not code or code in vus:
                validation.erreur("Épreuve : code (lettres, chiffres, souligné) unique et obligatoire")
            vus.add(code)
            propres.append({"code": code, "libelle": str(e["libelle"]).strip()[:80]})
        maj["epreuves"] = propres
    pieces = _liste_de_dicts(corps, "pieces", "Pièces à fournir", ["cle", "libelle"], 30)
    if pieces is not None:
        vus = set()
        propres = []
        for p in pieces:
            cle = re.sub(r"[^a-z0-9_]", "", validation.normaliser(p["cle"]).replace(" ", "_"))[:30]
            if not cle or cle in vus:
                validation.erreur("Pièce : clé (lettres, chiffres, souligné) unique et obligatoire")
            vus.add(cle)
            propres.append({"cle": cle, "libelle": str(p["libelle"]).strip()[:80], "obligatoire": bool(p.get("obligatoire"))})
        maj["pieces"] = propres
    modes = _liste_de_dicts(corps, "modes_paiement", "Modes de paiement", ["cle", "libelle"], 12)
    if modes is not None:
        autorises = {m["cle"] for m in MODES_PAR_DEFAUT}
        maj["modes_paiement"] = [{"cle": m["cle"], "libelle": str(m["libelle"]).strip()[:60]} for m in modes if m["cle"] in autorises]
        if not maj["modes_paiement"]:
            validation.erreur("Modes de paiement : au moins un mode")
    if "operateurs_mobile" in corps:
        ops = corps["operateurs_mobile"]
        if not isinstance(ops, list) or len(ops) > 10:
            validation.erreur("Opérateurs de mobile money : 10 au plus")
        maj["operateurs_mobile"] = [str(o).strip()[:40] for o in ops if str(o).strip()]
    return maj


def _prefixe(corps: dict, id_actuel: str = "") -> str:
    """Préfixe des matricules (2 à 6 lettres ou chiffres, majuscules), unique sur la plateforme."""
    p = validation.texte(corps, "prefixe", "Préfixe des matricules", True, 6).upper()
    if not re.fullmatch(r"[A-Z0-9]{2,6}", p):
        validation.erreur("Préfixe : 2 à 6 lettres ou chiffres (exemple : EXC)")
    if db.brut().ecoles.find_one({"prefixe": p, "id": {"$ne": id_actuel}}):
        raise HTTPException(409, "Ce préfixe est déjà utilisé par une autre auto-école")
    return p


def creer_agence(nom: str, principale: bool = False, **plus) -> dict:
    """Crée une agence dans l'école courante."""
    a = {"id": str(uuid.uuid4()), "nom": nom, "ville": plus.get("ville", ""), "adresse": plus.get("adresse", ""), "telephone": plus.get("telephone", ""),
         "actif": True, "principale": principale, "cree_le": db.maintenant()}
    db.base().agences.insert_one(a)
    return a


@routeur.get("/ecoles/pays")
def lister_pays(u: dict = Depends(utilisateur_courant)):
    """Pays proposés (points de départ : devise, décimales, indicatif) pour la création d'une auto-école."""
    return [{"code": k, **v} for k, v in PAYS.items()]


@routeur.get("/ecoles")
def lister(u: dict = Depends(utilisateur_courant)):
    """Auto-écoles visibles : toutes pour le super administrateur (liste du sélecteur), la sienne seulement pour les autres."""
    if u["plateforme"]:
        return [_public(e) for e in db.brut().ecoles.find({}, {"_id": 0}).sort("nom", 1)]
    return [_public(e) for e in db.brut().ecoles.find({"id": u["ecole_id"]}, {"_id": 0})]


@routeur.post("/ecoles")
def creer(corps: dict, u: dict = Depends(exiger_roles(roles.SUPER_ADMIN))):
    """
    Crée une auto-école (super administrateur) avec son agence principale « Siège » et, si `directeur` est fourni {login, nom_affiche, mot_de_passe}, son premier directeur
    (mot de passe provisoire à changer à la première connexion).
    """
    pays = validation.choix(corps, "pays", "Pays", PAYS, obligatoire=True)
    base_pays = PAYS[pays]
    e = {"id": str(uuid.uuid4()), "prefixe": _prefixe(corps), "pays": pays, "devise": base_pays["devise"], "decimales": base_pays["decimales"], "indicatif": base_pays["indicatif"],
         "actif": True, "cree_le": db.maintenant(), "categories": CATEGORIES_PAR_DEFAUT, "epreuves": EPREUVES_PAR_DEFAUT, "pieces": PIECES_PAR_DEFAUT,
         "modes_paiement": MODES_PAR_DEFAUT, "operateurs_mobile": [], **{k: "" for k, *_ in CHAMPS_PRESENTATION}}
    e.update(_config_depuis_corps(corps))
    if "devise" in corps:
        e["devise"] = validation.texte(corps, "devise", "Devise", False, 8).upper() or e["devise"]
    directeur = corps.get("directeur")
    if directeur:
        login = validation.texte(directeur, "login", "Identifiant du directeur", True, 40).lower()
        mdp = str(directeur.get("mot_de_passe", ""))
        if not securite.mot_de_passe_assez_fort(mdp):
            validation.erreur("Mot de passe provisoire du directeur : 8 caractères au moins, avec une lettre et un chiffre")
        if db.brut().utilisateurs.find_one({"login": login}):
            raise HTTPException(409, "Cet identifiant existe déjà")
    db.brut().ecoles.insert_one(e)
    ancien = db.ecole_courante.get()
    db.fixer_ecole(e["id"])                                  # le temps de créer l'agence principale DANS la nouvelle école
    try:
        creer_agence("SIÈGE", principale=True, ville=e.get("ville", ""))
    finally:
        db.fixer_ecole(ancien)
    if directeur:
        db.brut().utilisateurs.insert_one({"id": str(uuid.uuid4()), "login": login, "nom_affiche": validation.texte(directeur, "nom_affiche", "Nom du directeur", True, 80),
                                           "role": roles.DIRECTEUR, "actif": True, "echecs": 0, "mot_de_passe_hash": securite.hacher_mot_de_passe(mdp),
                                           "doit_changer_mdp": True, "created_at": db.maintenant(), "ecole_id": e["id"], "agence_id": None})
    journaliser("ecole_creee", {**u, "ecole_id": e["id"]}, f"{e['nom']} ({e['prefixe']})")
    return _public(e)


@routeur.put("/ecoles/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.SUPER_ADMIN))):
    """Modifie une auto-école (super administrateur) : présentation, paramétrage, état actif ; le préfixe ne change plus après le premier élève."""
    e = db.brut().ecoles.find_one({"id": id_})
    if not e:
        raise HTTPException(404, "Auto-école introuvable")
    maj = _config_depuis_corps(corps)
    if "actif" in corps:
        maj["actif"] = bool(corps["actif"])
    if "prefixe" in corps and str(corps["prefixe"]).strip().upper() != e["prefixe"]:
        if db.brut().eleves.count_documents({"ecole_id": id_}, limit=1):
            raise HTTPException(409, "Le préfixe ne peut plus changer : des matricules existent déjà")
        maj["prefixe"] = _prefixe(corps, id_)
    if maj:
        db.brut().ecoles.update_one({"id": id_}, {"$set": maj})
        journaliser("ecole_modifiee", {**u, "ecole_id": id_}, ", ".join(sorted(maj)))
    return _public(db.brut().ecoles.find_one({"id": id_}))


@routeur.get("/ecole")
def mon_ecole(u: dict = Depends(utilisateur_courant)):
    """Fiche et paramétrage de l'auto-école de travail (catégories, épreuves, pièces, modes de paiement…)."""
    if not u["ecole_id"]:
        raise HTTPException(400, "Choisissez d'abord une auto-école")
    return _public(db.brut().ecoles.find_one({"id": u["ecole_id"]}))


@routeur.put("/ecole")
def modifier_mon_ecole(corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Le directeur règle SON auto-école (sauf préfixe, pays et état, réservés au super administrateur) ; la devise ne change plus après le premier paiement."""
    if not u["ecole_id"]:
        raise HTTPException(400, "Choisissez d'abord une auto-école")
    maj = _config_depuis_corps(corps)
    if "devise" in corps:
        devise = validation.texte(corps, "devise", "Devise", True, 8).upper()
        actuelle = db.brut().ecoles.find_one({"id": u["ecole_id"]})["devise"]
        if devise != actuelle:
            if db.base().paiements.count_documents({}, limit=1):
                raise HTTPException(409, "La devise ne peut plus changer : des paiements existent déjà")
            maj["devise"] = devise
    if maj:
        db.brut().ecoles.update_one({"id": u["ecole_id"]}, {"$set": maj})
        journaliser("ecole_reglee", u, ", ".join(sorted(maj)))
    return _public(db.brut().ecoles.find_one({"id": u["ecole_id"]}))


# ---------- agences ----------

@routeur.get("/agences")
def lister_agences(u: dict = Depends(utilisateur_courant)):
    """Agences de l'école ; un compte limité à une agence ne voit que la sienne."""
    f = {"id": u["agence_id"]} if u["agence_id"] else {}
    return [{k: v for k, v in a.items() if k not in ("_id", "ecole_id")} for a in db.base().agences.find(f, {"_id": 0}).sort([("principale", -1), ("nom", 1)])]


@routeur.post("/agences")
def creer_une_agence(corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Nouvelle agence (directeur)."""
    nom = validation.texte(corps, "nom", "Nom de l'agence", True, 80, majuscules=True)   # intitulé de l'agence : MAJUSCULES
    if db.base().agences.find_one({"nom": nom}):
        raise HTTPException(409, "Une agence porte déjà ce nom")
    a = creer_agence(nom, ville=validation.texte(corps, "ville", "Ville", False, 80), adresse=validation.texte(corps, "adresse", "Adresse", False, 160),
                     telephone=validation.texte(corps, "telephone", "Téléphone", False, 40))
    journaliser("agence_creee", u, nom)
    return {k: v for k, v in a.items() if k != "ecole_id"}


@routeur.put("/agences/{id_}")
def modifier_agence(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Modifie ou désactive une agence ; l'agence principale ne se désactive pas ; une agence qui a des élèves actifs ne se désactive pas."""
    a = db.base().agences.find_one({"id": id_})
    if not a:
        raise HTTPException(404, "Agence introuvable")
    maj = {}
    for cle, libelle, longueur in (("nom", "Nom", 80), ("ville", "Ville", 80), ("adresse", "Adresse", 160), ("telephone", "Téléphone", 40)):
        if cle in corps:
            maj[cle] = validation.texte(corps, cle, libelle, cle == "nom", longueur, majuscules=(cle == "nom"))
    if "actif" in corps and bool(corps["actif"]) != a.get("actif", True):
        if not corps["actif"] and (a.get("principale") or db.base().eleves.count_documents({"agence_id": id_, "statut": {"$in": ["inscrit", "en_formation", "pret_examen"]}}, limit=1)):
            raise HTTPException(409, "Cette agence est principale ou a encore des élèves en formation : elle ne peut pas être désactivée")
        maj["actif"] = bool(corps["actif"])
    if maj:
        db.base().agences.update_one({"id": id_}, {"$set": maj})
        journaliser("agence_modifiee", u, a["nom"])
    return {k: v for k, v in db.base().agences.find_one({"id": id_}).items() if k not in ("_id", "ecole_id")}
