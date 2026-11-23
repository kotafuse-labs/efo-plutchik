"""オントロジーのドキュメント完全性テスト (FAIR Reusability)。

全 term (クラス/プロパティ/個体) が rdfs:label + skos:definition を持つことと、
定義欠落を doc_shapes.ttl (SHACL) が機械的に弾くことを検証する。学習不要・完全ローカル。
`pytest tests/test_ontology_docs.py`。
"""
import os

from rdflib import Graph, Namespace, RDF, RDFS
from rdflib.namespace import OWL, SKOS

from src.provenance.validate import validate_documentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTL = os.path.join(REPO, "ontology", "efo-plutchik.ttl")
SHAPES = os.path.join(REPO, "ontology", "doc_shapes.ttl")
PLU = Namespace("https://w3id.org/efo-plutchik#")

# v0.5.0: 型付き term（class / objectProperty / datatypeProperty / namedIndividual の和集合）= 94。
EXPECTED_TERMS = 94
DOC_TYPES = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.NamedIndividual)


def _graph():
    g = Graph()
    g.parse(TTL, format="turtle")
    return g


def test_documentation_conforms_default():
    """同梱オントロジーは doc-SHACL conforms かつ全 term に label+定義がある。"""
    assert validate_documentation(verbose=False) is True


def test_all_typed_terms_have_label_and_definition():
    """型付き term (94 個) が漏れなく rdfs:label と skos:definition を持つ (件数明示で silent regression 防止)。"""
    g = _graph()
    terms = set()
    for t in DOC_TYPES:
        terms |= set(g.subjects(RDF.type, t))
    assert len(terms) == EXPECTED_TERMS, f"型付き term 数 {len(terms)} != 期待 {EXPECTED_TERMS}"
    for s in terms:
        assert list(g.objects(s, RDFS.label)), f"{s} に rdfs:label がない"
        assert list(g.objects(s, SKOS.definition)), f"{s} に skos:definition がない"


def test_definitions_are_language_tagged():
    """skos:definition は言語タグ付き (rdf:langString)。ツールが言語別に読めることを担保。"""
    g = _graph()
    defs = [o for o in g.objects(None, SKOS.definition)]
    assert len(defs) == 2 * EXPECTED_TERMS   # v0.5.0: 各 term に @en と @ja
    assert all(getattr(o, "language", None) for o in defs), "言語タグを欠く定義がある"
    assert sum(o.language == "ja" for o in defs) == EXPECTED_TERMS


def test_doc_shacl_rejects_missing_definition():
    """ある term の skos:definition を除くと doc_shapes(SHACL) が non-conforming を返す (負例検出)。"""
    from pyshacl import validate

    g = _graph()
    # Love の定義を 1 つ削除 → 定義欠落を SHACL が弾くはず。
    removed = list(g.objects(PLU.Love, SKOS.definition))
    assert removed, "前提: Love に定義がある"
    g.remove((PLU.Love, SKOS.definition, removed[0]))

    shapes = Graph()
    shapes.parse(SHAPES, format="turtle")
    conforms, _, _ = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    assert conforms is False


def test_doc_shacl_rejects_missing_japanese_label():
    """v0.5.0: ある term の @ja ラベルを除くと、バイリンガルの doc SHACL が弾く。"""
    from pyshacl import validate

    g = _graph()
    ja = [o for o in g.objects(PLU.Serenity, RDFS.label) if o.language == "ja"]
    assert ja, "前提: Serenity に @ja ラベルがある"
    g.remove((PLU.Serenity, RDFS.label, ja[0]))
    shapes = Graph()
    shapes.parse(SHAPES, format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    assert conforms is False and "Japanese rdfs:label" in text
