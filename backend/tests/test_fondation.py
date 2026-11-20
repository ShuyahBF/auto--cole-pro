"""Tests du lot 1 : isolation entre auto-écoles, droits, tarifs et promotions, inscriptions, paiements, impayés, tableau de bord."""
from datetime import date, timedelta

from app import db
from tests.conftest import ECOLE, entete, nouveau_tarif, nouvel_eleve


def test_connexion_et_blocage(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"login": "sec", "mot_de_passe": "faux"}).status_code == 401
    assert client.post("/api/auth/login", json={"login": "sec", "mot_de_passe": "Motdepasse1"}).status_code == 429


def test_ecole_creee_avec_agence_et_directeur(client):
    h = entete(client, "sa")
    r = client.post("/api/ecoles", json={"nom": "Auto-école Sahel", "prefixe": "SAH", "pays": "ML", "directeur": {"login": "dsahel", "nom_affiche": "Directeur", "mot_de_passe": "Motdepasse9"}}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["devise"] == "FCFA" and r.json()["decimales"] == 0
    # Préfixe unique
    assert client.post("/api/ecoles", json={"nom": "Autre", "prefixe": "SAH", "pays": "ML"}, headers=h).status_code == 409
    # Le directeur de la nouvelle école ne voit pas l'école de test
    r = client.post("/api/auth/login", json={"login": "dsahel", "mot_de_passe": "Motdepasse9"})
    hd = {"Authorization": "Bearer " + r.json()["jeton"]}
    assert [e["prefixe"] for e in client.get("/api/ecoles", headers=hd).json()] == ["SAH"]
    assert [a["nom"] for a in client.get("/api/agences", headers=hd).json()] == ["Siège"]


def test_isolation_des_ecoles(client):
    h = entete(client, "dir")
    t = nouveau_tarif(client, h)
    nouvel_eleve(client, h, t)
    hs = entete(client, "sa")
    client.post("/api/ecoles", json={"nom": "Autre école", "prefixe": "AUT", "pays": "BF", "directeur": {"login": "dautre", "nom_affiche": "D", "mot_de_passe": "Motdepasse9"}}, headers=hs)
    ha = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"login": "dautre", "mot_de_passe": "Motdepasse9"}).json()["jeton"]}
    assert client.get("/api/eleves", headers=ha).json()["total"] == 0
    assert client.get("/api/tarifs", headers=ha).json() == []
    # Un super administrateur sans école choisie n'accède à aucune donnée d'école
    assert client.get("/api/eleves", headers={"Authorization": hs["Authorization"]}).status_code == 400


def test_droits_par_role(client):
    assert client.post("/api/tarifs", json={"code": "X", "libelle": "x", "categorie": "B", "prix": 1}, headers=entete(client, "sec")).status_code == 403
    assert client.get("/api/comptes", headers=entete(client, "ges")).status_code == 403
    assert client.get("/api/tableau", headers=entete(client, "mec")).status_code == 403
    assert client.get("/api/eleves", headers=entete(client, "mec")).status_code == 403


def test_tarif_et_promotion(client):
    h = entete(client, "dir")
    t = nouveau_tarif(client, h, acompte_minimum=50000)
    assert client.post("/api/tarifs", json={"code": "B-STD", "libelle": "x", "categorie": "B", "prix": 1}, headers=h).status_code == 409
    assert client.post("/api/tarifs", json={"code": "Z", "libelle": "x", "categorie": "Z9", "prix": 1}, headers=h).status_code == 422
    p = client.post("/api/promotions", json={"code": "RENTREE", "libelle": "Rentrée", "type": "pourcentage", "valeur": 10}, headers=h)
    assert p.status_code == 200
    e = nouvel_eleve(client, h, t, promotion="rentree")
    assert e["remise"] == 15000 and e["net_a_payer"] == 135000
    # Une promotion terminée est refusée
    client.post("/api/promotions", json={"code": "VIEILLE", "libelle": "Vieille", "type": "montant", "valeur": 5000, "fin": (date.today() - timedelta(days=1)).isoformat()}, headers=h)
    r = client.post("/api/eleves", json={"nom": "Autre", "prenom": "X", "date_naissance": "1999-01-01", "telephone": "70000001", "categorie": "B", "tarif_id": t["id"], "promotion": "VIEILLE"}, headers=h)
    assert r.status_code == 422
    # Changer le tarif ne change pas le dossier existant ; un tarif utilisé ne se supprime pas
    client.put(f"/api/tarifs/{t['id']}", json={"prix": 200000}, headers=h)
    assert client.get(f"/api/eleves/{e['id']}", headers=h).json()["prix"] == 150000
    assert client.delete(f"/api/tarifs/{t['id']}", headers=h).status_code == 409


