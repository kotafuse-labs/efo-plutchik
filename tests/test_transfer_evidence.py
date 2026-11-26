"""転移の証拠のモジュール 0.2.1（CombineEFOMoE #88 → #90、#91 → #92）のテスト。学習不要・完全ローカル。"""
import csv
import hashlib
import importlib.util
import os
from decimal import Decimal

import pytest
from rdflib import Graph, Literal, Namespace, RDF
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, XSD

from src.provenance.validate import _evidence_graph, run_evidence_cqs, validate_transfer_evidence

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONT = os.path.join(REPO, "ontology")
MAP = Namespace("https://w3id.org/efo-plutchik/mapping#")
EVD = Namespace("https://w3id.org/efo-plutchik/mapping/evidence#")
E1 = EVD["t2026_brighter_eng_anger__crowdenvent_anger"]
E2 = EVD["t2026b_brighter_eng_anger__crowdenvent_anger"]


@pytest.fixture(scope="module")
def graph():
    return _evidence_graph()


def _copy(g):
    c = Graph()
    for t in g:
        c.add(t)
    return c


def test_generated_file_is_up_to_date():
    spec = importlib.util.spec_from_file_location("build_transfer_evidence", os.path.join(ONT, "build_transfer_evidence.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isomorphic(mod.build(), Graph().parse(os.path.join(ONT, "plutchik-mapping-evidence.ttl")))


def test_counts_and_values_match_csv(graph):
    rows = list(csv.DictReader(open(os.path.join(ONT, "evidence", "crossdata_transfer_2026-11.csv"), encoding="utf-8")))
    ev = list(graph.subjects(EVD.fromStudy, EVD.CrossDatasetTransfer2026))
    assert len(rows) == len(ev) == 529 and len(list(graph.subjects(RDF.type, EVD.TransferEvidence))) == 1061
    r = [x for x in rows if (x["source_dataset"], x["source_label"], x["target_dataset"], x["target_label"]) == ("brighter_eng", "anger", "crowdenvent", "anger")][0]
    assert graph.value(E1, EVD.matchedAuc).toPython() == Decimal(r["matched_auc"]) and graph.value(E1, EVD.rankOneSeeds).toPython() == int(r["rank1_seeds"])
    assert graph.value(E1, EVD.sourceMapping) == MAP.pn_brighter_eng_anger and graph.value(E1, EVD.targetMapping) == MAP.pn_crowdenvent_anger
    verdicts = {v: sum(1 for e in ev if graph.value(e, EVD.preregisteredVerdict) == EVD[v]) for v in ("Supported", "Partial", "NotSupported")}
    assert verdicts == {"Supported": 385, "Partial": 110, "NotSupported": 34}


def test_mapping_module_is_untouched():
    g = Graph().parse(os.path.join(ONT, "plutchik-mappings.ttl"))
    onto = next(g.subjects(RDF.type, OWL.Ontology))
    assert str(g.value(onto, OWL.versionInfo)) == "0.6.1"
    assert hashlib.sha256(open(os.path.join(ONT, "plutchik-mappings.ttl"), "rb").read()).hexdigest().startswith("9bdaff5f")


def test_shacl_conforms(graph):
    assert validate_transfer_evidence(graph, verbose=False)


def _set(g, s, p, o):
    g.remove((s, p, None)); g.add((s, p, o))


@pytest.mark.parametrize("name", ["other_term", "same_dataset", "verdict_mismatch", "auc_out_of_range", "rank_counts", "duplicate", "study_without_limits", "not_a_name_mapping",
                                  "untyped_node", "missing_study", "unknown_mapping", "few_positives", "rank3_over_seeds", "not_close_match", "ten_seeds", "empty_study_text",
                                  "b_verdict_mismatch", "b_missing_training_positives", "b_few_training_positives_not_inconclusive", "unknown_study", "a_missing_rank3", "untyped_number_only"])
def test_negative_examples_are_rejected(graph, name):
    g = _copy(graph)
    if name == "other_term":
        _set(g, E1, EVD.targetMapping, MAP.pn_crowdenvent_joy)
    elif name == "same_dataset":
        _set(g, E1, EVD.targetMapping, MAP.pn_brighter_eng_anger)
    elif name == "verdict_mismatch":
        _set(g, E1, EVD.preregisteredVerdict, EVD.NotSupported)
    elif name == "auc_out_of_range":
        _set(g, E1, EVD.matchedAuc, Literal(Decimal("1.2"), datatype=XSD.decimal))
    elif name == "rank_counts":
        _set(g, E1, EVD.rankThreeSeeds, Literal(2, datatype=XSD.integer))
    elif name == "duplicate":
        for p, o in graph.predicate_objects(E1):
            g.add((EVD.dup, p, o))
    elif name == "study_without_limits":
        from rdflib.namespace import SKOS
        g.remove((EVD.CrossDatasetTransfer2026, SKOS.scopeNote, None))
    elif name == "b_verdict_mismatch":
        _set(g, E2, EVD.preregisteredVerdict, EVD.Mixed)
    elif name == "b_missing_training_positives":
        g.remove((E2, EVD.sourceTrainingPositives, None))
    elif name == "b_few_training_positives_not_inconclusive":
        _set(g, E2, EVD.sourceTrainingPositives, Literal(49, datatype=XSD.integer))
    elif name == "unknown_study":
        from rdflib.namespace import DCTERMS, SKOS
        s3 = EVD.ThirdStudy
        for p, o in graph.predicate_objects(EVD.CrossDatasetTransfer2026b):
            g.add((s3, p, o))
        _set(g, E2, EVD.fromStudy, s3)
    elif name == "a_missing_rank3":
        g.remove((E1, EVD.rankThreeSeeds, None))
    elif name == "untyped_number_only":
        g.add((EVD.junk, EVD.sourceTrainingPositives, Literal(10, datatype=XSD.integer)))
    elif name == "untyped_node":
        g.add((EVD.junk, EVD.sourceMapping, MAP.pn_brighter_eng_anger)); g.add((EVD.junk, EVD.matchedAuc, Literal(Decimal("9.9"), datatype=XSD.decimal)))
    elif name == "missing_study":
        g.remove((E1, EVD.fromStudy, None))
    elif name == "unknown_mapping":
        _set(g, E1, EVD.targetMapping, MAP.pn_no_such_record)
    elif name == "few_positives":
        _set(g, E1, EVD.targetPositives, Literal(19, datatype=XSD.integer))
    elif name == "rank3_over_seeds":
        _set(g, E1, EVD.rankThreeSeeds, Literal(6, datatype=XSD.integer))
    elif name == "not_close_match":
        from rdflib.namespace import SKOS
        _set(g, MAP.pn_crowdenvent_anger, MAP.matchType, SKOS.relatedMatch)
    elif name == "ten_seeds":
        _set(g, E1, EVD.seedCount, Literal(10, datatype=XSD.integer))
    elif name == "empty_study_text":
        from rdflib.namespace import DCTERMS, SKOS
        s2 = EVD.OtherStudy
        g.add((s2, RDF.type, EVD.EvidenceStudy)); g.add((s2, DCTERMS.description, Literal(""))); g.add((s2, SKOS.scopeNote, Literal("")))
        g.add((s2, DCTERMS.date, Literal("2026-11-27", datatype=XSD.date))); g.add((s2, DCTERMS.source, Literal("x")))
    else:
        other = [r for r in graph.subjects(MAP.inScheme, MAP.LimCheong2024) if graph.value(r, MAP.mapsTo) == graph.value(MAP.pn_crowdenvent_anger, MAP.mapsTo)]
        if not other:
            pytest.skip("Lim & Cheong の方式に、同じ語への記録が無い")
        _set(g, E1, EVD.sourceMapping, other[0])
    assert not validate_transfer_evidence(g, verbose=False)


def test_source_hashes_are_recorded(graph):
    import json
    from rdflib.namespace import DCTERMS
    for name, study, n in (("crossdata_transfer_2026-11", EVD.CrossDatasetTransfer2026, 529), ("crossdata_transfer_2026-11b", EVD.CrossDatasetTransfer2026b, 532)):
        src = json.load(open(os.path.join(ONT, "evidence", name + ".source.json"), encoding="utf-8"))
        recorded = {str(o) for o in graph.objects(study, DCTERMS.source)}
        assert src["n_pairs"] == n and all(f"sha256 {h} {k}" in recorded for k, h in {**src["inputs"], **src["scripts"]}.items())


def test_best_other_has_no_ties_with_matched(graph):
    """小数 6 桁なら、名前の合うラベルと最良のほかのラベルの同点は無い（4 桁では 1 組あった）。CQ-T1 の「上回る組」は 421。"""
    ev = list(graph.subjects(EVD.fromStudy, EVD.CrossDatasetTransfer2026))
    assert all(graph.value(e, EVD.matchedAuc) != graph.value(e, EVD.bestOtherAuc) for e in ev)
    assert sum(graph.value(e, EVD.matchedAuc).toPython() > graph.value(e, EVD.bestOtherAuc).toPython() for e in ev) == 421


def test_second_study(graph):
    """再実行（#91）: 532 件、判定の内訳、学習側の陽性の数、まれなラベルの扱い。"""
    ev = list(graph.subjects(EVD.fromStudy, EVD.CrossDatasetTransfer2026b))
    assert len(ev) == 532 and all(graph.value(e, EVD.sourceTrainingPositives) is not None for e in ev)
    verdicts = {v: sum(1 for e in ev if graph.value(e, EVD.preregisteredVerdict) == EVD[v]) for v in ("Supported", "Mixed", "NotSupported", "Inconclusive", "Partial")}
    assert verdicts == {"Supported": 412, "Mixed": 29, "NotSupported": 91, "Inconclusive": 0, "Partial": 0}
    fear = [e for e in ev if graph.value(e, EVD.sourceMapping) == MAP.pn_dailydialog_fear]
    assert len(fear) == 8 and all(graph.value(e, EVD.preregisteredVerdict) == EVD.Supported and graph.value(e, EVD.sourceTrainingPositives).toPython() == 124 for e in fear)
    from rdflib.namespace import DCTERMS, SKOS
    assert (EVD.CrossDatasetTransfer2026b, DCTERMS.relation, EVD.CrossDatasetTransfer2026) in graph
    assert any("read together with the re-run" in str(n) for n in graph.objects(EVD.CrossDatasetTransfer2026, SKOS.scopeNote))
    assert any("not an independent replication" in str(n) for n in graph.objects(EVD.CrossDatasetTransfer2026b, SKOS.scopeNote))


def test_competency_questions(graph):
    cq = run_evidence_cqs(graph, verbose=False)
    a = lambda rows: [r[1:] for r in rows if r[0].endswith("CrossDatasetTransfer2026")]
    b = lambda rows: [r[1:] for r in rows if r[0].endswith("CrossDatasetTransfer2026b")]
    assert len(a(cq["CQ-T1"])) == 14 and sum(int(r[1]) for r in a(cq["CQ-T1"])) == 529 and sum(int(r[1]) for r in b(cq["CQ-T1"])) == 532
    assert ("goodnewseveryone", "annoyance") in {(r[0], r[1]) for r in a(cq["CQ-T2"])} and ("goodnewseveryone", "annoyance") in {(r[0], r[1]) for r in a(cq["CQ-T3"])}
    assert ("dailydialog", "fear") in {(r[0], r[1]) for r in a(cq["CQ-T2"])} and ("dailydialog", "fear") not in {(r[0], r[1]) for r in b(cq["CQ-T2"])}
    assert len(cq["CQ-T4"]) == 23 and all(not (r[0] == "goemotions" and r[1] == "anger") for r in cq["CQ-T4"])
    assert any("dailydialog_fear__enisear_fear" in r[1] for r in cq["CQ-T5"])
    assert len(cq["CQ-T6"]) == 61 and sum(r[3].endswith("#Supported") for r in cq["CQ-T6"]) == 43
    assert sum(int(r[7]) for r in b(cq["CQ-T1"])) == 29 and all(len(r) == 10 for r in cq["CQ-T1"])       # 再実行の Mixed が列に出る
    t5b = [r for r in cq["CQ-T5"] if r[0].endswith("CrossDatasetTransfer2026b")]
    assert sum(r[4].endswith("#NotSupported") for r in t5b) == 20 and sum(r[4].endswith("#Mixed") for r in t5b) == 1
