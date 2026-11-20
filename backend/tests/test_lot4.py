"""Tests du lot 4 : messagerie WhatsApp (Transmission universelle), retours signés de SAWALI, notifications automatiques, évaluations par les clients."""
import json
import time
from datetime import date, timedelta

import pytest

from app import db, whatsapp
from tests.conftest import ECOLE, entete, nouveau_tarif, nouvel_eleve

CLE = "cle-de-test-liluvine-123"


@pytest.fixture()
def wa(monkeypatch, client):
    """WhatsApp configuré (ligne partagée) avec un faux service : aucun appel réseau réel ; les appels sont enregistrés."""
    monkeypatch.setenv("LILUVINE_WA_URL", "https://sawali.test/send")
    monkeypatch.setenv("LILUVINE_WA_HMAC", CLE)
    monkeypatch.setenv("WHATSAPP_SYNC", "1")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://autoecole.test")
    appels = []

    def faux(url, entetes, corps):
        d = json.loads(corps)
        appels.append({"entetes": entetes, "corps": d})
        return (409, {}) if d["to"].endswith("70000009") else (200, {"ok": True})
    monkeypatch.setattr(whatsapp, "_appel_http", faux)
    return appels


def _signer(corps: dict, cle=CLE, decalage=0):
    brut = json.dumps(corps)
    ts = str(int(time.time()) + decalage)
    return brut, {"X-Timestamp": ts, "X-Signature": whatsapp.signer(cle, ts, brut), "Content-Type": "application/json"}


def test_envoi_signe_et_statuts(client, wa):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hs, t, telephone="70 11 22 33")
    assert client.post("/api/messagerie/contacts/importer-eleves", headers=hs).json()["crees"] == 1
    c = client.get("/api/messagerie/contacts", headers=hs).json()[0]
    assert c["numero"] == "22670112233" and "70112233" not in c["numero_masque"]
    r = client.post("/api/messagerie/envoyer", json={"contact_id": c["id"], "texte": "Bonjour {prenom} ({matricule})"}, headers=hs)
    assert r.status_code == 200 and r.json()["statut"] == "en_cours"                   # la réponse est immédiate
    corps = wa[0]["corps"]
    assert corps["to"] == "+22670112233" and e["matricule"] in corps["message"] and corps["source"] == "AutoEcole Pro" and wa[0]["entetes"]["X-Emetteur"] == "autoecole"
    # La signature est celle du protocole : HMAC-SHA256(clé, "<horodatage>.<corps brut>")
    brut = json.dumps(corps, ensure_ascii=False, separators=(",", ":"))
    assert wa[0]["entetes"]["X-Signature"] == whatsapp.signer(CLE, wa[0]["entetes"]["X-Timestamp"], brut)
    assert client.get(f"/api/messagerie/contacts/{c['id']}/messages", headers=hs).json()["messages"][0]["statut"] == "envoye"      # puis « envoyé » (arrière-plan)
    # Retour de statut signé : remis
    brut, h = _signer({"type": "statut", "id": r.json()["id"], "statut": "delivered"})
    assert client.post("/api/webhooks/liluvine-retour", content=brut, headers=h).status_code == 200
    conv = client.get(f"/api/messagerie/contacts/{c['id']}/messages", headers=hs).json()
    assert conv["messages"][0]["statut"] == "remis"


def test_retour_signature_et_stats(client, wa):
    brut, h = _signer({"type": "stats_du_jour"}, cle="mauvaise")
    assert client.post("/api/webhooks/liluvine-retour", content=brut, headers=h).status_code == 401
    brut, h = _signer({"type": "stats_du_jour"}, decalage=-1000)
    assert client.post("/api/webhooks/liluvine-retour", content=brut, headers=h).status_code == 401          # horodatage trop ancien
    brut, h = _signer({"type": "stats_du_jour"})
    r = client.post("/api/webhooks/liluvine-retour", content=brut, headers=h).json()
    assert {i["cle"] for i in r["indicateurs"]} >= {"ecoles", "eleves", "avis", "wa_envoyes"} and r["version"] and r["deploye_le"]
    assert "nom" not in json.dumps(r)                                                                      # aucune donnée personnelle


