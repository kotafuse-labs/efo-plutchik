"""NRC VAD Lexicon から Plutchik の感情語の VAD（valence / arousal / dominance）を引き、別ファイルの TTL を作る（v0.5.0）。

NRC VAD の利用条件は研究・非商用で、本パッケージの CC BY 4.0 と合わないため、辞書も生成物も同梱しない
（出力 ontology/plutchik-vad.ttl は .gitignore 済み。CombineEFOMoE Issue #33）。
辞書は利用者が NRC の配布元（https://saifmohammad.com/WebPages/nrc-vad.html）から取得して --lexicon に渡す。

対象: コアの基本感情 8・強度の変種 16・dyad 24 の英語ラベル（すべて 1 語）を小文字で引く。見つからない語は報告し、読み取り値を作らない。
辞書の形式: 1 行目がヘッダ、以後「語<TAB>valence<TAB>arousal<TAB>dominance」（v1 2018 の 0〜1、v2 2025 の −1〜1 のどちらも、
値は辞書の尺度のまま記録し、尺度は --scale で記録する）。

使い方:
  python ontology/build_vad.py --lexicon /path/to/NRC-VAD-Lexicon.txt --version "NRC VAD v2.1 (2025)" --scale "-1..1"
"""
import argparse
import os
from decimal import Decimal

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, PROV, XSD

PLU = Namespace("https://w3id.org/efo-plutchik#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "plutchik-vad.ttl")
NRC_VAD = URIRef("https://saifmohammad.com/WebPages/nrc-vad.html")
TARGET_CLASSES = (PLU.BasicEmotion, PLU.IntensityVariant, PLU.PrimaryDyad, PLU.SecondaryDyad, PLU.TertiaryDyad)


def read_lexicon(path: str) -> dict:
    table = {}
    with open(path, encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            table[parts[0].strip().lower()] = tuple(Decimal(x) for x in parts[1:4])
    return table


def build(lexicon: dict, version: str, scale: str, core_path=os.path.join(HERE, "efo-plutchik.ttl")):
    core = Graph(); core.parse(core_path)
    g = Graph()
    g.bind("plu", PLU); g.bind("prov", PROV); g.bind("dcterms", DCTERMS)
    src = URIRef(f"{NRC_VAD}#{version.replace(' ', '_')}")
    g.add((src, RDF.type, PROV.Entity))
    g.add((src, RDFS.label, Literal(version)))
    g.add((src, DCTERMS.source, NRC_VAD))
    g.add((src, RDFS.comment, Literal(f"Score scale: {scale}. Research / non-commercial use only (NRC terms of use).")))
    missing = []
    for cls in TARGET_CLASSES:
        for e in sorted(core.subjects(RDF.type, cls)):
            word = next(str(l).lower() for l in core.objects(e, RDFS.label) if l.language == "en")
            if word not in lexicon:
                missing.append(word)
                continue
            v, a, d = lexicon[word]
            r = PLU[f"VAD_{str(e).split('#')[1]}"]
            g.add((e, PLU.hasVADReading, r))
            g.add((r, RDF.type, PLU.VADReading))
            g.add((r, PLU.lexiconTerm, Literal(word)))
            g.add((r, PLU.vadValence, Literal(v, datatype=XSD.decimal)))
            g.add((r, PLU.vadArousal, Literal(a, datatype=XSD.decimal)))
            g.add((r, PLU.vadDominance, Literal(d, datatype=XSD.decimal)))
            g.add((r, PROV.wasDerivedFrom, src))
    return g, sorted(missing)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lexicon", required=True, help="NRC VAD Lexicon のテキストファイル（タブ区切り、ヘッダ 1 行）")
    ap.add_argument("--version", required=True, help='辞書の版（例: "NRC VAD v2.1 (2025)"）')
    ap.add_argument("--scale", required=True, help='値の尺度（例: "0..1" / "-1..1"）')
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    g, missing = build(read_lexicon(a.lexicon), a.version, a.scale)
    header = ("# 生成物（同梱しない）: NRC VAD Lexicon から引いた Plutchik の感情語の VAD。研究・非商用に限る。\n"
              f"# ontology/build_vad.py --version {a.version!r} --scale {a.scale!r}\n")
    open(a.out, "w", encoding="utf-8").write(header + g.serialize(format="turtle"))
    n = len(set(g.subjects(RDF.type, PLU.VADReading)))
    print(f"wrote {a.out}: {n} readings; not in lexicon ({len(missing)}): {', '.join(missing) or '-'}")


if __name__ == "__main__":
    main()
