"""Tests du lot 2 : examens (sessions, éligibilité, résultats, diplôme), séances et livret, transferts, statistiques."""
from datetime import date, timedelta

from tests.conftest import entete, nouveau_tarif, nouvel_eleve

PIECES = {"identite": True, "photos": True, "naissance": True, "medical": True}


def _eleve_pret(client, h, tarif, **extra):
    e = nouvel_eleve(client, h, tarif, **extra)
    client.put(f"/api/eleves/{e['id']}", json={"pieces": PIECES}, headers=h)
    return e


def _session(client, h, epreuve="code", type="interne", jours=3, **extra):
    r = client.post("/api/examens/sessions", json={"type": type, "epreuve": epreuve, "categorie": "B", "date": (date.today() + timedelta(days=jours)).isoformat(), "heure": "08:30",
                                                    "lieu": "Centre d'examen", "capacite": 2, **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_eligibilite_et_capacite(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    s = _session(client, hs)
    incomplet = nouvel_eleve(client, hs, t, nom="Incomplet", prenom="Dossier")
    r = client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": incomplet["id"]}, headers=hs)
    assert r.status_code == 409 and "Dossier incomplet" in r.text
    e1, e2, e3 = (_eleve_pret(client, hs, t, nom=f"Candidat{i}", prenom="X") for i in range(3))
    assert client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e1["id"]}, headers=hs).status_code == 200
    assert client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e1["id"]}, headers=hs).status_code == 409     # déjà inscrit
    assert client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e2["id"]}, headers=hs).status_code == 200
    assert "complète" in client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e3["id"]}, headers=hs).text
    assert client.get(f"/api/examens/sessions/{s['id']}", headers=hs).json()["places_restantes"] == 0
    # L'aide à l'inscription annonce les motifs
    el = {x["nom"]: x["motifs"] for x in client.get(f"/api/examens/sessions/{s['id']}/eligibles", headers=hs).json()}
    assert any("Dossier incomplet" in m for m in el["INCOMPLET Dossier"])


