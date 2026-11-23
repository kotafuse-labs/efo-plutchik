"""データセットラベル写像（v0.5.0、CombineEFOMoE #33）のテスト。学習不要・完全ローカル。

- plutchik-mappings.ttl が build_mappings.py の出力と一致する（生成物の手編集・生成忘れを弾く）。
- Plutchik2001Names 方式は mapping_shapes.ttl に conforms、負例は弾かれる。
- Lim & Cheong 方式の監査結果が CombineEFOMoE #22 の既知の結果と一致する。
"""
import os

from rdflib import Graph, Literal, Namespace, RDF
from rdflib.compare import isomorphic
from rdflib.namespace import SKOS

from src.provenance.validate import _mapping_graph, audit_mappings, validate_mappings

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLU = Namespace("https://w3id.org/efo-plutchik#")
MAP = Namespace("https://w3id.org/efo-plutchik/mapping#")


def _curated(g, ds, label):
    return MAP[f"pn_{ds}_{label}"]


def test_generated_file_is_up_to_date():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_mappings", os.path.join(REPO, "ontology", "build_mappings.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    on_disk = Graph(); on_disk.parse(os.path.join(REPO, "ontology", "plutchik-mappings.ttl"))
    assert isomorphic(mod.build(), on_disk), "plutchik-mappings.ttl が build_mappings.py の出力と違う（再生成すること）"


def test_curated_mappings_conform():
    assert validate_mappings(verbose=False) is True


def test_curated_mapping_counts():
    """SemEval 11 = closeMatch 11。GoEmotions 28 = closeMatch 15 + broadMatch 12 + 写さない 1（neutral）。"""
    g = _mapping_graph()
    def count(ds, mt=None, unmapped=False):
        n = 0
        for r in g.subjects(MAP.inScheme, MAP.Plutchik2001Names):
            if str(g.value(r, MAP.dataset)) != ds:
                continue
            if unmapped:
                n += (r, RDF.type, MAP.UnmappedLabel) in g
            else:
                n += g.value(r, MAP.matchType) == mt
        return n
    assert (count("semeval2018", SKOS.closeMatch), count("semeval2018", SKOS.broadMatch), count("semeval2018", unmapped=True)) == (11, 0, 0)
    assert (count("goemotions", SKOS.closeMatch), count("goemotions", SKOS.broadMatch), count("goemotions", unmapped=True)) == (15, 12, 1)


def test_intensity_and_dyad_targets():
    """強度の変種と dyad に写る代表例（名前の一致）。"""
    g = _mapping_graph()
    expect = {"admiration": PLU.Admiration, "annoyance": PLU.Annoyance, "grief": PLU.Grief,
              "curiosity": PLU.Curiosity, "pride": PLU.Pride, "remorse": PLU.Remorse, "love": PLU.Love}
    for lab, tgt in expect.items():
        assert g.value(_curated(g, "goemotions", lab), MAP.mapsTo) == tgt, lab
    assert g.value(_curated(g, "semeval2018", "pessimism"), MAP.mapsTo) == PLU.Pessimism


def test_close_match_requires_identical_name():
    """名前の違うものを closeMatch にすると SHACL が弾く（amusement を Joy へ closeMatch に改竄）。"""
    g = _mapping_graph()
    r = _curated(g, "goemotions", "amusement")
    g.set((r, MAP.matchType, SKOS.closeMatch))
    assert validate_mappings(graph=g, verbose=False) is False


def test_broad_match_must_target_basic_emotion():
    g = _mapping_graph()
    r = _curated(g, "goemotions", "relief")
    c = g.value(r, MAP.label)
    g.remove((c, SKOS.broadMatch, PLU.Joy))
    g.set((r, MAP.mapsTo, PLU.Serenity)); g.add((c, SKOS.broadMatch, PLU.Serenity))
    assert validate_mappings(graph=g, verbose=False) is False


def test_every_label_has_one_record_per_scheme():
    """ラベルの記録が欠けると網羅の SHACL が弾く。"""
    g = _mapping_graph()
    for t in list(g.triples((_curated(g, "goemotions", "caring"), None, None))):
        g.remove(t)
    assert validate_mappings(graph=g, verbose=False) is False


def test_unmapped_label_needs_reason():
    g = _mapping_graph()
    g.remove((_curated(g, "goemotions", "neutral"), MAP.basis, None))
    assert validate_mappings(graph=g, verbose=False) is False


def test_lim_cheong_audit_matches_known_findings():
    """CombineEFOMoE #22 の監査結果: confusion = Violation、disappointment / excitement = Warning。"""
    out = audit_mappings(verbose=False)
    assert out.get("Violation") == ["goemotions/confusion"]
    assert out.get("Warning") == ["goemotions/disappointment", "goemotions/excitement"]
    assert out.get("Info") == ["goemotions/admiration", "goemotions/annoyance", "goemotions/grief"]


# --- 写像の provenance CQ（mapping_cq.rq、CombineEFOMoE #36）---
_M5_EXPECTED = {
    ("amusement", "Joy", "Plutchik2001Names"), ("approval", "Joy", "Plutchik2001Names"), ("caring", "Joy", "Plutchik2001Names"),
    ("confusion", "Anticipation", "LimCheong2024"), ("desire", "Joy", "Plutchik2001Names"),
    ("disappointment", "Surprise", "LimCheong2024"), ("embarrassment", "Sadness", "Plutchik2001Names"),
    ("excitement", "Fear", "LimCheong2024"), ("gratitude", "Joy", "Plutchik2001Names"),
    ("nervousness", "Fear", "Plutchik2001Names"), ("realization", "Surprise", "Plutchik2001Names"),
    ("relief", "Joy", "Plutchik2001Names"),
}


def test_mapping_cqs_answer_and_completeness_holds():
    from src.provenance.validate import run_mapping_cqs
    r = run_mapping_cqs(verbose=False)
    assert r["CQ-M2"] == [] and r["CQ-M3"] == []
    labels = {(row[1], row[2]) for row in r["CQ-M1"]}
    assert len(labels) == 28 + 11                                   # GoEmotions 28 + SemEval 11 のラベルすべてが辿れる
    assert {(row[1], row[2].split("#")[1], row[3]) for row in r["CQ-M5"]} == _M5_EXPECTED
    assert all(row[0] == "goemotions" for row in r["CQ-M5"])         # SemEval は 2 方式で食い違わない


def test_mapping_cq_completeness_detects_gaps():
    from src.provenance.validate import run_mapping_cqs
    g = _mapping_graph()
    g.remove((MAP["pn_goemotions_amusement"], None, None))            # 1 方式で記録が欠ける
    g.remove((MAP["lc_goemotions_anger"], MAP.basis, None))           # 根拠が欠ける
    r = run_mapping_cqs(graph=g, verbose=False)
    assert [(row[1], row[2]) for row in r["CQ-M2"]] == [("goemotions", "amusement")]
    assert [row[1] for row in r["CQ-M3"]] == ["basis"]
