"""Tests du lot 3 : parc automobile (véhicules, km, carburant, pannes, interventions, pièces, commandes, alertes, coûts, confidentialité des montants)."""
from datetime import date, timedelta

from tests.conftest import entete


def _vehicule(client, h, immat="11 AA 1111", **extra):
    r = client.post("/api/parc/vehicules", json={"immatriculation": immat, "marque": "Toyota", "modele": "Yaris", "annee": 2020, "km_actuel": 10000, "intervalle_entretien_km": 5000, **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_vehicule_et_kilometrage(client):
    hm, hd = entete(client, "mec"), entete(client, "dir")
    v = _vehicule(client, hm)
    assert v["immatriculation"] == "11AA1111" and v["km_actuel"] == 10000
    assert client.post("/api/parc/vehicules", json={"immatriculation": "11aa1111", "marque": "X", "modele": "Y"}, headers=hm).status_code == 409
    assert client.post(f"/api/parc/vehicules/{v['id']}/km", json={"km": 10500}, headers=entete(client, "mon")).status_code == 200
    r = client.post(f"/api/parc/vehicules/{v['id']}/km", json={"km": 9000}, headers=entete(client, "mon"))
    assert r.status_code == 409 and "reculer" in r.text
    assert client.post(f"/api/parc/vehicules/{v['id']}/km", json={"km": 10400, "correction": True, "motif": "Erreur de lecture"}, headers=entete(client, "mon")).status_code == 409   # le moniteur ne corrige pas
    assert client.post(f"/api/parc/vehicules/{v['id']}/km", json={"km": 10400, "correction": True, "motif": "Erreur de lecture"}, headers=hd).status_code == 200
    assert client.get("/api/parc/vehicules", headers=hm).json()[0]["km_actuel"] == 10400


def test_carburant_consommation_et_anomalie(client):
    hm = entete(client, "mec")
    v = _vehicule(client, hm)
    base = date.today() - timedelta(days=40)
    for n, (km, litres) in enumerate([(10000, 40), (10500, 40), (11000, 40), (11500, 40), (12000, 70)]):       # 8 L/100 km puis 14 L/100 km (anomalie)
        r = client.post(f"/api/parc/vehicules/{v['id']}/pleins", json={"km": km, "litres": litres, "montant": litres * 700, "date": (base + timedelta(days=n * 7)).isoformat(), "station": "Total"}, headers=hm)
        assert r.status_code == 200, r.text
    d = client.get(f"/api/parc/vehicules/{v['id']}/pleins", headers=hm).json()
    assert d["pleins"][0]["conso_100km"] == 14.0 and d["pleins"][0]["anomalie"] and not d["pleins"][1]["anomalie"]
    assert any(a["type"] == "carburant" for a in client.get("/api/parc/alertes", headers=hm).json())
    assert client.post(f"/api/parc/vehicules/{v['id']}/pleins", json={"km": 100, "litres": 10}, headers=hm).status_code == 409   # compteur en recul


def test_montants_caches_au_moniteur_et_au_secretariat(client):
    hm, hmo, hs = entete(client, "mec"), entete(client, "mon"), entete(client, "sec")
    v = _vehicule(client, hm, prix_achat=9000000)
    client.post(f"/api/parc/vehicules/{v['id']}/pleins", json={"km": 10100, "litres": 30, "montant": 21000}, headers=hmo)
    assert "montant" not in client.get(f"/api/parc/vehicules/{v['id']}/pleins", headers=hmo).json()["pleins"][0]
    assert "montant" in client.get(f"/api/parc/vehicules/{v['id']}/pleins", headers=hm).json()["pleins"][0]
    assert "prix_achat" not in client.get("/api/parc/vehicules", headers=hs).json()[0] and "prix_achat" in client.get("/api/parc/vehicules", headers=hm).json()[0]
    assert client.get("/api/parc/synthese", headers=hmo).status_code == 403
    assert client.post("/api/parc/vehicules", json={"immatriculation": "ZZ", "marque": "a", "modele": "b"}, headers=hmo).status_code == 403


def test_panne_immobilisante_et_intervention_avec_pieces(client):
    hm = entete(client, "mec")
    v = _vehicule(client, hm)
    p = client.post(f"/api/parc/vehicules/{v['id']}/pannes", json={"description": "Embrayage HS", "gravite": "immobilisante"}, headers=entete(client, "mon")).json()
    assert client.get("/api/parc/vehicules", headers=hm).json()[0]["statut"] == "en_panne"
    assert client.put(f"/api/parc/vehicules/{v['id']}", json={"marque": "Toyota", "modele": "Yaris", "statut": "en_service"}, headers=hm).status_code == 409
    piece = client.post("/api/parc/pieces", json={"reference": "emb-01", "designation": "Kit d'embrayage", "stock": 1, "seuil_alerte": 1, "prix_unitaire": 45000}, headers=hm).json()
    i = client.post(f"/api/parc/vehicules/{v['id']}/interventions", json={"type": "reparation", "description": "Remplacement embrayage", "panne_id": p["id"], "pieces": [{"piece_id": piece["id"], "quantite": 2}]}, headers=hm).json()
    client.post(f"/api/parc/interventions/{i['id']}/demarrer", headers=hm)
    assert client.get("/api/parc/vehicules", headers=hm).json()[0]["statut"] == "en_maintenance"
    r = client.post(f"/api/parc/interventions/{i['id']}/terminer", json={"cout_main_oeuvre": 20000}, headers=hm)
    assert r.status_code == 409 and "Stock insuffisant" in r.text                                    # rien n'est décompté
    assert client.get("/api/parc/pieces", headers=hm).json()[0]["stock"] == 1
    client.post(f"/api/parc/pieces/{piece['id']}/mouvement", json={"type": "entree", "quantite": 1}, headers=hm)
    r = client.post(f"/api/parc/interventions/{i['id']}/terminer", json={"cout_main_oeuvre": 20000, "km": 10200}, headers=hm).json()
    assert r["cout_pieces"] == 90000 and r["cout_total"] == 110000
    v2 = client.get("/api/parc/vehicules", headers=hm).json()[0]
    assert v2["statut"] == "en_service" and v2["pannes_ouvertes"] == 0 and v2["km_actuel"] == 10200
    assert client.get("/api/parc/pieces", headers=hm).json()[0]["stock"] == 0


def test_pieces_mouvements_et_commandes(client):
    hm = entete(client, "mec")
    pc = client.post("/api/parc/pieces", json={"reference": "FLT-1", "designation": "Filtre à huile", "stock": 5, "seuil_alerte": 4, "prix_unitaire": 3000}, headers=hm).json()
    assert client.post(f"/api/parc/pieces/{pc['id']}/mouvement", json={"type": "sortie", "quantite": 9}, headers=hm).status_code == 409        # jamais négatif
    assert client.post(f"/api/parc/pieces/{pc['id']}/mouvement", json={"type": "ajustement", "quantite": 3}, headers=hm).status_code == 422     # motif obligatoire
    client.post(f"/api/parc/pieces/{pc['id']}/mouvement", json={"type": "ajustement", "quantite": 3, "motif": "Inventaire"}, headers=hm)
    sug = client.get("/api/parc/suggestions", headers=hm).json()
    assert sug[0]["quantite_conseillee"] == 5                                                          # 2 × 4 − 3
    f = client.post("/api/parc/fournisseurs", json={"nom": "Auto Pièces SA"}, headers=hm).json()
    c = client.post("/api/parc/commandes", json={"fournisseur_id": f["id"], "lignes": [{"piece_id": pc["id"], "quantite": 5, "prix_unitaire": 3200}], "envoyer": True}, headers=hm).json()
    assert c["numero"].endswith("-000001") and c["total"] == 16000 and c["statut"] == "commandee"
    assert client.post(f"/api/parc/commandes/{c['id']}/statut", json={"statut": "commandee"}, headers=hm).status_code == 409
    client.post(f"/api/parc/commandes/{c['id']}/statut", json={"statut": "recue", "recues": {pc["id"]: 4}}, headers=hm)
    p2 = client.get("/api/parc/pieces", headers=hm).json()[0]
    assert p2["stock"] == 7 and p2["prix_unitaire"] == 3200 and not p2["a_commander"]
    assert len(client.get(f"/api/parc/pieces/{pc['id']}/mouvements", headers=hm).json()) == 3
    assert client.get("/api/parc/commandes", headers=entete(client, "mon")).status_code == 403


def test_alertes_echeances_pastille_et_couts(client):
    hm = entete(client, "mec")
    v = _vehicule(client, hm, assurance_expire=(date.today() - timedelta(days=2)).isoformat(), visite_expire=(date.today() + timedelta(days=10)).isoformat(), km_actuel=20000)
    al = client.get("/api/parc/alertes", headers=hm).json()
    assert al[0]["niveau"] == "rouge" and "Assurance expirée" in al[0]["message"]
    assert any("Visite technique expire" in a["message"] for a in al) and any(a["type"] == "entretien" for a in al)
    assert client.get("/api/notifications/compteurs", headers=hm).json()["/parc"] == 1
    client.post(f"/api/parc/vehicules/{v['id']}/pleins", json={"km": 20300, "litres": 30, "montant": 21000}, headers=hm)
    s = client.get("/api/parc/synthese", headers=entete(client, "cpt")).json()
    assert s["total_carburant"] == 21000 and s["vehicules"][0]["km_periode"] == 300 and s["vehicules"][0]["cout_au_km"] == 70
