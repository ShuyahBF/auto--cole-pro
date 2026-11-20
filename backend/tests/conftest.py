"""Fixtures de test : base MongoDB en mémoire (mongomock), une école de test (Burkina, FCFA) et un compte par rôle."""
import os
import sys

import mongomock
import pytest
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = "secret-de-test-assez-long-123456"
os.environ["PRESENCE_SAWALI"] = "0"
os.environ["FRONTEND_ORIGIN"] = "https://autoecole.test"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import db, ecoles, securite  # noqa: E402
from app.main import app  # noqa: E402

ECOLE = "ecole-test"
AGENCE = "agence-siege"


@pytest.fixture()
def client():
    base = mongomock.MongoClient()["test"]
    db.definir_base(base)
    db.creer_index(base)
    base.ecoles.insert_one({"id": ECOLE, "nom": "Auto-école Excellence", "prefixe": "EXC", "pays": "BF", "devise": "FCFA", "decimales": 0, "indicatif": "226", "actif": True,
                            "categories": ecoles.CATEGORIES_PAR_DEFAUT, "epreuves": ecoles.EPREUVES_PAR_DEFAUT, "pieces": ecoles.PIECES_PAR_DEFAUT,
                            "modes_paiement": ecoles.MODES_PAR_DEFAUT, "operateurs_mobile": []})
    db.fixer_ecole(ECOLE)
    base_vue = db.base()
    base_vue.agences.insert_one({"id": AGENCE, "nom": "Siège", "actif": True, "principale": True})
    for login, role in [("sa", "super_admin"), ("dir", "directeur"), ("ges", "gestionnaire"), ("sec", "secretaire"), ("cpt", "comptable"), ("mon", "moniteur"), ("mec", "mecanicien")]:
        base.utilisateurs.insert_one({"id": "id-" + login, "login": login, "nom_affiche": login, "role": role, "actif": True, "echecs": 0,
                                      "ecole_id": None if role == "super_admin" else ECOLE, "agence_id": None,
                                      "mot_de_passe_hash": securite.hacher_mot_de_passe("Motdepasse1"), "doit_changer_mdp": False})
    return TestClient(app)


def entete(client, login):
    """En-tête d'authentification pour le compte « login » (le super administrateur travaille dans l'école de test)."""
    r = client.post("/api/auth/login", json={"login": login, "mot_de_passe": "Motdepasse1"})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["jeton"]}
    if login == "sa":
        h["X-Ecole"] = ECOLE
    return h


def nouveau_tarif(client, h, code="B-STD", prix=150000, categorie="B", **extra):
    r = client.post("/api/tarifs", json={"code": code, "libelle": "Permis B standard", "categorie": categorie, "prix": prix, "heures_conduite": 20, "seances_code": 10, **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def nouvel_eleve(client, h, tarif, **extra):
    corps = {"nom": "Ouedraogo", "prenom": "Awa", "sexe": "F", "date_naissance": "2000-03-02", "telephone": "70000000", "categorie": "B", "tarif_id": tarif["id"], **extra}
    r = client.post("/api/eleves", json=corps, headers=h)
    assert r.status_code == 200, r.text
    return r.json()