def test_inscription_controles(client):
    h = entete(client, "sec")
    hd = entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, h, t)
    assert e["matricule"].startswith("EXC-") and e["matricule"].endswith("-000001")
    assert nouvel_eleve(client, h, t, nom="Autre", prenom="Personne")["matricule"].endswith("-000002")
    # Doublon : refus puis confirmation
    base = {"nom": "Ouedraogo", "prenom": "Awa", "date_naissance": "2000-03-02", "telephone": "70000000", "categorie": "B", "tarif_id": t["id"]}
    assert client.post("/api/eleves", json=base, headers=h).status_code == 409
    assert client.post("/api/eleves", json={**base, "confirmer_doublon": True}, headers=h).status_code == 200
    # Âge minimum de la catégorie
    jeune = (date.today() - timedelta(days=365 * 17)).isoformat()
    assert client.post("/api/eleves", json={**base, "nom": "Jeune", "date_naissance": jeune}, headers=h).status_code == 422
    # Tarif d'une autre catégorie
    t2 = nouveau_tarif(client, hd, code="A-STD", categorie="A")
    assert client.post("/api/eleves", json={**base, "nom": "Moto", "tarif_id": t2["id"]}, headers=h).status_code == 422


def test_dossier_pieces_et_statut(client):
    h = entete(client, "sec")
    t = nouveau_tarif(client, entete(client, "dir"))
    e = nouvel_eleve(client, h, t)
    assert not e["dossier_complet"] and "identite" in e["pieces_manquantes"]
    assert client.post(f"/api/eleves/{e['id']}/statut", json={"statut": "pret_examen"}, headers=h).status_code == 409
    r = client.put(f"/api/eleves/{e['id']}", json={"pieces": {"identite": True, "photos": True, "naissance": True, "medical": True}}, headers=h)
    assert r.json()["dossier_complet"]
    assert client.post(f"/api/eleves/{e['id']}/statut", json={"statut": "pret_examen"}, headers=h).json()["statut"] == "pret_examen"


def test_paiements_recu_et_annulation(client):
    hs, hd, hc = entete(client, "sec"), entete(client, "dir"), entete(client, "cpt")
    t = nouveau_tarif(client, hd, prix=100000)
    e = nouvel_eleve(client, hs, t)
    r = client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 40000, "mode": "especes"}, headers=hs)
    assert r.status_code == 200 and r.json()["recu"].endswith("-000001")
    # Mobile money sans référence refusé ; dépassement refusé
    assert client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 1000, "mode": "mobile_money"}, headers=hs).status_code == 422
    assert client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 70000, "mode": "especes"}, headers=hs).status_code == 409
    p2 = client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 60000, "mode": "mobile_money", "reference": "TX123"}, headers=hs).json()
    assert p2["recu"].endswith("-000002")
    assert client.get(f"/api/eleves/{e['id']}", headers=hs).json()["reste_du"] == 0
    # Annulation réservée (secrétaire refusée), motif obligatoire, le reste dû revient
    assert client.post(f"/api/paiements/{p2['id']}/annuler", json={"motif": "erreur"}, headers=hs).status_code == 403
    assert client.post(f"/api/paiements/{p2['id']}/annuler", json={}, headers=hc).status_code == 422
    assert client.post(f"/api/paiements/{p2['id']}/annuler", json={"motif": "Erreur de saisie"}, headers=hc).status_code == 200
    assert client.get(f"/api/eleves/{e['id']}", headers=hs).json()["reste_du"] == 60000
    pdf = client.get(f"/api/paiements/{p2['id']}/recu", headers=hs)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and "inline" in pdf.headers["content-disposition"]
    jour = client.get("/api/paiements", headers=hs).json()
    assert jour["total"] == 40000 and jour["nombre"] == 1


