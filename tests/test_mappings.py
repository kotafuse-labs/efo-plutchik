"""データセットラベル写像（モジュール 0.6.0。v0.5.0 = CombineEFOMoE #33、追加のデータセット = #85）のテスト。学習不要・完全ローカル。

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
    assert len({x for x in labels if x[0] in ("goemotions", "semeval2018")}) == 28 + 11   # GoEmotions 28 + SemEval 11 のラベルすべてが辿れる
    assert len(labels) == 28 + 11 + 119 + 70                        # 追加の 10 データセットのラベル 119 個（CombineEFOMoE #85）と、0.7.0 の 9 データセットの 70 個（#102）
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


# ---- CombineEFOMoE #85: 追加のデータセット ----

def _count(g, ds, mt=None, unmapped=False):
    rs = [r for r in g.subjects(MAP.inScheme, MAP.Plutchik2001Names) if str(g.value(r, MAP.dataset)) == ds]
    return sum((r, RDF.type, MAP.UnmappedLabel) in g for r in rs) if unmapped else sum(g.value(r, MAP.matchType) == mt for r in rs)


def test_extra_dataset_counts():
    """追加の 10 データセット: closeMatch（名前の一致 + 表に載る語形）と、写さないラベルの数。broadMatch は使わない。"""
    g = _mapping_graph()
    expect = {"empatheticdialogues": (16, 16), "crowdenvent": (11, 2), "goodnewseveryone": (10, 5), "brighter_eng": (5, 0), "xed": (8, 1), "ssec": (8, 0),
              "enisear": (7, 0), "dailydialog": (5, 2), "semeval2018_eioc": (4, 0), "electoraltweets": (7, 12)}
    for ds, (close, un) in expect.items():
        assert (_count(g, ds, SKOS.closeMatch), _count(g, ds, SKOS.broadMatch), _count(g, ds, unmapped=True)) == (close, 0, un), ds
    assert sum(a + b for a, b in expect.values()) == 119


def test_transfer_replication_dataset_counts():
    """0.7.0（CombineEFOMoE #100 → #102）で足した 9 データセット: 規則と語形の表は変えていない。closeMatch 51、写さないラベル 19。"""
    g = _mapping_graph()
    expect = {"isear": (7, 0), "cbet": (8, 1), "carer": (6, 0), "tec": (6, 0), "meld": (6, 1), "rwwd": (5, 3), "senwave": (3, 7), "stockemotions": (5, 7), "universaljoy": (5, 0)}
    for ds, (close, un) in expect.items():
        assert (_count(g, ds, SKOS.closeMatch), _count(g, ds, SKOS.broadMatch), _count(g, ds, unmapped=True)) == (close, 0, un), ds
    assert (sum(a for a, _ in expect.values()), sum(b for _, b in expect.values())) == (51, 19)
    assert len(list(g.subjects(RDF.type, MAP.NameVariantRule))) == 16                                    # 語形の表は 0.6.1 のまま
    for lab in ("optimistic", "pessimistic", "thankful"):                                               # 表に無い語形は写さない
        assert (MAP[f"pn_senwave_{lab}"], RDF.type, MAP.UnmappedLabel) in g
    assert (MAP["pn_rwwd_happiness"], RDF.type, MAP.UnmappedLabel) in g
    assert {str(o).split("#")[1] for ds in ("cbet", "carer", "tec") for o in g.objects(MAP[f"{ds}_labels"], MAP.labellingMethod)} == {"DistantlySupervised"}
    assert (MAP.DistantlySupervised, RDF.type, MAP.LabellingMethod) in g


