"""
PIÈCES DÉTACHÉES, FOURNISSEURS et APPROVISIONNEMENT : catalogue de pièces (stock, seuil d'alerte, dernier prix), mouvements tracés (entrée, sortie, ajustement motivé),
fournisseurs, bons de commande (brouillon → commandé → reçu) dont la RÉCEPTION met à jour le stock et le prix, suggestions de réapprovisionnement.
Le stock ne devient jamais négatif. Les prix ne sont vus que par COUTS_PARC (le serveur les retire pour les autres rôles).
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from . import db, roles, validation
from .auth import exiger_roles, journaliser
from .parc import _couts_visibles, _masquer
from .tarifs import arrondi

routeur = APIRouter()
CATEGORIES = {"moteur": "Moteur", "freinage": "Freinage", "pneumatique": "Pneumatiques", "electricite": "Électricité", "transmission": "Transmission", "carrosserie": "Carrosserie",
              "filtration": "Filtres et fluides", "autre": "Autre"}
STATUTS_COMMANDE = {"brouillon": "Brouillon", "commandee": "Commandée", "recue": "Reçue", "annulee": "Annulée"}


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


# ---------- pièces ----------

@routeur.get("/parc/pieces")
def lister(sous_seuil: bool = False, q: str = "", u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    """Catalogue des pièces (recherche sur la référence ou la désignation) ; `sous_seuil` = pièces à réapprovisionner."""
    lignes = [_masquer({**_public(p), "categorie_libelle": CATEGORIES.get(p["categorie"], ""), "a_commander": p.get("seuil_alerte", 0) > 0 and p["stock"] <= p["seuil_alerte"]}, u)
              for p in db.base().pieces.find({}, {"_id": 0}).sort("designation", 1)]
    if q.strip():
        n = validation.normaliser(q)
        lignes = [p for p in lignes if n in validation.normaliser(p["designation"]) or n in validation.normaliser(p["reference"])]
    return [p for p in lignes if p["a_commander"]] if sous_seuil else lignes


@routeur.post("/parc/pieces")
def creer(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Nouvelle pièce (référence unique) ; un stock initial crée un mouvement d'entrée tracé."""
    ref = validation.texte(corps, "reference", "Référence", True, 40).upper()
    if db.base().pieces.find_one({"reference": ref}):
        raise HTTPException(409, "Cette référence existe déjà")
    stock = validation.nombre(corps, "stock", "Stock initial", 0, 1_000_000) or 0
    prix = validation.nombre(corps, "prix_unitaire", "Prix unitaire", 0, 1_000_000_000)
    p = {"id": str(uuid.uuid4()), "reference": ref, "designation": validation.texte(corps, "designation", "Désignation", True, 100), "categorie": validation.choix(corps, "categorie", "Catégorie", CATEGORIES, "autre"),
         "unite": validation.texte(corps, "unite", "Unité", False, 12) or "pièce", "stock": stock, "seuil_alerte": validation.nombre(corps, "seuil_alerte", "Seuil d'alerte", 0, 1_000_000) or 0,
         "prix_unitaire": arrondi(prix) if prix is not None and _couts_visibles(u) else None, "emplacement": validation.texte(corps, "emplacement", "Emplacement", False, 60), "actif": True, "cree_le": db.maintenant()}
    db.base().pieces.insert_one(p)
    if stock:
        db.base().mouvements_pieces.insert_one({"id": str(uuid.uuid4()), "piece_id": p["id"], "type": "entree", "quantite": stock, "date": date.today().isoformat(), "motif": "Stock initial", "par": u["login"], "cree_le": db.maintenant()})
    journaliser("piece_creee", u, ref)
    return _masquer(_public(p), u)


