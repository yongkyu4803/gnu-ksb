import json
from dataclasses import asdict
from unittest.mock import Mock

import pytest
import requests

from protinteract.core import uniprot as u
from protinteract.core import af_json as af


def protein(uid="P04637", sequence="ACDEFG"):
    return u.ProteinInfo(uid, "ok", accession=uid, sequence=sequence, length=len(sequence))


@pytest.mark.parametrize("sequence", ["", "ABCX", "acdef", "AAA", "AA AA"])
def test_bad_sequences_are_not_jobs(sequence):
    info = u._from_json("P04637", {"primaryAccession": "P04637", "sequence": {"value": sequence}})
    assert info.status == "error"
    plans = af.plan_jobs([af.TargetChain(protein())], [info], "target")
    assert not plans[0].included
    with pytest.raises(ValueError):
        af.build_job("test", [(sequence, 1)])


def test_json_length_and_shape_validation():
    assert u._from_json("P04637", {"primaryAccession": "P04637", "sequence": {"value": "ACDE", "length": 9}}).status == "error"
    with pytest.raises(ValueError):
        u._from_json("P04637", [])


def test_fasta_preserves_isoform_and_rejects_wrong_response():
    fasta = ">sp|P04637-2|P53_HUMAN Protein OS=Homo sapiens OX=9606 GN=TP53\nACDEFG\n"
    info = u._from_fasta("P04637-2", fasta)
    assert info.status == "ok" and info.accession == "P04637-2"
    assert u._from_fasta("P04637-3", fasta).status == "error"
    for text in ["", "not fasta", fasta + fasta]:
        with pytest.raises(ValueError):
            u._from_fasta("P04637-2", text)


def test_parse_and_merge_keep_isoforms():
    assert u.parse_id_list("p04637, P04637; P04637-2") == ["P04637", "P04637-2"]
    entries, errors = af.parse_target_lines("P04637 2\np04637 1\nQ00987 0")
    assert entries == [("P04637", 3)] and errors
    alias = protein("Q00987")
    alias.accession = "P04637"
    targets, warnings = af.merge_targets([af.TargetChain(protein(), 2), af.TargetChain(alias), af.TargetChain(protein("P04637-2"))])
    assert [t.count for t in targets] == [3, 1] and warnings


def test_counts_tokens_self_candidate_and_duplicate():
    target = [af.TargetChain(protein(), 2)]
    plans = af.plan_jobs(target, [protein(), protein(), protein("Q00987")], "target", 18)
    assert [p.included for p in plans] == [True, False, True]
    assert "최종 3개" in plans[0].note
    jobs = af.build_jobs(plans, target)
    assert jobs[0]["sequences"] == [{"proteinChain": {"sequence": "ACDEFG", "count": 3}}]
    assert len(jobs[1]["sequences"]) == 2  # 같은 서열이어도 다른 ID는 별도 항목
    assert not af.plan_jobs(target, [protein("Q00987")], "target", 17)[0].included
    with pytest.raises(ValueError):
        af.build_job("big", [("A" * 5001, 1)])


def test_names_and_preview_do_not_change_download():
    target = [af.TargetChain(protein(sequence="A" * 30))]
    plans = af.plan_jobs(target, [protein("Q00987"), protein("P04637-2")], "a" * 100)
    jobs = af.build_jobs(plans, target)
    assert len({j["name"] for j in jobs}) == 2
    af.shorten_for_preview(jobs[0])
    assert jobs[0]["sequences"][0]["proteinChain"]["sequence"] == "A" * 30


def test_cache_validation_force_refresh_and_network_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(u, "CACHE_DIR", tmp_path)
    response = Mock(ok=True, status_code=200)
    response.json.return_value = {"primaryAccession": "P04637", "sequence": {"value": "ACDEFG", "length": 6}}
    get = Mock(return_value=response)
    monkeypatch.setattr(u.requests, "get", get)
    assert u.fetch_protein("P04637").status == "ok"
    assert u.fetch_protein("P04637").status == "ok"
    assert get.call_count == 1
    u.fetch_protein("P04637", use_cache=False)
    assert get.call_count == 2
    # Old or tampered caches cannot bypass validation.
    saved = json.loads((tmp_path / "P04637.json").read_text())
    saved["protein"]["sequence"] = ""
    (tmp_path / "P04637.json").write_text(json.dumps(saved))
    assert u.fetch_protein("P04637").sequence == "ACDEFG"
    assert get.call_count == 3
    get.side_effect = requests.Timeout()
    assert u.fetch_protein("P04637", False).status == "error"
    get.side_effect = None
    response.status_code = 404
    assert u.fetch_protein("P04637", False).status == "not_found"
    assert u.fetch_protein("invalid").status == "invalid"
