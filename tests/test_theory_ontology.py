"""理論グラフ (efo-plutchik.ttl) 自体の構造検証・論理一貫性のテスト (Tier2 ④⑤)。

学習不要・完全ローカル。`pytest tests/test_theory_ontology.py`。
"""
import os

from rdflib import Graph, Literal, Namespace, RDF
from rdflib.namespace import OWL

from src.provenance.validate import validate_theory_graph, check_theory_consistency

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTL = os.path.join(REPO, "ontology", "efo-plutchik.ttl")
PLU = Namespace("https://w3id.org/efo-plutchik#")


def _theory_graph():
    g = Graph()
    g.parse(TTL, format="turtle")
    return g


# ---------- ④ TBox SHACL + カーディナリティ ----------

def test_theory_graph_conforms_default():
    """同梱の理論グラフは SHACL conforms かつ v0.5.0 のカーディナリティ（基本 8・dyad 24・変種 16・対極 4・隣接 8・成分 48）を満たす。"""
    assert validate_theory_graph(verbose=False) is True


def test_theory_shacl_rejects_opposite_components():
    """primary dyad の構成 2 感情が対極ペアだと SHACL が弾く (カーディナリティは不変で SHACL を分離)。"""
    g = _theory_graph()
    # Love = Joy + Trust → Joy + Sadness に改竄 (Joy と Sadness は対極)。
    # 構成数 2・dyad 数・component 48・opposite 4 は不変 → 純粋に SHACL の制約が発火。
    g.remove((PLU.Love, PLU.hasComponentEmotion, PLU.Trust))
    g.add((PLU.Love, PLU.hasComponentEmotion, PLU.Sadness))
    assert validate_theory_graph(graph=g, verbose=False) is False


def test_theory_counts_reject_extra_dyad():
    """primary dyad を 1 つ増やすとカーディナリティ sanity が False を返す。"""
    g = _theory_graph()
    extra = PLU.ExtraDyad
    g.add((extra, RDF.type, OWL.NamedIndividual))
    g.add((extra, RDF.type, PLU.PrimaryDyad))
    g.add((extra, PLU.hasComponentEmotion, PLU.Joy))
    g.add((extra, PLU.hasComponentEmotion, PLU.Trust))
    assert validate_theory_graph(graph=g, verbose=False) is False


# ---------- ⑤ OWL-RL 一貫性 ----------

def test_theory_consistent_default():
    """同梱の理論グラフは OWL-RL 閉包で論理一貫 (disjoint clash なし)。"""
    assert check_theory_consistency(verbose=False) is True


def test_consistency_detects_basic_compound_clash():
    """基本感情を dyad に混入させると、閉包で BasicEmotion ∧ CompoundEmotion 衝突を検出する。"""
    g = _theory_graph()
    g.add((PLU.Joy, RDF.type, PLU.Dyad))  # Dyad ⊂ CompoundEmotion → 閉包で衝突
    assert check_theory_consistency(graph=g, verbose=False) is False


# ---------- v0.5.0: dyad 24・強度の変種・wheel の幾何 ----------

def test_secondary_dyad_wrong_wheel_distance_rejected():
    """secondary dyad の成分を隣接ペアに替えると、wheel 距離の SHACL が弾く（Guilt = Joy+Fear → Joy+Trust）。"""
    g = _theory_graph()
    g.remove((PLU.Guilt, PLU.hasComponentEmotion, PLU.Fear))
    g.add((PLU.Guilt, PLU.hasComponentEmotion, PLU.Trust))
    assert validate_theory_graph(graph=g, verbose=False) is False


def test_missing_dyad_for_pair_rejected():
    """非対極の組に dyad が無いと「各組ちょうど 1 dyad」の SHACL が弾く（Anxiety を削除）。"""
    g = _theory_graph()
    for t in list(g.triples((PLU.Anxiety, None, None))):
        g.remove(t)
    from pyshacl import validate
    shapes = Graph(); shapes.parse(os.path.join(REPO, "ontology", "theory_shapes.ttl"))
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    assert conforms is False and "exactly one dyad" in text


def test_duplicate_wheel_position_rejected():
    """wheel 上の位置が重複すると SHACL が弾く。"""
    g = _theory_graph()
    g.remove((PLU.Trust, PLU.wheelPosition, None))
    g.add((PLU.Trust, PLU.wheelPosition, Literal(0)))
    assert validate_theory_graph(graph=g, verbose=False) is False


def test_wrong_adjacency_rejected():
    """wheel 上で隣り合わない組に isAdjacentTo を張ると SHACL が弾く。"""
    g = _theory_graph()
    g.add((PLU.Joy, PLU.isAdjacentTo, PLU.Fear))
    assert validate_theory_graph(graph=g, verbose=False) is False


def test_intensity_variants_need_distinct_levels():
    """同じ基本感情の 2 つの変種が同じ強度段階だと SHACL が弾く（Ecstasy を low に）。"""
    g = _theory_graph()
    g.remove((PLU.Ecstasy, PLU.hasIntensityLevel, PLU.HighIntensity))
    g.add((PLU.Ecstasy, PLU.hasIntensityLevel, PLU.LowIntensity))
    assert validate_theory_graph(graph=g, verbose=False) is False


def test_consistency_detects_variant_basic_clash():
    """強度の変種を基本感情としても型付けすると、AllDisjointClasses で衝突を検出する。"""
    g = _theory_graph()
    g.add((PLU.Serenity, RDF.type, PLU.BasicEmotion))
    assert check_theory_consistency(graph=g, verbose=False) is False


def test_consistency_detects_dyad_kind_clash():
    """dyad を primary と secondary の両方に型付けすると、AllDisjointClasses で衝突を検出する。"""
    g = _theory_graph()
    g.add((PLU.Love, RDF.type, PLU.SecondaryDyad))
    assert check_theory_consistency(graph=g, verbose=False) is False