def test_impayes_et_retard(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd, prix=100000)
    e = nouvel_eleve(client, hs, t)
    hier = (date.today() - timedelta(days=5)).isoformat()
    demain = (date.today() + timedelta(days=5)).isoformat()
    assert client.put(f"/api/eleves/{e['id']}", json={"echeances": [{"date": hier, "montant": 50000}, {"date": demain, "montant": 50000}]}, headers=hs).status_code == 200
    assert client.put(f"/api/eleves/{e['id']}", json={"echeances": [{"date": hier, "montant": 150000}]}, headers=hs).status_code == 422
    client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 20000, "mode": "especes"}, headers=hs)
    imp = client.get("/api/impayes", headers=hs).json()
    assert imp["impayes"][0]["retard"] == 30000 and imp["impayes"][0]["reste_du"] == 80000
    assert client.get("/api/eleves?impaye=true", headers=hs).json()["total"] == 1


def test_tableau_de_bord_et_recherche(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd, prix=100000)
    e = nouvel_eleve(client, hs, t)
    nouvel_eleve(client, hs, t, nom="Kaboré", prenom="Issa")
    client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 30000, "mode": "especes"}, headers=hs)
    tb = client.get("/api/tableau", headers=hd).json()
    assert tb["eleves_total"] == 2 and tb["encaisse_aujourdhui"] == 30000 and tb["reste_du_total"] == 170000 and tb["inscriptions_mois"] == 2
    assert [x["nombre"] for x in tb["par_statut"] if x["statut"] == "inscrit"] == [2]
    assert client.get("/api/eleves?q=kabore", headers=hs).json()["total"] == 1       # sans accent ni majuscule
    assert client.get("/api/eleves?tri=nom&sens=asc", headers=hs).json()["eleves"][0]["nom"] == "KABORÉ"


def test_agence_limitee(client):
    hd = entete(client, "dir")
    a2 = client.post("/api/agences", json={"nom": "Bobo"}, headers=hd).json()
    t = nouveau_tarif(client, hd)
    nouvel_eleve(client, hd, t)                                     # agence principale
    nouvel_eleve(client, hd, t, nom="Sanou", prenom="Paul", agence_id=a2["id"])
    db.brut().utilisateurs.update_one({"login": "ges"}, {"$set": {"agence_id": a2["id"]}})
    hg = entete(client, "ges")
    r = client.get("/api/eleves", headers=hg).json()
    assert r["total"] == 1 and r["eleves"][0]["nom"] == "SANOU"
    assert client.post("/api/eleves", json={"nom": "X", "prenom": "Y", "date_naissance": "1999-01-01", "telephone": "70000009", "categorie": "B", "tarif_id": t["id"], "agence_id": "autre"}, headers=hg).status_code == 422


def test_ecole_desactivee_et_devise(client):
    hd = entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hd, t)
    client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 1000, "mode": "especes"}, headers=hd)
    assert client.put("/api/ecole", json={"devise": "EUR"}, headers=hd).status_code == 409      # des paiements existent
    client.put(f"/api/ecoles/{ECOLE}", json={"actif": False}, headers=entete(client, "sa"))
    assert client.get("/api/me", headers=hd).status_code == 403


def test_le_moniteur_ne_voit_aucun_montant(client):
    hd, hm = entete(client, "dir"), entete(client, "mon")
    t = nouveau_tarif(client, hd, prix=100000)
    e = nouvel_eleve(client, hd, t)
    liste = client.get("/api/eleves", headers=hm).json()
    assert liste["totaux"] is None and not ({"prix", "net_a_payer", "paye", "reste_du"} & set(liste["eleves"][0]))
    fiche = client.get(f"/api/eleves/{e['id']}", headers=hm).json()
    assert not ({"prix", "net_a_payer", "paye", "reste_du", "paiements"} & set(fiche))
    assert client.post(f"/api/eleves/{e['id']}/paiements", json={"montant": 1, "mode": "especes"}, headers=hm).status_code == 403
    assert client.get("/api/impayes", headers=hm).status_code == 403


def test_pastilles_du_menu(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    nouvel_eleve(client, hs, t)                                     # dossier incomplet (pièces obligatoires non reçues)
    assert client.get("/api/notifications/compteurs", headers=hs).json() == {"/eleves": 1, "/impayes": 0}
    assert client.get("/api/notifications/compteurs", headers=entete(client, "mon")).json() == {"/eleves": 1}
