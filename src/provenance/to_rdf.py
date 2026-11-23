"""注入知識の予測寄与を instance-level の PROV-O KG として外部化する (Phase 3, RQ4)。

attribution.GraphKnowledgeAttributor.top_influences の出力 (どの dyad 知識がどの予測に
どれだけ効いたか) を RDF 化する。各予測は emo:EmotionSituation として表現し、
inj:influencedBy (⊂ prov:wasInfluencedBy) で寄与した知識ノードと attribution score に
reified influence ノード経由でリンクする。

さらに各寄与は **どの attribution 手法が生成したか** を PROV-O Activity として明示する:
    inf prov:wasGeneratedBy act
    act a inj:AttributionActivity (⊂ prov:Activity) ;
        prov:wasAssociatedWith <method> ;   # ablation / ablation_mean / grad_input
        prov:used <graph_mode> .            # theory / cooccur / fusion グラフ
    <model> a prov:SoftwareAgent .
これにより「どの寄与が・どの手法で・どの知識グラフから得られたか」が KG 内で追跡でき、
multi_method_attribution_to_graph で複数手法を 1 つの KG に載せると、provenance ランクの
**手法非依存性**を SHACL/CQ で機械検証できる (= 「単一 attribution 手法の産物でない」)。

これが本研究の核「verifiable provenance of knowledge influence」(RELATED_WORK_DIFF) の
生成側であり、validate 系の SHACL shape / SPARQL CQ で形式検証できる queryable な KG を出す。

修論本体の語彙 (plu:isManifestationOf / plu:sourceText / plu:sourceModel) を再利用し、
注入固有の述語のみ inj: 名前空間で新規宣言する (efo-plutchik.ttl は変更しない)。
"""
from __future__ import annotations

import os
from typing import Optional

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

PLU = Namespace("https://w3id.org/efo-plutchik#")
EMO = Namespace("http://www.ontologydesignpatterns.org/ont/emotions/EmoCore.owl#")
PROV = Namespace("http://www.w3.org/ns/prov#")
INJ = Namespace("https://w3id.org/efo-plutchik/injection#")


def _declare_vocab(g: Graph) -> None:
    """生成 KG が自己完結するよう注入 provenance 述語・クラスを宣言する。"""
    g.add((INJ.influencedBy, RDF.type, OWL.ObjectProperty))
    g.add((INJ.influencedBy, RDFS.subPropertyOf, PROV.wasInfluencedBy))
    g.add((INJ.influencedBy, RDFS.label, Literal("influenced by", lang="en")))
    g.add((INJ.knowledgeNode, RDF.type, OWL.ObjectProperty))
    g.add((INJ.knowledgeNode, RDFS.label, Literal("knowledge node", lang="en")))
    g.add((INJ.derivedByMethod, RDF.type, OWL.ObjectProperty))
    g.add((INJ.attributionScore, RDF.type, OWL.DatatypeProperty))
    g.add((INJ.attributionScore, RDFS.range, XSD.float))
    g.add((INJ.Influence, RDF.type, OWL.Class))
    g.add((INJ.AttributionMethod, RDF.type, OWL.Class))
    # PROV-O Activity 層: attribution の計算自体を Activity として型付け。
    g.add((INJ.AttributionActivity, RDF.type, OWL.Class))
    g.add((INJ.AttributionActivity, RDFS.subClassOf, PROV.Activity))


def _bind(g: Graph) -> None:
    for pfx, ns in (("plu", PLU), ("emo", EMO), ("prov", PROV), ("inj", INJ)):
        g.bind(pfx, ns)


def _add_method(g: Graph, method_name: str, injection_mode: str) -> URIRef:
    """attribution 手法を inj:AttributionMethod 個体として宣言する。"""
    method = INJ[method_name]
    g.add((method, RDF.type, OWL.NamedIndividual))
    g.add((method, RDF.type, INJ.AttributionMethod))
    g.add((method, RDFS.label, Literal(f"{method_name} attribution over {injection_mode} graph", lang="en")))
    return method


def _add_graph_entity(g: Graph, injection_mode: str) -> URIRef:
    """attribution 対象の知識グラフ (theory/cooccur/fusion) を prov:Entity として宣言する。"""
    ent = INJ[f"graph_{injection_mode}"]
    g.add((ent, RDF.type, PROV.Entity))
    g.add((ent, RDFS.label, Literal(f"{injection_mode} injection knowledge graph", lang="en")))
    return ent


