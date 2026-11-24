"""Connexion par compte Google (AutoÉcole Pro). Aucun accès réseau : l'échange du code avec Google est simulé."""
import base64
import json
import time

import pytest

from app import db, google, google_auth
from tests.conftest import entete

CLIENT = "client-test.apps.googleusercontent.com"


def _identite(sub="g-1", email="awa.badini@gmail.com"):
    return {"sub": sub, "email": email, "nom": "BADINI Awa"}


@pytest.fixture
def google_actif(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret-test")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://api.test/auth/google/retour")


def _simuler(monkeypatch, identite):
    monkeypatch.setattr(google, "_echanger_code", lambda code, uri: identite)


def _etat(cible="web", lier=None):
    return google_auth.signer_etat(cible, lier, "secret-de-test-assez-long-123456")


def test_inactif_sans_configuration(client):
    assert client.get("/api/auth/google/config").json() == {"disponible": False}
    assert client.get("/api/auth/google/demarrer", follow_redirects=False).status_code == 503


def test_liaison_puis_connexion_puis_code_a_usage_unique(client, google_actif, monkeypatch):
    h = entete(client, "dir")
    url = client.post("/api/auth/google/lier-url", json={"cible": "web"}, headers=h).json()["url"]
    assert url.startswith("https://accounts.google.com/")
    _simuler(monkeypatch, _identite("g-dir"))
    r = client.get("/api/auth/google/retour", params={"code": "c", "state": _etat("web", "id-dir")}, follow_redirects=False)
    assert r.status_code == 302 and "lie=1" in r.headers["location"]
    assert client.get("/api/auth/google/etat", headers=h).json()["lie"] is True
    r = client.get("/api/auth/google/retour", params={"code": "c", "state": _etat()}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1]
    ok = client.post("/api/auth/google/echange", json={"code": code})
    assert ok.status_code == 200 and ok.json()["login"] == "dir" and ok.json()["jeton"]
    assert client.post("/api/auth/google/echange", json={"code": code}).status_code == 401      # usage unique


def test_identite_inconnue_ne_cree_aucun_compte(client, google_actif, monkeypatch):
    _simuler(monkeypatch, _identite("g-inconnu"))
    r = client.get("/api/auth/google/retour", params={"code": "c", "state": _etat()}, follow_redirects=False)
    assert "erreur=aucun_compte" in r.headers["location"]


def test_un_etat_falsifie_est_refuse(client, google_actif):
    r = client.get("/api/auth/google/retour", params={"code": "c", "state": "faux.faux"}, follow_redirects=False)
    assert "erreur=etat" in r.headers["location"]


def test_cible_application_renvoie_la_page_avec_le_lien_application(client, google_actif, monkeypatch):
    _simuler(monkeypatch, _identite("g-inconnu2"))
    r = client.get("/api/auth/google/retour", params={"code": "c", "state": _etat("app")})
    assert r.status_code == 200 and "autoecolepro://google?" in r.text


def test_delier_exige_le_mot_de_passe(client, google_actif, monkeypatch):
    h = entete(client, "sec")
    _simuler(monkeypatch, _identite("g-sec"))
    client.get("/api/auth/google/retour", params={"code": "c", "state": _etat("web", "id-sec")}, follow_redirects=False)
    assert client.post("/api/auth/google/delier", json={"mot_de_passe": "faux"}, headers=h).status_code == 401
    assert client.post("/api/auth/google/delier", json={"mot_de_passe": "Motdepasse1"}, headers=h).status_code == 200
    assert client.get("/api/auth/google/etat", headers=h).json()["lie"] is False
