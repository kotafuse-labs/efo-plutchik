"""VAD 生成スクリプト（ontology/build_vad.py、v0.5.0）のテスト。NRC の辞書は使わず、架空の小さな辞書で配線だけ確かめる。"""
import importlib.util
import os

from rdflib import Graph, Namespace, RDF
from rdflib.namespace import PROV

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLU = Namespace("https://w3id.org/efo-plutchik#")


def _mod():
    spec = importlib.util.spec_from_file_location("build_vad", os.path.join(REPO, "ontology", "build_vad.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_vad_readings_from_fixture(tmp_path):
    lex = tmp_path / "fake_vad.txt"
    lex.write_text("term\tvalence\tarousal\tdominance\njoy\t0.98\t0.82\t0.79\nserenity\t0.9\t0.1\t0.6\nunrelated\t0.5\t0.5\t0.5\n",
                   encoding="utf-8")
    m = _mod()
    g, missing = m.build(m.read_lexicon(str(lex)), "fake v0", "0..1")
    readings = set(g.subjects(RDF.type, PLU.VADReading))
    assert readings == {PLU.VAD_Joy, PLU.VAD_Serenity}
    assert float(g.value(PLU.VAD_Joy, PLU.vadValence)) == 0.98
    assert g.value(PLU.Joy, PLU.hasVADReading) == PLU.VAD_Joy
    assert all(g.value(r, PROV.wasDerivedFrom) is not None for r in readings)
    assert len(missing) == 48 - 2 and "trust" in missing   # 基本 8 + 変種 16 + dyad 24 = 48 語


def test_generated_vad_not_shipped():
    """NRC の利用条件のため、生成物は .gitignore で同梱しない。"""
    gi = open(os.path.join(REPO, ".gitignore"), encoding="utf-8").read()
    assert "ontology/plutchik-vad.ttl" in gi
