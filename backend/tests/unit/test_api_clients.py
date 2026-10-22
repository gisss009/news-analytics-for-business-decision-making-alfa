from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_clients_list(demo_db):
    r = client.get("/clients")
    data = r.json()
    assert r.status_code == 200 and len(data) == 35
    first = data[0]
    assert first["id"] == "U_S0001" and first["name"] == "СтройИнвест Девелопмент" and "кредиты" in first["products"]


def test_profile_has_sources(demo_db):
    r = client.get("/clients/U_S0002/profile")
    body = r.json()
    assert r.status_code == 200 and body["client"]["sector"] == "gold_mining"
    assert all(f["source"] for f in body["features"]) and len(body["exposures"]) == 10


def test_unknown_client_404(demo_db):
    r = client.get("/clients/U_NOPE/profile")
    assert r.status_code == 404 and r.json()["error"]["code"] == "client_not_found"


def test_roles():
    assert {r["id"] for r in client.get("/roles").json()} == {"ceo", "cfo", "treasurer", "accountant"}
