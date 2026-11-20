"""
CENTRE DE MESSAGERIE WhatsApp de l'auto-école (par la « Transmission WA universelle » Liluvine de SAWALI) : contacts (importés des élèves), conversations, modèles de messages,
envois groupés (convocations d'une session d'examen, relances d'impayés, demandes d'avis), notifications automatiques (option par école), et l'ADRESSE DE RETOUR signée de SAWALI
(`POST /api/webhooks/liluvine-retour`, règle 7). Aujourd'hui : la ligne PARTAGÉE (émetteur « autoecole ») ; plus tard : la LIGNE PRIVÉE d'une école (champ `wa_emetteur` de sa fiche +
variable Render `LILUVINE_WA_HMAC_<PRÉFIXE>`), sans changer le code.

Principes : chaque école a SES contacts, messages et modèles (filtrés par école) ; l'envoi part en ARRIÈRE-PLAN (règle 7) : « en cours » → « envoyé » → « remis » → « lu » / « échec » ;
un numéro qui a répondu STOP ne reçoit plus rien (409) ; le TEXTE d'un message n'est jamais journalisé ; aucun montant détaillé ni donnée de santé ne part par WhatsApp.
"""
from __future__ import annotations

import hmac
import json
import logging
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from . import db, roles, validation, whatsapp
from .auth import exiger_roles, journaliser

routeur = APIRouter()
# Journal VISIBLE dans Render : le logger « uvicorn.error » est celui dont le niveau INFO est affiché
journal_serveur = logging.getLogger("uvicorn.error")

MODELES_DEFAUT = [
    ("Bienvenue", "Bonjour {prenom}, bienvenue à {ecole} ! Votre matricule est {matricule}. Nous restons à votre disposition."),
    ("Convocation à l'examen", "Bonjour {prenom}, vous êtes convoqué(e) à l'examen {examen} le {date_examen} à {heure_examen} ({lieu_examen}). Munissez-vous d'une pièce d'identité. {ecole}"),
    ("Rappel de paiement", "Bonjour {prenom}, sauf erreur de notre part, un solde reste à régler pour votre formation. Merci de passer à {ecole} ou de nous contacter. Merci !"),
    ("Demande d'avis", "Bonjour {prenom}, votre avis compte pour {ecole} ! Donnez-nous votre avis en 1 minute : {lien_avis}"),
    ("Félicitations", "Félicitations {prenom} pour votre réussite ! Toute l'équipe de {ecole} vous souhaite bonne route."),
]
REPONSES_OUI = {"1", "oui", "ok", "yes", "confirme", "confirmé"}
REPONSES_NON = {"2", "non", "no", "empêché", "empeche"}


def _court(valeur, taille: int) -> str:
    return str(valeur or "")[:taille]


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "ecole_id")}


def _ecole(id_: str | None = None) -> dict:
    return db.brut().ecoles.find_one({"id": id_ or db.ecole_courante.get()}) or {}


def lancer(fonction, *arguments) -> None:
    """Envoie EN ARRIÈRE-PLAN (fil séparé : la requête n'attend jamais l'API WhatsApp, règle 7). WHATSAPP_SYNC=1 : envoi immédiat (tests)."""
    from .config import env
    if env("WHATSAPP_SYNC") == "1":
        fonction(*arguments)
        return
    import threading
    threading.Thread(target=fonction, args=arguments, daemon=True).start()


# ---------- état, contacts ----------

