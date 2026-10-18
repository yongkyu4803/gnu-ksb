from unittest.mock import Mock

from protinteract.core import uniprot as u
from protinteract.core.af_json import TargetChain, merge_targets, plan_jobs, build_jobs
from protinteract import main
from fastapi.testclient import TestClient


def test_merged_and_inactive():
    merged = u._from_json("Q00987", {"primaryAccession":"P04637", "sequence":{"value":"ACDEFG", "length":6}})
    assert merged.status == "merged" and "P04637" in merged.message
    inactive = u._from_json("Q00987", {"entryType":"Inactive", "inactiveReason":{"inactiveReasonType":"DELETED"}})
    assert inactive.status == "inactive"
    targets, warnings = merge_targets([TargetChain(merged), TargetChain(u.ProteinInfo("P04637", "ok", accession="P04637", sequence="ACDEFG", length=6), 2)])
    assert targets[0].count == 3 and warnings


def test_non_string_sequence_and_certificate_error(monkeypatch):
    assert u._from_json("P04637", {"primaryAccession":"P04637", "sequence":{"value":123, "length":4}}).status == "error"
    monkeypatch.setattr(u.requests, "get", Mock(side_effect=OSError("invalid certificate")))
    assert "인증서" in u.fetch_protein("P04637", False).message


def test_actual_fetch_parser_exclusion_through_api(tmp_path, monkeypatch):
    monkeypatch.setattr(u, "CACHE_DIR", tmp_path)
    def get(url, **kwargs):
        response = Mock(ok=True, status_code=200)
        uid = url.rsplit("/", 1)[1].removesuffix(".json")
        response.json.return_value = {"primaryAccession":uid, "sequence":{"value":"ACDEFG" if uid == "P04637" else ""}}
        return response
    monkeypatch.setattr(u.requests, "get", get)
    result = TestClient(main.app).post("/api/v1/jobs/preview", json={"target_text":"P04637", "candidate_text":"Q00987", "use_cache":False})
    assert result.status_code == 200
    assert result.json()["jobs"] == []
    assert "빈 서열" in result.json()["plans"][0]["note"]


def test_exact_server_token_boundary():
    target = [TargetChain(u.ProteinInfo("P04637", "ok", accession="P04637", sequence="A"*2500, length=2500))]
    candidate = u.ProteinInfo("Q00987", "ok", accession="Q00987", sequence="A"*2500, length=2500)
    plans = plan_jobs(target, [candidate], "test")
    assert plans[0].included and plans[0].tokens == 5000
    assert len(build_jobs(plans, target)) == 1