def test_stop_reponse_et_confirmation(client, wa):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hs, t, telephone="70000009")
    client.post("/api/messagerie/contacts/importer-eleves", headers=hs)
    c = client.get("/api/messagerie/contacts", headers=hs).json()[0]
    # Désinscription (STOP) : plus aucun envoi
    brut, h = _signer({"type": "desinscription", "de": "+22670000009"})
    client.post("/api/webhooks/liluvine-retour", content=brut, headers=h)
    assert client.post("/api/messagerie/envoyer", json={"contact_id": c["id"], "texte": "x"}, headers=hs).status_code == 409
    # Réponse d'un contact : rangée dans la conversation, comptée non lue ; « 1 » confirme l'examen suivant
    PIECES = {"identite": True, "photos": True, "naissance": True, "medical": True}
    client.put(f"/api/eleves/{e['id']}", json={"pieces": PIECES}, headers=hs)
    s = client.post("/api/examens/sessions", json={"type": "interne", "epreuve": "code", "categorie": "B", "date": (date.today() + timedelta(days=2)).isoformat(), "lieu": "Salle", "capacite": 5}, headers=hs).json()
    ins = client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs).json()
    brut, h = _signer({"type": "reponse", "de": "+22670000009", "texte": "1"})
    client.post("/api/webhooks/liluvine-retour", content=brut, headers=h)
    assert client.get("/api/messagerie/contacts", headers=hs).json()[0]["non_lus"] == 1
    assert db.brut().inscriptions_examen.find_one({"id": ins["id"]})["confirmation_wa"] == "confirmee"


def test_groupe_convocations_impayes_et_modeles(client, wa):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd, prix=100000)
    PIECES = {"identite": True, "photos": True, "naissance": True, "medical": True}
    e = nouvel_eleve(client, hs, t, telephone="70112233")
    client.put(f"/api/eleves/{e['id']}", json={"pieces": PIECES}, headers=hs)
    s = client.post("/api/examens/sessions", json={"type": "externe", "epreuve": "code", "categorie": "B", "date": (date.today() + timedelta(days=5)).isoformat(), "heure": "09:00", "lieu": "Centre Nord", "capacite": 5}, headers=hs).json()
    client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs)
    client.put(f"/api/eleves/{e['id']}", json={"echeances": [{"date": (date.today() - timedelta(days=3)).isoformat(), "montant": 40000}]}, headers=hs)      # retard APRÈS l'inscription
    ap = client.post("/api/messagerie/groupe", json={"cible": "convocations", "session_id": s["id"], "apercu": True}, headers=hs).json()
    assert ap["a_envoyer"] == 1 and wa == []                                                         # l'aperçu n'envoie rien
    r = client.post("/api/messagerie/groupe", json={"cible": "convocations", "session_id": s["id"]}, headers=hs).json()
    assert r["envoyes"] == 1 and "Centre Nord" in wa[0]["corps"]["message"] and "09:00" in wa[0]["corps"]["message"]
    assert client.post("/api/messagerie/groupe", json={"cible": "impayes"}, headers=hs).json()["envoyes"] == 1
    assert "solde" in wa[1]["corps"]["message"] and "40" not in wa[1]["corps"]["message"]            # aucun montant ne part par WhatsApp
    assert len(client.get("/api/messagerie/modeles", headers=hs).json()) == 5
    assert client.get("/api/messagerie/etat", headers=hs).json() == {"configure": True, "canal": "partagee"}


def test_notifications_automatiques_et_ligne_privee(client, wa, monkeypatch):
    hs, hd, hsa = entete(client, "sec"), entete(client, "dir"), entete(client, "sa")
    t = nouveau_tarif(client, hd)
    nouvel_eleve(client, hs, t, telephone="70112233")
    assert wa == []                                                                                 # éteint par défaut
    assert client.put("/api/messagerie/parametres", json={"auto": {"inscription": True}}, headers=hs).status_code == 403
    client.put("/api/messagerie/parametres", json={"auto": {"inscription": True}}, headers=hd)
    nouvel_eleve(client, hs, t, nom="Autre", prenom="Eleve", telephone="70445566")
    assert len(wa) == 1 and "bienvenue" in wa[0]["corps"]["message"].lower()
    # Ligne privée : émetteur de l'école + clé dans LILUVINE_WA_HMAC_EXC
    monkeypatch.setenv("LILUVINE_WA_HMAC_EXC", "cle-privee-exc")
    r = client.put("/api/messagerie/ligne", json={"wa_emetteur": "exc"}, headers=hsa).json()
    assert r["variable_cle"] == "LILUVINE_WA_HMAC_EXC" and r["canal"] == "ligne_ecole"
    nouvel_eleve(client, hs, t, nom="Troisieme", prenom="Eleve", telephone="70778899")
    assert wa[-1]["entetes"]["X-Emetteur"] == "exc"
    assert wa[-1]["entetes"]["X-Signature"] == whatsapp.signer("cle-privee-exc", wa[-1]["entetes"]["X-Timestamp"], json.dumps(wa[-1]["corps"], ensure_ascii=False, separators=(",", ":")))
    # Un retour signé par la clé PRIVÉE désigne l'école : les stats ne portent que sur elle
    brut, h = _signer({"type": "stats_du_jour"}, cle="cle-privee-exc")
    stats = client.post("/api/webhooks/liluvine-retour", content=brut, headers=h).json()
    assert [i["valeur"] for i in stats["indicateurs"] if i["cle"] == "ecoles"] == [1]