@routeur.put("/parc/pieces/{id_}")
def modifier(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Modifie désignation, catégorie, seuil, emplacement, prix, état (le stock passe par les mouvements)."""
    p = db.base().pieces.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Pièce introuvable")
    maj: dict = {}
    for cle, lib, lon in (("designation", "Désignation", 100), ("unite", "Unité", 12), ("emplacement", "Emplacement", 60)):
        if cle in corps:
            maj[cle] = validation.texte(corps, cle, lib, cle == "designation", lon)
    if "categorie" in corps:
        maj["categorie"] = validation.choix(corps, "categorie", "Catégorie", CATEGORIES, obligatoire=True)
    if "seuil_alerte" in corps:
        maj["seuil_alerte"] = validation.nombre(corps, "seuil_alerte", "Seuil d'alerte", 0, 1_000_000) or 0
    if "prix_unitaire" in corps and _couts_visibles(u):
        prix = validation.nombre(corps, "prix_unitaire", "Prix unitaire", 0, 1_000_000_000)
        maj["prix_unitaire"] = arrondi(prix) if prix is not None else None
    if "actif" in corps:
        maj["actif"] = bool(corps["actif"])
    if maj:
        db.base().pieces.update_one({"id": id_}, {"$set": maj})
    return _masquer(_public(db.base().pieces.find_one({"id": id_})), u)


@routeur.post("/parc/pieces/{id_}/mouvement")
def mouvement(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Mouvement manuel : entrée, sortie (ne descend jamais sous zéro) ou ajustement d'inventaire (motif obligatoire, quantité = nouveau stock)."""
    p = db.base().pieces.find_one({"id": id_})
    if not p:
        raise HTTPException(404, "Pièce introuvable")
    typ = validation.choix(corps, "type", "Type de mouvement", ["entree", "sortie", "ajustement"], obligatoire=True)
    q = validation.nombre(corps, "quantite", "Quantité", 0, 1_000_000)
    if q is None or (q == 0 and typ != "ajustement"):
        validation.erreur("Quantité : obligatoire")
    motif = validation.texte(corps, "motif", "Motif", typ == "ajustement", 160)
    delta = q if typ == "entree" else -q if typ == "sortie" else q - p["stock"]
    if p["stock"] + delta < 0:
        raise HTTPException(409, f"Stock insuffisant (disponible : {p['stock']})")
    db.base().pieces.update_one({"id": id_}, {"$inc": {"stock": delta}})
    db.base().mouvements_pieces.insert_one({"id": str(uuid.uuid4()), "piece_id": id_, "type": typ, "quantite": abs(delta) if typ == "ajustement" else q, "date": date.today().isoformat(), "motif": motif, "par": u["login"], "cree_le": db.maintenant()})
    journaliser("piece_mouvement", u, f"{p['reference']} {typ} {q}")
    return _masquer(_public(db.base().pieces.find_one({"id": id_})), u)


@routeur.get("/parc/pieces/{id_}/mouvements")
def mouvements(id_: str, u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    return [_masquer(_public(m), u, ("cout_unitaire",)) for m in db.base().mouvements_pieces.find({"piece_id": id_}, {"_id": 0}).sort([("date", -1), ("cree_le", -1)]).limit(300)]


# ---------- fournisseurs ----------

@routeur.get("/parc/fournisseurs")
def lister_fournisseurs(u: dict = Depends(exiger_roles(roles.LECTURE_PARC))):
    return [_public(f) for f in db.base().fournisseurs.find({}, {"_id": 0}).sort("nom", 1)]


@routeur.post("/parc/fournisseurs")
def creer_fournisseur(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    nom = validation.texte(corps, "nom", "Nom", True, 80)
    if db.base().fournisseurs.find_one({"nom": nom}):
        raise HTTPException(409, "Ce fournisseur existe déjà")
    f = {"id": str(uuid.uuid4()), "nom": nom, "telephone": validation.texte(corps, "telephone", "Téléphone", False, 30), "email": validation.texte(corps, "email", "E-mail", False, 120),
         "adresse": validation.texte(corps, "adresse", "Adresse", False, 160), "produits": validation.texte(corps, "produits", "Produits fournis", False, 200), "actif": True, "cree_le": db.maintenant()}
    db.base().fournisseurs.insert_one(f)
    journaliser("fournisseur_cree", u, nom)
    return _public(f)


@routeur.put("/parc/fournisseurs/{id_}")
def modifier_fournisseur(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    f = db.base().fournisseurs.find_one({"id": id_})
    if not f:
        raise HTTPException(404, "Fournisseur introuvable")
    maj = {c: validation.texte(corps, c, c, c == "nom", 200) for c in ("nom", "telephone", "email", "adresse", "produits") if c in corps}
    if "actif" in corps:
        maj["actif"] = bool(corps["actif"])
    if maj:
        db.base().fournisseurs.update_one({"id": id_}, {"$set": maj})
    return _public(db.base().fournisseurs.find_one({"id": id_}))


# ---------- approvisionnement ----------

@routeur.get("/parc/suggestions")
def suggestions(u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Pièces à réapprovisionner : quantité conseillée = 2 × seuil − stock (de quoi couvrir le double du seuil). Une suggestion AIDE à commander, elle ne commande rien."""
    return [_masquer({"piece_id": p["id"], "reference": p["reference"], "designation": p["designation"], "stock": p["stock"], "seuil_alerte": p["seuil_alerte"], "quantite_conseillee": arrondi(2 * p["seuil_alerte"] - p["stock"]),
                      "prix_unitaire": p.get("prix_unitaire")}, u) for p in db.base().pieces.find({"actif": {"$ne": False}, "seuil_alerte": {"$gt": 0}}).sort("designation", 1) if p["stock"] <= p["seuil_alerte"]]


def _lignes_commande(corps: dict) -> list[dict]:
    lignes = []
    for x in corps.get("lignes") or []:
        p = db.base().pieces.find_one({"id": str(x.get("piece_id") or "")})
        q = validation.nombre({"q": x.get("quantite")}, "q", "Quantité", 0.01, 1_000_000)
        prix = validation.nombre({"p": x.get("prix_unitaire")}, "p", "Prix unitaire", 0, 1_000_000_000)
        if not p or q is None:
            validation.erreur("Ligne de commande : pièce et quantité obligatoires")
        lignes.append({"piece_id": p["id"], "reference": p["reference"], "designation": p["designation"], "quantite": q, "prix_unitaire": arrondi(prix) if prix is not None else p.get("prix_unitaire") or 0})
    if not lignes:
        validation.erreur("Une commande contient au moins une ligne")
    return lignes


def _total(lignes: list[dict]) -> float:
    return arrondi(sum(l["quantite"] * l["prix_unitaire"] for l in lignes))


@routeur.get("/parc/commandes")
def lister_commandes(statut: str = "", u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    return [{**_public(c), "statut_libelle": STATUTS_COMMANDE[c["statut"]]} for c in db.base().commandes.find({"statut": statut} if statut else {}, {"_id": 0}).sort("date_commande", -1).limit(300)]


@routeur.post("/parc/commandes")
def creer_commande(corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """Bon de commande en brouillon (numéro C-AAAA-000001) chez un fournisseur actif ; `envoyer` le passe directement « commandée »."""
    f = db.base().fournisseurs.find_one({"id": str(corps.get("fournisseur_id") or ""), "actif": True})
    if not f:
        validation.erreur("Fournisseur inconnu ou désactivé")
    lignes = _lignes_commande(corps)
    n = db.numero_suivant(f"commande-{date.today().year}")
    c = {"id": str(uuid.uuid4()), "numero": f"C-{date.today().year}-{n:06d}", "fournisseur_id": f["id"], "fournisseur_nom": f["nom"], "lignes": lignes, "total": _total(lignes),
         "statut": "commandee" if corps.get("envoyer") else "brouillon", "date_commande": date.today().isoformat(), "notes": validation.texte(corps, "notes", "Notes", False, 200), "cree_par": u["login"], "cree_le": db.maintenant()}
    db.base().commandes.insert_one(c)
    journaliser("commande_creee", u, f"{c['numero']} {c['total']}")
    return _public(c)


@routeur.post("/parc/commandes/{id_}/statut")
def changer_statut(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.ECRITURE_PARC))):
    """brouillon → commandée → reçue ; annulation possible avant réception. La RÉCEPTION (quantités reçues éventuellement partielles via `recues`) crée les entrées de stock et met à jour le dernier prix."""
    c = db.base().commandes.find_one({"id": id_})
    if not c:
        raise HTTPException(404, "Commande introuvable")
    s = validation.choix(corps, "statut", "Statut", ["commandee", "recue", "annulee"], obligatoire=True)
    ordre = {"brouillon": ["commandee", "annulee"], "commandee": ["recue", "annulee"]}
    if s not in ordre.get(c["statut"], []):
        raise HTTPException(409, f"Passage impossible : {STATUTS_COMMANDE[c['statut']]} → {STATUTS_COMMANDE[s]}")
    if s == "recue":
        recues = corps.get("recues") or {}
        for l in c["lignes"]:
            q = validation.nombre({"q": recues.get(l["piece_id"], l["quantite"])}, "q", "Quantité reçue", 0, 1_000_000) or 0
            if q <= 0:
                continue
            maj = {"$inc": {"stock": q}}
            if l["prix_unitaire"]:
                maj["$set"] = {"prix_unitaire": l["prix_unitaire"]}
            db.base().pieces.update_one({"id": l["piece_id"]}, maj)
            db.base().mouvements_pieces.insert_one({"id": str(uuid.uuid4()), "piece_id": l["piece_id"], "type": "entree", "quantite": q, "date": date.today().isoformat(), "commande_id": id_,
                                                    "cout_unitaire": l["prix_unitaire"], "motif": f"Réception {c['numero']}", "par": u["login"], "cree_le": db.maintenant()})
    db.base().commandes.update_one({"id": id_}, {"$set": {"statut": s, **({"date_reception": date.today().isoformat()} if s == "recue" else {})}})
    journaliser("commande_statut", u, f"{c['numero']} → {s}")
    return _public(db.base().commandes.find_one({"id": id_}))