def test_ordre_des_epreuves_resultats_et_permis(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    e = _eleve_pret(client, hs, t)
    conduite = _session(client, hs, epreuve="conduite", type="externe")
    # La conduite exige d'avoir réussi le code
    assert "précédente" in client.post(f"/api/examens/sessions/{conduite['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs).text
    code = _session(client, hs, epreuve="code", type="externe", jours=1)
    ins = client.post(f"/api/examens/sessions/{code['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs).json()
    assert ins["tentative"] == 1
    assert client.get(f"/api/examens/inscriptions/{ins['id']}/convocation", headers=hs).content.startswith(b"%PDF")
    assert client.get(f"/api/examens/sessions/{code['id']}/presence", headers=hs).content.startswith(b"%PDF")
    r = client.post(f"/api/examens/sessions/{code['id']}/resultats", json={"resultats": [{"inscription_id": ins["id"], "statut": "ajourne", "note": 22}], "cloturer": True}, headers=hs)
    assert r.status_code == 200 and r.json()["statut"] == "terminee" and r.json()["ajournes"] == 1
    # Session terminée : plus d'inscription ; nouvelle session, 2e tentative, admis
    code2 = _session(client, hs, epreuve="code", type="externe", jours=2)
    ins2 = client.post(f"/api/examens/sessions/{code2['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs).json()
    assert ins2["tentative"] == 2
    client.post(f"/api/examens/sessions/{code2['id']}/resultats", json={"resultats": [{"inscription_id": ins2["id"], "statut": "admis", "note": 35}]}, headers=hs)
    ins3 = client.post(f"/api/examens/sessions/{conduite['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs)
    assert ins3.status_code == 200
    r = client.post(f"/api/examens/sessions/{conduite['id']}/resultats", json={"resultats": [{"inscription_id": ins3.json()["id"], "statut": "admis"}]}, headers=hs)
    assert r.json()["nouveaux_diplomes"] == 1
    fiche = client.get(f"/api/eleves/{e['id']}", headers=hs).json()
    assert fiche["statut"] == "diplome" and fiche["date_permis"]
    assert len(client.get(f"/api/eleves/{e['id']}/examens", headers=hs).json()) == 3


def test_impaye_en_retard_bloque_examen_externe(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd, prix=100000)
    e = _eleve_pret(client, hs, t)
    client.put(f"/api/eleves/{e['id']}", json={"echeances": [{"date": (date.today() - timedelta(days=3)).isoformat(), "montant": 50000}]}, headers=hs)
    ext = _session(client, hs, type="externe")
    assert "Impayé" in client.post(f"/api/examens/sessions/{ext['id']}/inscriptions", json={"eleve_id": e["id"], "forcer": True}, headers=hd).text   # jamais forcé en externe
    interne = _session(client, hs, type="interne", jours=2)
    assert client.post(f"/api/examens/sessions/{interne['id']}/inscriptions", json={"eleve_id": e["id"]}, headers=hs).status_code == 409
    assert client.post(f"/api/examens/sessions/{interne['id']}/inscriptions", json={"eleve_id": e["id"], "forcer": True}, headers=hd).status_code == 200


def test_planning_et_statistiques(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd)
    s = _session(client, hs, jours=1, capacite=5)
    assert client.get("/api/examens/planning?mois=" + s["date"][:7], headers=hs).json()["total_sessions"] >= 1
    e1, e2 = _eleve_pret(client, hs, t, nom="Un", prenom="A"), _eleve_pret(client, hs, t, nom="Deux", prenom="B")
    i1 = client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e1["id"]}, headers=hs).json()
    i2 = client.post(f"/api/examens/sessions/{s['id']}/inscriptions", json={"eleve_id": e2["id"]}, headers=hs).json()
    client.post(f"/api/examens/sessions/{s['id']}/resultats", json={"resultats": [{"inscription_id": i1["id"], "statut": "admis"}, {"inscription_id": i2["id"], "statut": "absent"}], "cloturer": True}, headers=hs)
    st = client.get(f"/api/statistiques/examens?au={s['date']}", headers=hd).json()
    assert st["passes"] == 1 and st["admis"] == 1 and st["taux_global"] == 100.0 and st["par_epreuve"][0]["absents"] == 1
    assert client.get("/api/statistiques/examens", headers=hs).status_code == 403


def test_livret_et_seances(client):
    hs, hd, hm = entete(client, "sec"), entete(client, "dir"), entete(client, "mon")
    t = nouveau_tarif(client, hd)
    e = nouvel_eleve(client, hs, t)
    assert client.post(f"/api/eleves/{e['id']}/seances", json={"duree_min": 5}, headers=hm).status_code == 422
    r = client.post(f"/api/eleves/{e['id']}/seances", json={"duree_min": 60, "theme": "Créneaux", "appreciation": "en_progres", "km": 12}, headers=hm)
    assert r.status_code == 200
    client.post(f"/api/eleves/{e['id']}/seances", json={"duree_min": 30, "type": "code"}, headers=hm)
    liv = client.get(f"/api/eleves/{e['id']}/seances", headers=hm).json()
    assert liv["heures_conduite"] == 1.0 and liv["heures_prevues"] == 20 and liv["seances_code"] == 1 and liv["km"] == 12
    assert client.get(f"/api/eleves/{e['id']}", headers=hs).json()["statut"] == "en_formation"
    assert client.delete(f"/api/seances/{r.json()['id']}", headers=hm).status_code == 403            # le moniteur ne corrige pas
    assert client.get("/api/seances", headers=hm).json()["heures_par_moniteur"] == {"mon": 1.5}


def test_transferts(client):
    hs, hd = entete(client, "sec"), entete(client, "dir")
    t = nouveau_tarif(client, hd, prix=100000)
    e = nouvel_eleve(client, hs, t)
    bobo = client.post("/api/agences", json={"nom": "Bobo"}, headers=hd).json()
    assert client.post("/api/transferts/agence", json={"eleve_id": e["id"], "agence_id": bobo["id"]}, headers=hs).status_code == 403     # secrétaire : non
    assert client.post("/api/transferts/agence", json={"eleve_id": e["id"], "agence_id": bobo["id"], "motif": "Déménagement"}, headers=hd).status_code == 200
    assert client.get(f"/api/eleves/{e['id']}", headers=hd).json()["agence_nom"] == "Bobo"
    assert client.post("/api/transferts/agence", json={"eleve_id": e["id"], "agence_id": bobo["id"]}, headers=hd).status_code == 409
    # Sortant avec reste dû : confirmation exigée
    assert client.post("/api/transferts/sortant", json={"eleve_id": e["id"], "ecole_destination": "Auto-école Sahel"}, headers=hd).status_code == 409
    r = client.post("/api/transferts/sortant", json={"eleve_id": e["id"], "ecole_destination": "Auto-école Sahel", "accepter_solde": True}, headers=hd)
    assert r.status_code == 200 and r.json()["solde_restant"] == 100000
    assert client.get(f"/api/eleves/{e['id']}", headers=hd).json()["statut"] == "transfere"
    pdf = client.get(f"/api/transferts/{r.json()['id']}/dossier", headers=hd)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    # Entrant : inscription + origine, heures reprises dans le livret
    ent = client.post("/api/transferts/entrant", json={"nom": "Venu", "prenom": "Ailleurs", "date_naissance": "1999-05-05", "telephone": "70998877", "categorie": "B", "tarif_id": t["id"],
                                                        "ecole_origine": "Auto-école Nord", "heures_deja_faites": 8}, headers=hd)
    assert ent.status_code == 200, ent.text
    assert client.get(f"/api/eleves/{ent.json()['id']}/seances", headers=hd).json()["heures_conduite"] == 8
    assert len(client.get("/api/transferts", headers=hd).json()) == 3