def test_avis_lien_unique_nps_et_publication(client, wa):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hs, t, telephone="70112233")
    client.post(f"/api/eleves/{e['id']}/seances", json={"duree_min": 60}, headers=entete(client, "mon"))
    lien = client.post("/api/avis/demandes", json={"eleve_id": e["id"]}, headers=hd).json()["lien"]
    assert lien.startswith("https://autoecole.test/avis/")
    jeton = lien.rsplit("/", 1)[1]
    assert jeton not in json.dumps(list(db.brut().demandes_avis.find({}, {"_id": 0})))               # seule l'empreinte est gardée
    f = client.get(f"/api/public/avis/{jeton}").json()
    assert f["ecole"] == "Auto-école Excellence" and f["prenom"] == "Awa" and not f["deja_repondu"]
    assert client.get("/api/public/avis/inconnu").status_code == 404
    assert client.post(f"/api/public/avis/{jeton}", json={"nps": 9}).status_code == 422             # note globale obligatoire
    r = client.post(f"/api/public/avis/{jeton}", json={"note_globale": 5, "nps": 10, "notes": {"moniteur": 5, "vehicule": 4}, "commentaire": "<script>alert(1)</script> Super !", "autorise_publication": True})
    assert r.status_code == 200
    assert client.post(f"/api/public/avis/{jeton}", json={"note_globale": 1}).status_code == 409    # usage unique
    # Deuxième élève, insatisfait, sans autorisation de publication
    e2 = nouvel_eleve(client, hs, t, nom="Mecontent", prenom="Paul", telephone="70445566")
    j2 = client.post("/api/avis/demandes", json={"eleve_id": e2["id"]}, headers=hd).json()["lien"].rsplit("/", 1)[1]
    client.post(f"/api/public/avis/{j2}", json={"note_globale": 2, "nps": 3})
    syn = client.get("/api/avis/synthese", headers=hs).json()
    assert syn["nombre"] == 2 and syn["satisfaction"] == 3.5 and syn["nps"] == 0 and syn["taux_reponse"] == 100
    assert syn["par_moniteur"] == [{"moniteur": "mon", "moyenne": 5.0, "nombre": 1}]
    avis = {a["prenom"]: a for a in client.get("/api/avis", headers=hs).json()}
    assert client.get("/api/avis?note_max=2", headers=hs).json()[0]["prenom"] == "Paul"
    assert client.put(f"/api/avis/{avis['Paul']['id']}", json={"publie": True}, headers=hd).status_code == 409        # pas de consentement
    assert client.put(f"/api/avis/{avis['Awa']['id']}", json={"publie": True, "reponse_ecole": "Merci !"}, headers=hd).json()["publie"] is True
    assert client.put(f"/api/avis/{avis['Awa']['id']}", json={"publie": False}, headers=hs).status_code == 403        # le secrétariat ne publie pas
    # Une nouvelle demande est refusée juste après une réponse
    assert client.post("/api/avis/demandes", json={"eleve_id": e["id"]}, headers=hd).status_code == 409


def test_avis_par_groupe_apres_permis(client, wa):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hs, t, telephone="70112233")
    db.base().eleves.update_one({"id": e["id"]}, {"$set": {"statut": "diplome", "date_permis": date.today().isoformat()}})
    assert client.post("/api/messagerie/groupe", json={"cible": "avis"}, headers=hs).json()["envoyes"] == 1
    assert "/avis/" in wa[0]["corps"]["message"]
    assert client.post("/api/messagerie/groupe", json={"cible": "avis"}, headers=hs).json()["envoyes"] == 0       # une seule demande par élève
