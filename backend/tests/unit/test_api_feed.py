import time

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def ids(company, **params):
    r = client.get(f"/clients/{company}/feed", params={"limit": 8, **params})
    assert r.status_code == 200
    return [e["event_id"] for e in r.json()["events"]], r.json()


def test_two_companies_get_different_feeds(demo_db):
    a, body = ids("U_S0001")
    b, _ = ids("U_S0002")
    assert a != b and set(a) != set(b)
    e = body["events"][0]
    assert e["reasons"] and e["topic_title"] and e["annotation"] and 0 <= e["score"] <= 1


def test_topic_filter_and_role(demo_db):
    fx, body = ids("U_S0004", topic="fx")
    assert fx and all(e["topic"] == "fx" for e in body["events"])
    r = client.get("/clients/U_S0004/feed", params={"role": "boss"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_role"


def test_unknown_client(demo_db):
    assert client.get("/clients/U_X/feed").status_code == 404


def test_refresh_and_speed(demo_db):
    t = time.perf_counter()
    r = client.post("/clients/U_S0001/feed/refresh")
    assert r.status_code == 200 and r.json()["events"] > 30
    assert time.perf_counter() - t < 5
