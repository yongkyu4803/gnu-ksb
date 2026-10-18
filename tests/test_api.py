from fastapi.testclient import TestClient
import pytest

from protinteract import main
from protinteract.core.uniprot import ProteinInfo


@pytest.fixture
def client(monkeypatch):
    def fake_fetch(ids, use_cache=True):
        return [ProteinInfo(uid, "not_found", message="찾을 수 없음") if uid == "BAD" else ProteinInfo(uid, "ok", accession=uid, sequence="ACDEFG", length=6) for uid in ids]
    monkeypatch.setattr(main, "fetch_many", fake_fetch)
    return TestClient(main.app)


def test_static_health_and_docs(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert client.get("/api/docs").status_code == 200


def test_partial_failure_and_download_contract(client):
    response = client.post("/api/v1/jobs/preview", json={"target_text": "P04637 2\nP04637 1", "candidate_text": "P04637 BAD P04637-2", "target_label": "my target"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["summary"] == {"total": 3, "included": 2, "excluded": 1}
    assert data["targets"][0]["count"] == 3 and data["warnings"]
    assert data["jobs"][0]["sequences"][0]["proteinChain"]["count"] == 4
    assert data["jobs"][1]["sequences"][1]["proteinChain"]["count"] == 1
    assert data["target_label"] == "my_target"


@pytest.mark.parametrize("payload", [
    {"target_text":"BAD", "candidate_text":"P04637"},
    {"target_text":"P04637 0", "candidate_text":"P04637"},
    {"target_text":"P04637", "candidate_text":" "},
    {"target_text":"P04637", "candidate_text":"Q00987", "token_limit":5001},
    {"target_text":"P04637", "candidate_text":"Q00987", "token_limit":True},
])
def test_rejected_requests(client, payload):
    response = client.post("/api/v1/jobs/preview", json=payload)
    assert response.status_code == 422 and "message" in response.json()["error"]


def test_lookup_and_no_jobs(client):
    data = client.post("/api/v1/proteins/lookup", json={"ids":"p04637,P04637; BAD"}).json()
    assert len(data["results"]) == 2
    data = client.post("/api/v1/jobs/preview", json={"target_text":"P04637", "candidate_text":"Q00987", "token_limit":10}).json()
    assert data["jobs"] == [] and data["preview"] is None