def test_name_variants_and_unmapped_reasons():
    g = _mapping_graph()
    r = MAP["pn_empatheticdialogues_terrified"]
    assert g.value(r, MAP.mapsTo) == PLU.Terror and str(g.value(r, MAP.nameVariantOf)) == "terror"
    assert g.value(MAP["pn_empatheticdialogues_hopeful"], MAP.mapsTo) == PLU.Hope
    for lab in ("afraid", "furious", "jealous", "content"):          # 表に無い語形・類義語は写さない
        assert (MAP[f"pn_empatheticdialogues_{lab}"], RDF.type, MAP.UnmappedLabel) in g, lab
    assert (MAP["pn_dailydialog_happiness"], RDF.type, MAP.UnmappedLabel) in g
    assert "Composite label" in str(g.value(MAP["pn_electoraltweets_calmness_or_serenity"], MAP.basis))
    assert "Qualified form" in str(g.value(MAP["pn_goodnewseveryone_negative_surprise"], MAP.basis))
    for lab in ("love_including_like", "negative_anticipation_including_pessimism", "positive_anticipation_including_optimism"):   # 0.6.1: データの複合のラベル
        assert (MAP[f"pn_goodnewseveryone_{lab}"], RDF.type, MAP.UnmappedLabel) in g, lab
    # 強度のクラス（EI-oc）は強度の変種に写さない: 写す先は基本感情だけ
    assert {g.value(r, MAP.mapsTo) for r in g.subjects(MAP.dataset, Literal("semeval2018_eioc"))} == {PLU.Anger, PLU.Fear, PLU.Joy, PLU.Sadness}


def test_scheme_scope_and_dataset_metadata():
    """Lim & Cheong の方式は 2 データセットだけが対象。追加のデータセットは、付け方・出典・確認元を持つ。"""
    g = _mapping_graph()
    assert {str(o).split("#")[1] for o in g.objects(MAP.LimCheong2024, MAP.coversDataset)} == {"semeval2018_labels", "goemotions_labels"}
    assert len(list(g.objects(MAP.Plutchik2001Names, MAP.coversDataset))) == 21
    assert not [r for r in g.subjects(MAP.inScheme, MAP.LimCheong2024) if str(g.value(r, MAP.dataset)) not in ("semeval2018", "goemotions")]
    assert g.value(MAP["empatheticdialogues_labels"], MAP.labellingMethod) == MAP.WriterChosen
    assert g.value(MAP["semeval2018_eioc_labels"], MAP.labellingMethod) == MAP.ScoreThresholded
    assert g.value(MAP["ssec_labels"], MAP.labellingMethod) == MAP.ReaderAnnotated


def test_name_variant_must_match_target_and_scope_is_enforced():
    g = _mapping_graph()
    r = MAP["pn_empatheticdialogues_terrified"]
    g.remove((r, MAP.nameVariantOf, None)); g.add((r, MAP.nameVariantOf, Literal("rage")))        # 語形の元の語が写す先と違う
    assert validate_mappings(graph=g, verbose=False) is False
    g = _mapping_graph()
    x = MAP["lc_ssec_anger"]                                                                     # 対象外の方式に記録を足す
    for t in ((x, RDF.type, MAP.UnmappedLabel), (x, MAP.inScheme, MAP.LimCheong2024), (x, MAP.label, MAP["ssec/anger"]), (x, MAP.basis, Literal("x"))):
        g.add(t)
    assert validate_mappings(graph=g, verbose=False) is False


def test_coverage_cqs_by_labelling_method():
    """CQ-M6 / M7: Plutchik の 48 語のうち、読み手の注釈で名前が対応するラベルを持たない語。"""
    from src.provenance.validate import run_mapping_cqs
    r = run_mapping_cqs(verbose=False)
    assert len(r["CQ-M6"]) == 48
    missing = {row[1].split("#")[1] for row in r["CQ-M7"]}
    assert {"Awe", "Contempt", "Submission", "Aggressiveness", "Rage", "Terror", "Ecstasy"} <= missing
    assert not ({"Anger", "Joy", "Love", "Optimism", "Pessimism", "Annoyance", "Admiration", "Pride", "Guilt", "Shame", "Grief", "Remorse", "Curiosity"} & missing)
    assert len(missing) == 24                                        # 48 語のうち 24 語に、読み手の注釈で名前が対応するラベルがある（0.7.0 で Anxiety が加わった: SenWave と StockEmotions）
    writer_only = {row[0].split("#")[1] for row in r["CQ-M6"] if int(row[2]) == 0 and int(row[3]) > 0}
    assert writer_only == {"Apprehension", "Boredom", "Hope", "Sentimentality", "Terror"}