@routeur.get("/messagerie/etat")
def etat(u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """WhatsApp est-il configuré, et par quelle ligne (« ligne_ecole » privée, « partagee » commune, « aucun ») ?"""
    return {"configure": whatsapp.configure(db.ecole_courante.get()), "canal": whatsapp.canal_de_l_ecole(db.ecole_courante.get())}


def _contact(id_: str) -> dict:
    c = db.base().contacts.find_one({"id": id_})
    if not c:
        raise HTTPException(404, "Contact introuvable")
    return c


def _contact_pour_eleve(e: dict) -> dict | None:
    """Contact WhatsApp de l'élève (créé si besoin) ; None si son numéro n'est pas valide."""
    indicatif = _ecole().get("indicatif") or "226"
    brut = re.sub(r"\D", "", e.get("telephone") or "")
    numero = whatsapp.normaliser_numero(brut if len(brut) != 8 else indicatif + brut)
    if not numero:
        return None
    c = db.base().contacts.find_one({"numero": numero})
    if c:
        if not c.get("eleve_id"):
            db.base().contacts.update_one({"id": c["id"]}, {"$set": {"eleve_id": e["id"]}})
        return c
    c = {"id": str(uuid.uuid4()), "nom": f"{e['nom']} {e['prenom']}", "nom_norm": validation.normaliser(f"{e['nom']} {e['prenom']}"), "numero": numero, "eleve_id": e["id"], "categorie": "eleve",
         "desinscrit": False, "dernier_le": "", "dernier_extrait": "", "cree_le": _maintenant()}
    db.base().contacts.insert_one(c)
    return c


@routeur.get("/messagerie/contacts")
def lister_contacts(q: str = "", u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Contacts (conversations récentes d'abord) avec le nombre de messages non lus, calculé en UNE lecture."""
    f: dict = {"nom_norm": {"$regex": re.escape(validation.normaliser(q))}} if q.strip() else {}
    non_lus: dict = {}
    for m in db.base().wa_messages.find({"sens": "entrant", "lu": False}, {"contact_id": 1}):
        non_lus[m["contact_id"]] = non_lus.get(m["contact_id"], 0) + 1
    lignes = [{**_public(c), "numero_masque": whatsapp.masquer_numero(c["numero"]), "non_lus": non_lus.get(c["id"], 0)} for c in db.base().contacts.find(f, {"_id": 0}).limit(1000)]
    lignes.sort(key=lambda c: c.get("dernier_le") or "", reverse=True)
    return lignes


@routeur.post("/messagerie/contacts")
def creer_contact(corps: dict, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Nouveau contact (nom, numéro WhatsApp valide, unique dans l'école)."""
    numero = whatsapp.normaliser_numero(re.sub(r"\D", "", validation.texte(corps, "numero", "Numéro WhatsApp", True, 25)))
    if not numero:
        validation.erreur("Numéro WhatsApp invalide")
    if db.base().contacts.find_one({"numero": numero}):
        raise HTTPException(409, "Ce numéro existe déjà")
    nom = validation.texte(corps, "nom", "Nom", True, 80)
    c = {"id": str(uuid.uuid4()), "nom": nom, "nom_norm": validation.normaliser(nom), "numero": numero, "eleve_id": "", "categorie": "autre", "desinscrit": False, "dernier_le": "", "dernier_extrait": "", "cree_le": _maintenant()}
    db.base().contacts.insert_one(c)
    return _public(c)


@routeur.post("/messagerie/contacts/importer-eleves")
def importer_eleves(u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Crée un contact pour chaque élève actif dont le numéro est valide et pas encore connu (une lecture groupée des contacts)."""
    connus = {c["numero"] for c in db.base().contacts.find({}, {"numero": 1})}
    crees = ignores = 0
    for e in db.base().eleves.find({"statut": {"$nin": ["abandon", "transfere"]}}):
        c = _contact_pour_eleve(e) if True else None
        if c is None:
            ignores += 1
        elif c["numero"] not in connus:
            crees += 1
            connus.add(c["numero"])
    journaliser("contacts_importes", u, f"{crees} créé(s), {ignores} numéro(s) invalide(s)")
    return {"crees": crees, "numeros_invalides": ignores}


# ---------- modèles ----------

def _modeles() -> list[dict]:
    """Modèles de l'école ; les modèles par défaut sont créés au premier accès."""
    if not db.base().wa_modeles.count_documents({}, limit=1):
        db.base().wa_modeles.insert_many([{"id": str(uuid.uuid4()), "nom": n, "texte": t, "cree_le": _maintenant()} for n, t in MODELES_DEFAUT])
    return list(db.base().wa_modeles.find({}, {"_id": 0}).sort("nom", 1))


@routeur.get("/messagerie/modeles")
def lister_modeles(u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    return [_public(m) for m in _modeles()]


@routeur.post("/messagerie/modeles")
def creer_modele(corps: dict, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    _modeles()
    nom = validation.texte(corps, "nom", "Nom du modèle", True, 60)
    if db.base().wa_modeles.find_one({"nom": nom}):
        raise HTTPException(409, "Ce modèle existe déjà")
    m = {"id": str(uuid.uuid4()), "nom": nom, "texte": validation.texte(corps, "texte", "Texte", True, 800), "cree_le": _maintenant()}
    db.base().wa_modeles.insert_one(m)
    return _public(m)


@routeur.put("/messagerie/modeles/{id_}")
def modifier_modele(id_: str, corps: dict, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    if not db.base().wa_modeles.find_one({"id": id_}):
        raise HTTPException(404, "Modèle introuvable")
    db.base().wa_modeles.update_one({"id": id_}, {"$set": {"texte": validation.texte(corps, "texte", "Texte", True, 800)}})
    return _public(db.base().wa_modeles.find_one({"id": id_}))


@routeur.delete("/messagerie/modeles/{id_}")
def supprimer_modele(id_: str, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    db.base().wa_modeles.delete_one({"id": id_})
    return {"ok": True}


def appliquer_variables(texte: str, contact: dict | None = None, extra: dict | None = None) -> str:
    """Remplace {prenom}, {nom}, {ecole}, {matricule}… ; une variable inconnue est laissée telle quelle."""
    e = db.base().eleves.find_one({"id": (contact or {}).get("eleve_id")}) if (contact or {}).get("eleve_id") else None
    valeurs = {"ecole": _ecole().get("nom", ""), "prenom": (e or {}).get("prenom") or ((contact or {}).get("nom", "").split(" ")[-1]), "nom": (e or {}).get("nom") or (contact or {}).get("nom", ""),
               "matricule": (e or {}).get("matricule", ""), **(extra or {})}
    return re.sub(r"\{(\w+)\}", lambda m: str(valeurs.get(m.group(1), m.group(0))), texte)


# ---------- conversations et envoi ----------

def _noter_message(contact_id: str, **champs) -> dict:
    doc = {"id": str(uuid.uuid4()), "contact_id": contact_id, "cree_le": _maintenant(), "lu": champs.get("sens") != "entrant", "canal": whatsapp.canal_de_l_ecole(db.ecole_courante.get()) if champs.get("sens") == "sortant" else "", **champs}
    db.base().wa_messages.insert_one(doc)
    db.base().contacts.update_one({"id": contact_id}, {"$set": {"dernier_le": doc["cree_le"], "dernier_extrait": (champs.get("texte") or "")[:80]}})
    return doc


def _expedier(ecole_id: str, msg_id: str, numero: str, texte: str) -> None:
    """Fil d'ARRIÈRE-PLAN : appelle Liluvine puis note le résultat sur le message. N'attend jamais la requête de l'écran."""
    ok, erreur = whatsapp.envoyer(numero, texte, None, identifiant=msg_id, ecole_id=ecole_id)
    db.brut().wa_messages.update_one({"id": msg_id}, {"$set": {"statut": "envoye" if ok else "echec", "erreur": "" if ok else erreur, "envoye_le": _maintenant() if ok else ""}})
    if erreur and "désinscrit" in erreur:
        db.brut().contacts.update_many({"numero": numero, "ecole_id": ecole_id}, {"$set": {"desinscrit": True}})


def poster(contact: dict, texte: str, par: str, type_: str = "") -> dict | None:
    """Range un message sortant « en cours » et le fait partir en arrière-plan. None si WhatsApp n'est pas configuré ou si le contact est désinscrit (rien n'est bloqué pour autant)."""
    if not whatsapp.configure(db.ecole_courante.get()) or contact.get("desinscrit"):
        return None
    m = _noter_message(contact["id"], sens="sortant", texte=texte, statut="en_cours", erreur="", par=par, numero=contact["numero"], type=type_)
    lancer(_expedier, db.ecole_courante.get(), m["id"], contact["numero"], texte)
    return m


@routeur.post("/messagerie/envoyer")
def envoyer(corps: dict, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Envoie un message à un contact. Départ en arrière-plan : la réponse est immédiate (statut « en cours »)."""
    if not whatsapp.configure(db.ecole_courante.get()):
        raise HTTPException(503, "WhatsApp n'est pas configuré sur le serveur (LILUVINE_WA_URL et LILUVINE_WA_HMAC)")
    c = _contact(str(corps.get("contact_id") or ""))
    if c.get("desinscrit"):
        raise HTTPException(409, "Ce contact s'est désinscrit des messages WhatsApp (réponse STOP)")
    texte = appliquer_variables(validation.texte(corps, "texte", "Message", True, 1000), c)
    m = poster(c, texte, u["login"])
    journaliser("message_wa_envoye", u, f"{c['id']} ({len(texte)} car.)")            # jamais le texte
    return _public(m)


@routeur.get("/messagerie/contacts/{id_}/messages")
def conversation(id_: str, limite: int = 100, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Conversation (les `limite` derniers messages, du plus ancien au plus récent) ; les messages reçus passent « lus »."""
    c = _contact(id_)
    db.base().wa_messages.update_many({"contact_id": id_, "sens": "entrant", "lu": False}, {"$set": {"lu": True}})
    lignes = list(db.base().wa_messages.find({"contact_id": id_}, {"_id": 0, "ecole_id": 0}).sort("cree_le", -1).limit(max(1, min(limite, 300))))
    lignes.reverse()
    return {"contact": {**_public(c), "numero_masque": whatsapp.masquer_numero(c["numero"])}, "messages": lignes}


@routeur.post("/messagerie/groupe")
def envoi_groupe(corps: dict, u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """
    Envoi GROUPÉ à des élèves, selon `cible` : « convocations » (inscrits d'une session d'examen, `session_id`), « impayes » (élèves en retard d'échéancier) ou « avis » (permis obtenus récemment
    sans demande d'avis). Le modèle est choisi automatiquement (modifiable dans les modèles). `apercu` = ne rien envoyer, seulement compter. Un élève sans numéro valide ou désinscrit est ignoré.
    """
    cible = validation.choix(corps, "cible", "Cible", ["convocations", "impayes", "avis"], obligatoire=True)
    if not corps.get("apercu") and not whatsapp.configure(db.ecole_courante.get()):
        raise HTTPException(503, "WhatsApp n'est pas configuré sur le serveur (LILUVINE_WA_URL et LILUVINE_WA_HMAC)")
    modeles = {m["nom"]: m["texte"] for m in _modeles()}
    items: list[tuple[dict, str, dict]] = []                     # (élève, nom du modèle, variables supplémentaires)
    if cible == "convocations":
        s = db.base().sessions_examen.find_one({"id": str(corps.get("session_id") or "")})
        if not s:
            validation.erreur("Session d'examen : obligatoire")
        for i in db.base().inscriptions_examen.find({"session_id": s["id"], "statut": "inscrit"}):
            e = db.base().eleves.find_one({"id": i["eleve_id"]})
            if e:
                items.append((e, "Convocation à l'examen", {"examen": s["epreuve_libelle"], "date_examen": s["date"], "heure_examen": s.get("heure", ""), "lieu_examen": s["lieu"]}))
    elif cible == "impayes":
        aujourdhui = date.today().isoformat()
        paye: dict = {}
        for p in db.base().paiements.find({"annule": {"$ne": True}}, {"eleve_id": 1, "montant": 1}):
            paye[p["eleve_id"]] = paye.get(p["eleve_id"], 0) + p["montant"]
        for e in db.base().eleves.find({"statut": {"$nin": ["abandon", "transfere", "diplome"]}}):
            if sum(x["montant"] for x in e.get("echeances", []) if x["date"] < aujourdhui) > paye.get(e["id"], 0):
                items.append((e, "Rappel de paiement", {}))
    else:
        depuis = (date.today() - timedelta(days=30)).isoformat()
        for e in db.base().eleves.find({"statut": "diplome", "date_permis": {"$gte": depuis}}):
            if not db.base().demandes_avis.find_one({"eleve_id": e["id"]}):
                items.append((e, "Demande d'avis", {}))
    envoyes = ignores = 0
    for e, modele, extra in items:
        c = _contact_pour_eleve(e)
        if c is None or c.get("desinscrit"):
            ignores += 1
            continue
        if corps.get("apercu"):
            envoyes += 1
            continue
        if cible == "avis":
            from .avis import creer_demande
            extra = {"lien_avis": creer_demande(e)}
        if poster(c, appliquer_variables(modeles.get(modele, ""), c, extra), u["login"], type_=cible):
            envoyes += 1
        else:
            ignores += 1
    if not corps.get("apercu"):
        journaliser("messagerie_groupe", u, f"{cible} : {envoyes} envoyé(s), {ignores} ignoré(s)")
    return {"cible": cible, "a_envoyer" if corps.get("apercu") else "envoyes": envoyes, "ignores": ignores, "apercu": bool(corps.get("apercu"))}


# ---------- notifications automatiques (option par école) ----------

EVENEMENTS_AUTO = {"inscription": "Message de bienvenue à l'inscription", "examen_inscription": "Convocation à l'inscription à un examen", "examen_veille": "Rappel la veille de l'examen"}


@routeur.get("/messagerie/parametres")
def lire_parametres(u: dict = Depends(exiger_roles(roles.MESSAGERIE))):
    """Événements notifiés automatiquement (éteints par défaut) ; ligne privée de l'école (lecture seule ici : réglée par le super administrateur)."""
    e = _ecole()
    return {"auto": {k: bool((e.get("wa_auto") or {}).get(k)) for k in EVENEMENTS_AUTO}, "libelles": EVENEMENTS_AUTO, "wa_emetteur": e.get("wa_emetteur", ""), "wa_repli": bool(e.get("wa_repli"))}


@routeur.put("/messagerie/parametres")
def ecrire_parametres(corps: dict, u: dict = Depends(exiger_roles(roles.ADMINISTRATION))):
    """Active / désactive les notifications automatiques (directeur)."""
    auto = {k: bool((corps.get("auto") or {}).get(k)) for k in EVENEMENTS_AUTO}
    db.brut().ecoles.update_one({"id": db.ecole_courante.get()}, {"$set": {"wa_auto": auto}})
    journaliser("messagerie_auto_reglee", u, ", ".join(k for k, v in auto.items() if v) or "tout éteint")
    return lire_parametres(u)


@routeur.put("/messagerie/ligne")
def regler_ligne(corps: dict, u: dict = Depends(exiger_roles(roles.SUPER_ADMIN))):
    """LIGNE PRIVÉE d'une école (super administrateur) : émetteur créé dans SAWALI ; la clé va dans la variable Render LILUVINE_WA_HMAC_<PRÉFIXE> (jamais ici). `wa_repli` autorise la ligne partagée en cas de panne."""
    maj = {"wa_emetteur": validation.texte(corps, "wa_emetteur", "Émetteur SAWALI", False, 40).lower(), "wa_repli": bool(corps.get("wa_repli"))}
    db.brut().ecoles.update_one({"id": db.ecole_courante.get()}, {"$set": maj})
    journaliser("ligne_wa_reglee", u, maj["wa_emetteur"] or "ligne partagée")
    e = _ecole()
    return {**maj, "variable_cle": whatsapp.variable_cle_ecole(e.get("prefixe", "")), "canal": whatsapp.canal_de_l_ecole(e["id"])}


def notifier(evenement: str, eleve: dict, extra: dict | None = None) -> bool:
    """Message automatique si l'événement est activé pour l'école, si WhatsApp est configuré et si l'élève a un numéro valide non désinscrit. Ne lève JAMAIS d'exception : n'empêche jamais l'action d'origine."""
    try:
        if not (_ecole().get("wa_auto") or {}).get(evenement):
            return False
        nom = {"inscription": "Bienvenue", "examen_inscription": "Convocation à l'examen", "examen_veille": "Convocation à l'examen"}[evenement]
        modele = next((m["texte"] for m in _modeles() if m["nom"] == nom), "")
        c = _contact_pour_eleve(eleve)
        return bool(c and modele and poster(c, appliquer_variables(modele, c, extra), "automatique", type_=evenement))
    except Exception as exc:                                      # noqa: BLE001
        journal_serveur.warning("Notification automatique impossible (%s)", type(exc).__name__)
        return False


def rappels_veille(maintenant: date | None = None) -> int:
    """Tâche de fond (toutes les 5 minutes) : pour chaque école qui a activé « rappel la veille », convocation aux inscrits des sessions de DEMAIN (une seule fois par inscription)."""
    demain = ((maintenant or date.today()) + timedelta(days=1)).isoformat()
    n = 0
    for ecole in db.brut().ecoles.find({"actif": {"$ne": False}, "wa_auto.examen_veille": True}, {"id": 1}):
        db.fixer_ecole(ecole["id"])
        for s in db.base().sessions_examen.find({"date": demain, "statut": "planifiee"}):
            for i in db.base().inscriptions_examen.find({"session_id": s["id"], "statut": "inscrit", "rappel_envoye": {"$ne": True}}):
                e = db.base().eleves.find_one({"id": i["eleve_id"]})
                if e and notifier("examen_veille", e, {"examen": s["epreuve_libelle"], "date_examen": s["date"], "heure_examen": s.get("heure", ""), "lieu_examen": s["lieu"]}):
                    db.base().inscriptions_examen.update_one({"id": i["id"]}, {"$set": {"rappel_envoye": True}})
                    n += 1
    db.fixer_ecole(None)
    return n


# ---------- retours signés de SAWALI ----------

def _corps_signe(brut: bytes, horodatage: str, signature: str) -> tuple[dict, str | None]:
    """Vérifie la signature de SAWALI (X-Timestamp, X-Signature ; 5 minutes) ; la clé qui valide dit D'OÙ vient le retour (clé partagée → école None ; clé d'une école → cette école)."""
    cles = whatsapp.cles_de_retour()
    if not cles:
        raise HTTPException(503, "LILUVINE_WA_HMAC non configurée")
    if not horodatage.isdigit() or abs(time.time() - int(horodatage)) > 300:
        raise HTTPException(401, "Horodatage invalide")
    texte = brut.decode("utf-8")
    ecole = next((c for c, cle in cles if hmac.compare_digest(whatsapp.signer(cle, horodatage, texte), signature or "")), "refus")
    if ecole == "refus":
        raise HTTPException(401, "Signature invalide")
    try:
        corps = json.loads(texte or "{}")
    except ValueError:
        raise HTTPException(422, "Corps JSON invalide")
    if not isinstance(corps, dict):
        raise HTTPException(422, "Corps JSON attendu")
    return corps, ecole


def _stats_du_jour(ecole: str | None = None) -> dict:
    """Indicateurs du jour pour la synthèse quotidienne de SAWALI, sans aucune donnée personnelle : toutes les écoles (clé partagée) ou CETTE école (clé de sa ligne privée)."""
    from . import lot
    from .main import DEPLOYE_LE
    b, auj = db.brut(), date.today().isoformat()
    f = {"ecole_id": ecole} if ecole else {}
    return {"indicateurs": [
        {"cle": "ecoles", "libelle": "Auto-écoles actives", "valeur": 1 if ecole else b.ecoles.count_documents({"actif": {"$ne": False}})},
        {"cle": "eleves", "libelle": "Élèves en formation", "valeur": b.eleves.count_documents({**f, "statut": {"$in": ["inscrit", "en_formation", "pret_examen"]}})},
        {"cle": "inscriptions", "libelle": "Inscriptions du jour", "valeur": b.eleves.count_documents({**f, "date_inscription": auj})},
        {"cle": "examens", "libelle": "Sessions d'examen du jour", "valeur": b.sessions_examen.count_documents({**f, "date": auj, "statut": {"$ne": "annulee"}})},
        {"cle": "avis", "libelle": "Avis reçus aujourd'hui", "valeur": b.avis.count_documents({**f, "cree_le": {"$gte": auj}})},
        {"cle": "wa_envoyes", "libelle": "WhatsApp envoyés", "valeur": b.wa_messages.count_documents({**f, "sens": "sortant", "cree_le": {"$gte": auj}})},
        {"cle": "wa_recus", "libelle": "WhatsApp reçus", "valeur": b.wa_messages.count_documents({**f, "sens": "entrant", "cree_le": {"$gte": auj}})}],
        "faits_marquants": [], "version": lot.VERSION, "deploye_le": DEPLOYE_LE}


def _traiter_reponse(corps: dict, ecole: str | None = None) -> None:
    """Un contact a répondu : message rangé dans la conversation de la bonne école (numéro inconnu = « Nouveau contact » de l'école si elle est certaine) ; « 1 / 2 » confirment ou excusent l'examen suivant."""
    numero = whatsapp.normaliser_numero(str(corps.get("de") or corps.get("from") or ""))
    texte = str(corps.get("texte") or corps.get("message") or corps.get("text") or "").strip()[:1000]
    if not numero or not texte:
        return
    candidats = [c for c in db.brut().contacts.find({"numero": numero}) if not ecole or c["ecole_id"] == ecole]
    if not candidats:
        actives = [{"id": ecole}] if ecole else list(db.brut().ecoles.find({"actif": {"$ne": False}}, {"_id": 0, "id": 1}))
        if len(actives) != 1:
            db.brut().wa_non_classes.insert_one({"numero": numero, "extrait": texte[:80], "cree_le": _maintenant()})
            return
        db.fixer_ecole(actives[0]["id"])
        c = {"id": str(uuid.uuid4()), "nom": "Nouveau contact", "nom_norm": "nouveau contact", "numero": numero, "eleve_id": "", "categorie": "autre", "desinscrit": False, "dernier_le": "", "dernier_extrait": "", "cree_le": _maintenant()}
        db.base().contacts.insert_one(c)
        c["ecole_id"] = actives[0]["id"]
    else:
        c = max(candidats, key=lambda x: x.get("dernier_le") or "")
        db.fixer_ecole(c["ecole_id"])
    _noter_message(c["id"], sens="entrant", texte=texte, statut="recu", erreur="", numero=numero)
    mot = texte.lower().strip(" .!")
    if c.get("eleve_id") and mot in REPONSES_OUI | REPONSES_NON:
        i = db.base().inscriptions_examen.find_one({"eleve_id": c["eleve_id"], "statut": "inscrit", "date": {"$gte": date.today().isoformat()}}, sort=[("date", 1)])
        if i:
            db.base().inscriptions_examen.update_one({"id": i["id"]}, {"$set": {"confirmation_wa": "confirmee" if mot in REPONSES_OUI else "empeche", "confirmation_wa_le": _maintenant()}})


@routeur.post("/webhooks/liluvine-retour")
async def retour_sawali(request: Request):
    """
    Adresse de retour signée de SAWALI (règle 7) : statut de remise, réponse d'un contact, désinscription (STOP), statistiques du jour. À saisir dans SAWALI
    (émetteur « autoecole » → URL de retour, « URL des statistiques » laissée vide) : https://<serveur AutoÉcole Pro>/api/webhooks/liluvine-retour
    """
    from fastapi.concurrency import run_in_threadpool
    brut = await request.body()
    corps, ecole = _corps_signe(brut, request.headers.get("x-timestamp") or "", request.headers.get("x-signature") or "")
    genre = _court(corps.get("type"), 40)
    # JOURNAL DE DIAGNOSTIC (visible dans Render, logger « uvicorn.error ») : type, et pour un statut l'état, l'identifiant, la cause, la ligne. JAMAIS le texte d'un message ni un numéro.
    if genre == "statut":
        journal_serveur.info("Retour SAWALI : statut=%s message=%s cause=%s ligne=%s", _court(corps.get("statut"), 20), _court(corps.get("id") or corps.get("message_id"), 40),
                             _court(corps.get("erreur") or corps.get("error") or corps.get("raison") or corps.get("motif"), 80) or "-", "ecole" if ecole else "partagee")
    else:
        journal_serveur.info("Retour SAWALI : type=%s ligne=%s", genre or "-", "ecole" if ecole else "partagee")

    def travail():
        if genre == "stats_du_jour":
            return _stats_du_jour(ecole)
        if genre == "statut":
            ident, etat_ = str(corps.get("id") or corps.get("message_id") or ""), str(corps.get("statut") or "").lower()
            if ident and etat_:
                db.brut().wa_messages.update_one({"id": ident}, {"$set": {"statut": {"delivered": "remis", "read": "lu", "sent": "envoye", "failed": "echec"}.get(etat_, etat_)}})
        elif genre == "reponse":
            _traiter_reponse(corps, ecole)
        elif genre == "desinscription":
            numero = whatsapp.normaliser_numero(str(corps.get("de") or corps.get("from") or ""))
            if numero:
                db.brut().contacts.update_many({"numero": numero, **({"ecole_id": ecole} if ecole else {})}, {"$set": {"desinscrit": True, "desinscrit_le": _maintenant()}})
        else:
            db.brut().retours_sawali.insert_one({"type": genre[:40], "recu_le": _maintenant()})
        return {"ok": True}
    db.fixer_ecole(None)
    return await run_in_threadpool(travail)
