"""EFO との vocabulary-level alignment を機械検証するテスト (Tier1 ③)。

owl:imports は宣言上の参照に留まるため、実際の整合は共有 IRI (emo:/be:) + skos:closeMatch。
本テストは owl:imports をローカルキャッシュ (ontology/efo-src/、gitignore) で解決し、efo-plutchik が
参照する EFO 用語が「実際の EFO 定義」に解決することを確認する。EFO はリポに含めない
(上流にライセンスがない) ので、キャッシュがなければ上流の固定コミットから取得し、
取得できない環境 (オフライン) ではこのファイルのテストを skip する。`pytest tests/test_efo_alignment.py`。
"""
import os

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from src.provenance.validate import EFOUnavailable, check_efo_alignment, ensure_efo_schema, load_efo_local

try:
    ensure_efo_schema()
except EFOUnavailable as _e:
    pytest.skip(f"EFO スキーマを用意できない: {_e}", allow_module_level=True)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTL = os.path.join(REPO, "ontology", "efo-plutchik.ttl")
EMO = Namespace("http://www.ontologydesignpatterns.org/ont/emotions/EmoCore.owl#")

# efo-plutchik が skos:closeMatch で整合させる EFO BasicEmotions 用語 (5.3)。
_CLOSEMATCH_EXPECTED = {"Enjoyment", "Fear", "Surprise", "Sadness", "Disgust", "Anger"}


def test_efo_local_imports_resolve_offline():
    """キャッシュ済みの EFO スキーマ (EmoCore + BasicEmotions) がリモート取得なしでロードできる。"""
    efo = load_efo_local(fetch=False)
    assert len(efo) > 500
    efo = load_efo_local()
    efo = load_efo_local()
    assert len(efo) > 500  # 実 EFO スキーマ (~1000 triples) が手元に再構成される


def test_alignment_check_passes():
    """skos:closeMatch で整合する基本感情用語が全て同梱 EFO に解決する。"""
    assert check_efo_alignment(verbose=False) is True


def test_closematch_targets_defined_in_local_efo():
    """各 skos:closeMatch 対象が同梱 EFO に subject として実在する (件数も明示し空振りを防ぐ)。"""
    plu = Graph()
    plu.parse(TTL, format="turtle")
    efo_subjects = set(load_efo_local().subjects())
    targets = {o for o in plu.objects(None, SKOS.closeMatch) if isinstance(o, URIRef)}
    short = {str(o).split("#")[-1] for o in targets}
    assert short == _CLOSEMATCH_EXPECTED  # 6 件ちょうど (PREFIX 不一致なら 0 件で落ちる)
    for o in targets:
        assert o in efo_subjects, f"{o} が同梱 EFO に未定義 (alignment 切れ)"


def test_emo_emotion_superclass_resolves():
    """plu:PlutchikEmotion の上位 emo:Emotion が EFO core に定義されている。"""
    efo_subjects = set(load_efo_local().subjects())
    assert EMO.Emotion in efo_subjects


def test_corrupted_cache_is_rejected(tmp_path, monkeypatch):
    """キャッシュの中身が固定 hash と違えば使わない (上流の変更・破損の検出)。"""
    import src.provenance.validate as v

    monkeypatch.setattr(v, "EFO_SRC", str(tmp_path))
    for fname in v.EFO_LOCAL_SCHEMA:
        (tmp_path / fname).write_text("# not EFO\n")
    with pytest.raises(EFOUnavailable):
        v.ensure_efo_schema(fetch=False)


def test_missing_cache_without_fetch_raises(tmp_path, monkeypatch):
    """キャッシュがなく fetch=False なら取得せずに EFOUnavailable。"""
    import src.provenance.validate as v

    monkeypatch.setattr(v, "EFO_SRC", str(tmp_path))
    with pytest.raises(EFOUnavailable):
        v.ensure_efo_schema(fetch=False)