def _bad(edit):
    g = _mapping_graph()
    edit(g)
    return validate_mappings(graph=g, verbose=False) is False


def test_name_variant_needs_a_listed_rule():
    """語形は、表（map:NameVariantRule）に載る組だけ。自己申告の nameVariantOf では closeMatch を正当化できない（#85 の監査）。"""
    def retarget(g):                                   # 写す先も語形の元の語も揃えて、別の感情に付け替える
        r = MAP["pn_empatheticdialogues_terrified"]
        for pr in (MAP.mapsTo, MAP.nameVariantOf):
            g.remove((r, pr, None))
        g.add((r, MAP.mapsTo, PLU.Rage)); g.add((r, MAP.nameVariantOf, Literal("rage")))
        g.remove((MAP["empatheticdialogues/terrified"], SKOS.closeMatch, None)); g.add((MAP["empatheticdialogues/terrified"], SKOS.closeMatch, PLU.Rage))
    assert _bad(retarget)

    def unlisted(g):                                   # 表に無い語形（afraid → Fear）
        r, c = MAP["pn_empatheticdialogues_afraid"], MAP["empatheticdialogues/afraid"]
        g.remove((r, RDF.type, MAP.UnmappedLabel)); g.add((r, RDF.type, MAP.ConceptMapping))
        g.add((r, MAP.mapsTo, PLU.Fear)); g.add((r, MAP.matchType, SKOS.closeMatch)); g.add((r, MAP.nameVariantOf, Literal("fear"))); g.add((c, SKOS.closeMatch, PLU.Fear))
    assert _bad(unlisted)
    assert _bad(lambda g: g.add((MAP["pn_xed_anger"], MAP.nameVariantOf, Literal("rage"))))                 # 名前が一致する記録に語形
    assert _bad(lambda g: g.add((MAP["pn_empatheticdialogues_terrified"], MAP.nameVariantOf, Literal("fear"))))   # 語形が 2 つ
    assert _bad(lambda g: g.add((MAP["pn_empatheticdialogues_afraid"], MAP.nameVariantOf, Literal("fear"))))      # 写さない記録に語形
    g = _mapping_graph()
    assert len(list(g.subjects(RDF.type, MAP.NameVariantRule))) == 16


def test_record_and_concept_integrity():
    """記録とラベル概念の一致、概念の所属、直接の SKOS の対応と記録の一致、データセットの付帯情報（#85 の監査）。"""
    assert _bad(lambda g: (g.remove((MAP["pn_xed_anger"], MAP.dataset, None)), g.add((MAP["pn_xed_anger"], MAP.dataset, Literal("ssec")))))
    assert _bad(lambda g: (g.remove((MAP["pn_xed_neutral"], MAP.sourceLabel, None)), g.add((MAP["pn_xed_neutral"], MAP.sourceLabel, Literal("joy")))))
    assert _bad(lambda g: g.remove((MAP["pn_xed_anger"], RDF.type, MAP.ConceptMapping)))                      # 種類の無い記録
    assert _bad(lambda g: g.add((MAP["xed/neutral"], SKOS.closeMatch, PLU.Joy)))                              # 記録の無い直接の対応
    assert _bad(lambda g: g.add((MAP["orphan"], RDF.type, SKOS.Concept)))                                     # どの体系にも属さない概念
    for pr in (MAP.labellingMethod, MAP.labelsCheckedIn, MAP.datasetKey):
        assert _bad(lambda g, pr=pr: g.remove((MAP["ssec_labels"], pr, None))), pr


def test_no_licence_strings_and_version():
    """利用条件は記録しない（配布元を見る）。写像のモジュールは 0.7.0 で、コア 0.5.0 を import する。"""
    from rdflib.namespace import DCTERMS, OWL
    from rdflib import URIRef
    g = _mapping_graph()
    assert not [1 for cs in g.subjects(RDF.type, SKOS.ConceptScheme) for _ in g.objects(cs, DCTERMS.rights)]
    onto = URIRef("https://w3id.org/efo-plutchik/mapping")
    assert str(g.value(onto, OWL.versionInfo)) == "0.7.0" and g.value(onto, OWL.imports) == URIRef("https://w3id.org/efo-plutchik/0.5.0")