def _add_records(
    g: Graph,
    records: list[dict],
    model_uri: str,
    method: URIRef,
    method_name: str,
    graph_entity: URIRef,
    top_k: Optional[int],
) -> None:
    """1 手法分の attribution レコード列を既存 Graph に追記する (Activity 層込み)。"""
    model = URIRef(model_uri)
    g.add((model, RDF.type, PROV.SoftwareAgent))
    for r in records:
        occ = INJ[r["pred_id"]]
        g.add((occ, RDF.type, OWL.NamedIndividual))
        g.add((occ, RDF.type, EMO.EmotionSituation))
        g.add((occ, PLU.isManifestationOf, PLU[r["emotion"]]))
        g.add((occ, INJ.derivedByMethod, method))
        g.add((occ, PLU.sourceModel, model))
        if r.get("source_text"):
            g.add((occ, PLU.sourceText, Literal(r["source_text"], datatype=XSD.string)))

        # 予測×手法ごとに 1 つの attribution activity。influence をこの activity に紐付ける。
        act = INJ[f"{r['pred_id']}__{method_name}__act"]
        g.add((act, RDF.type, OWL.NamedIndividual))
        g.add((act, RDF.type, INJ.AttributionActivity))
        g.add((act, PROV.wasAssociatedWith, method))
        g.add((act, PROV.used, graph_entity))

        influences = r["influences"][:top_k] if top_k else r["influences"]
        for node, score in influences:
            inf = BNode()
            g.add((occ, INJ.influencedBy, inf))
            g.add((inf, RDF.type, INJ.Influence))
            g.add((inf, INJ.knowledgeNode, PLU[node]))
            g.add((inf, INJ.attributionScore, Literal(round(float(score), 6), datatype=XSD.float)))
            g.add((inf, PROV.wasGeneratedBy, act))


def attribution_to_graph(
    records: list[dict],
    model_uri: str,
    method_name: str = "NodeAblation",
    injection_mode: str = "theory",
    top_k: Optional[int] = None,
) -> Graph:
    """attribution レコード列 → rdflib Graph (PROV-O KG, 単一手法)。

    Args:
        records: GraphKnowledgeAttributor.top_influences の出力。
        model_uri: 予測を出したモデル (prov:SoftwareAgent / plu:sourceModel)。
        method_name: attribution 手法名 (inj:AttributionMethod 個体名)。
        injection_mode: theory/cooccur/fusion (prov:used する知識グラフ)。
        top_k: 各予測で記録する influence を上位 k 件に制限 (None で全件)。
    """
    g = Graph()
    _bind(g)
    _declare_vocab(g)
    method = _add_method(g, method_name, injection_mode)
    ent = _add_graph_entity(g, injection_mode)
    _add_records(g, records, model_uri, method, method_name, ent, top_k)
    return g


def multi_method_attribution_to_graph(
    records_by_method: dict[str, list[dict]],
    model_uri: str,
    injection_mode: str = "theory",
    top_k: Optional[int] = None,
) -> Graph:
    """複数 attribution 手法の寄与を 1 つの PROV-O KG にまとめる (手法非依存性の検証用)。

    同じ予測 (pred_id) に対し手法ごとの influence/activity を載せるので、CQ で
    「同一予測の top-1 知識ノードが手法間で一致するか」「ある知識ノードが何手法で
    支持されるか」を機械的に問い合わせ・検証できる。

    Args:
        records_by_method: {手法名 -> top_influences レコード列}。各手法は同一の予測集合
            (同じ pred_id/emotion) について算出されている前提。
        model_uri: 予測を出したモデル。
        injection_mode: theory/cooccur/fusion。
        top_k: influence 上限。
    """
    g = Graph()
    _bind(g)
    _declare_vocab(g)
    ent = _add_graph_entity(g, injection_mode)
    for method_name, records in records_by_method.items():
        method = _add_method(g, method_name, injection_mode)
        _add_records(g, records, model_uri, method, method_name, ent, top_k)
    return g


def write_attribution_ttl(records: list[dict], out_path: str, model_uri: str, **kwargs) -> Graph:
    """attribution レコードを Turtle ファイルに書き出す (単一手法)。"""
    g = attribution_to_graph(records, model_uri, **kwargs)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    g.serialize(destination=out_path, format="turtle")
    return g


def write_multi_method_ttl(
    records_by_method: dict[str, list[dict]], out_path: str, model_uri: str, **kwargs
) -> Graph:
    """複数手法の attribution を 1 つの Turtle ファイルに書き出す。"""
    g = multi_method_attribution_to_graph(records_by_method, model_uri, **kwargs)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    g.serialize(destination=out_path, format="turtle")
    return g
