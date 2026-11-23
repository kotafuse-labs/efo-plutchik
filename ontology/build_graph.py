"""
EFO-Plutchik 理論グラフを efo-plutchik.ttl から抽出し、
MoE 注入 (経路1: GCN/GAT) で使う隣接行列・エッジリスト・ノード辞書を生成する。
Phase 1 (CombineEFOMoE)。出力: ontology/plutchik_graph.json

ノード順序は再現研究 src/data/plutchik_labeling.PLUTCHIK_BASE_EMOTIONS と同じ
(基本8感情アルファベット順 → primary dyad 8) に固定し、分類器の出力ラベル順と対応づける。
v0.5.0 でも注入グラフは primary dyad までの 16 ノード（secondary / tertiary dyad・強度の変種は読まない）。
"""
import json
import os

import numpy as np
from rdflib import Graph, Namespace, RDF

PLU = Namespace("https://w3id.org/efo-plutchik#")
BASE_ORDER = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]

HERE = os.path.dirname(os.path.abspath(__file__))
TTL_PATH = os.path.join(HERE, "efo-plutchik.ttl")
OUT_PATH = os.path.join(HERE, "plutchik_graph.json")


def _local(iri):
    return str(iri).split("#")[-1]


def build(ttl_path=TTL_PATH):
    g = Graph()
    g.parse(ttl_path, format="turtle")

    basics = {_local(s).lower(): _local(s) for s in g.subjects(RDF.type, PLU.BasicEmotion)}
    dyads = sorted(_local(s) for s in g.subjects(RDF.type, PLU.PrimaryDyad))
    assert set(basics) == set(BASE_ORDER), f"basic mismatch: {sorted(basics)}"
    assert len(dyads) == 8, f"expected 8 dyads, got {len(dyads)}"

    basic_nodes = [basics[b] for b in BASE_ORDER]
    nodes = basic_nodes + dyads
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)

    comp_edges, opp_edges = [], []
    A = np.zeros((n, n), dtype=int)
    A_comp = np.zeros((n, n), dtype=int)
    A_opp = np.zeros((n, n), dtype=int)

    for s, o in sorted(g.subject_objects(PLU.hasComponentEmotion)):
        a, b = _local(s), _local(o)
        if a not in idx:   # v0.5.0: secondary / tertiary dyad は注入グラフに入れない（16 ノードを維持、CombineEFOMoE #33）
            continue
        comp_edges.append([a, b])
        for M in (A, A_comp):
            M[idx[a], idx[b]] = 1
            M[idx[b], idx[a]] = 1
    for s, o in g.subject_objects(PLU.hasOpposite):
        a, b = _local(s), _local(o)
        opp_edges.append([a, b])
        for M in (A, A_opp):
            M[idx[a], idx[b]] = 1
            M[idx[b], idx[a]] = 1

    return {
        "nodes": nodes,
        "node_types": {**{b: "basic" for b in basic_nodes}, **{d: "dyad" for d in dyads}},
        "basic_emotions": basic_nodes,
        "basic_order_lower": BASE_ORDER,
        "primary_dyads": dyads,
        "edges": {"hasComponentEmotion": comp_edges, "hasOpposite": opp_edges},
        "adjacency": A.tolist(),
        "adjacency_component": A_comp.tolist(),
        "adjacency_opposite": A_opp.tolist(),
    }


def main():
    data = build()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"nodes ({len(data['nodes'])}): {data['nodes']}")
    print(f"  basic ({len(data['basic_emotions'])}): {data['basic_emotions']}")
    print(f"  dyads ({len(data['primary_dyads'])}): {data['primary_dyads']}")
    print(f"hasComponentEmotion edges: {len(data['edges']['hasComponentEmotion'])} (expect 16)")
    print(f"hasOpposite edges:        {len(data['edges']['hasOpposite'])} (expect 4)")
    print(f"adjacency: {len(data['adjacency'])}x{len(data['adjacency'][0])}")
    print(f"written -> {OUT_PATH}")


if __name__ == "__main__":
    main()
