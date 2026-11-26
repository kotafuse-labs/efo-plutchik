"""転移の証拠のモジュール 0.1.1 を生成する（CombineEFOMoE #88 → #90）。

入力: ontology/evidence/crossdata_transfer_2026-11.csv（CombineEFOMoE #88 の結果。数値だけで、データセットの文は含まない。AUC は小数 6 桁）と、
      同じ場所の .source.json（もとの json とスクリプトの sha256。CombineEFOMoE の scripts/export_transfer_evidence_csv.py が両方を書く）。
出力: ontology/plutchik-mapping-evidence.ttl（生成物。手で編集しない）。

写像の記録（map:ConceptMapping、方式 map:Plutchik2001Names）は変えない。ここでは、同じ Plutchik の語に対応する 2 つの記録の組ごとに、
「片方のデータセットで学習した分類器が、もう片方のラベルをどれだけ見分けたか」を証拠として足す。
証拠は対応の正しさの判定ではない（移らないことは、意味が違うことを示さない。docs/MODELING_DECISIONS.md G 節）。

  python ontology/build_transfer_evidence.py            # 生成
"""
import csv
import json
import os
from decimal import Decimal

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS, XSD

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "evidence", "crossdata_transfer_2026-11.csv")
OUT = os.path.join(HERE, "plutchik-mapping-evidence.ttl")
PLU = Namespace("https://w3id.org/efo-plutchik#")
MAP = Namespace("https://w3id.org/efo-plutchik/mapping#")
EVD = Namespace("https://w3id.org/efo-plutchik/mapping/evidence#")
ONTO = URIRef("https://w3id.org/efo-plutchik/mapping/evidence")
VERSION = "0.1.1"
SOURCE = os.path.join(HERE, "evidence", "crossdata_transfer_2026-11.source.json")
VERDICTS = {"supported": "Supported", "partial": "Partial", "not_supported": "NotSupported"}

CLASSES = {
    "EvidenceStudy": ("Evidence study", "証拠の調査", "An experiment that produced transfer evidence, with its setting and known limitations."),
    "TransferEvidence": ("Transfer evidence", "転移の証拠", "For two mapping records that map labels of two different datasets to the same Plutchik term: how well a classifier trained on the source dataset's label separates the target dataset's label. It is evidence about one experimental setting, not a judgement that the mapping is right or wrong."),
    "Verdict": ("Pre-registered verdict", "事前登録の判定", "The per-pair verdict defined in the study's pre-registration."),
}
PROPS = {  # 名前: (label, 型, range, 定義)
    "fromStudy": ("from study", "object", EVD.EvidenceStudy, "The study that produced the evidence."),
    "sourceMapping": ("source mapping", "object", MAP.ConceptMapping, "The mapping record of the label the classifier was trained on."),
    "targetMapping": ("target mapping", "object", MAP.ConceptMapping, "The mapping record of the label the classifier was evaluated against."),
    "matchedAuc": ("matched AUC", "data", XSD.decimal, "ROC-AUC of the source label's score against the target label's gold labels, averaged over seeds and rounded to 6 decimals."),
    "bestOtherAuc": ("best other AUC", "data", XSD.decimal, "In each seed, the highest ROC-AUC among the source model's other labels (all labels except the name-matched one); these per-seed maxima are averaged, so the best label may differ between seeds. It is chosen after the fact, so it is an upper reference, not a usable predictor."),
    "rankOneSeeds": ("rank-one seeds", "data", XSD.integer, "Number of seeds in which the name-matched label had the highest AUC among the source model's labels."),
    "rankThreeSeeds": ("rank-three seeds", "data", XSD.integer, "Number of seeds in which the name-matched label was among the three highest."),
    "seedCount": ("seed count", "data", XSD.integer, "Number of seeds."),
    "sourceLabelCount": ("source label count", "data", XSD.integer, "Number of labels of the source model. With few labels, rank three is easy to reach by chance."),
    "targetPositives": ("target positives", "data", XSD.integer, "Number of positive rows of the target label among the evaluation rows."),
    "targetRows": ("target rows", "data", XSD.integer, "Number of evaluation rows."),
    "nativeAuc": ("native AUC", "data", XSD.decimal, "ROC-AUC of the target dataset's own model for the target label on its test split, averaged over seeds."),
    "nativePositives": ("native positives", "data", XSD.integer, "Number of positive rows of the target label in the target dataset's test split. Below 20 the native AUC is unstable."),
    "preregisteredVerdict": ("pre-registered verdict", "object", EVD.Verdict, "Defined for five seeds. Supported: rank one in at least 4 of 5 seeds. Partial: within rank three in at least 4 of 5 seeds. NotSupported: otherwise. The rule has no absolute floor on the AUC."),
}
STUDY_LIMITS = (
    "One model (roberta-base), one training setting (at most 8,000 training rows, no model selection on validation data), five seeds, English only.",
    "Transfer does not show that two labels denote the same concept, and a lack of transfer does not show that they differ: granularity, label frequency, text type and the number of training positives also change the result.",
    "Datasets with many closely related labels (for example 28 or 32) lose rank to those neighbours; this is an effect of granularity.",
    "Rare labels had about 20 training positives or fewer after sampling (for example GoEmotions 'pride', DailyDialog 'fear'); pairs with these as the source are inconclusive.",
    "The verdict rule has no absolute floor: some pairs with a matched AUC below 0.6 are Partial. Compare matchedAuc with bestOtherAuc instead of relying on the verdict alone.",
    "Within rank three is easy to reach by chance when the source model has few labels (probability 0.60 with 5 labels); see sourceLabelCount.",
    "The highest values are for pairs in which both datasets were labelled by the writer; all of these datasets consist of event descriptions, so labelling method and text type cannot be separated.",
    "The evaluation rows are fixed; the seeds vary only the initialisation and data order of training, so agreement across seeds does not measure uncertainty across datasets or labels.",
    "In some target datasets the label word itself occurs in the positive texts (about 20% in GoEmotions, 7% in EmpatheticDialogues), which favours name-matched transfer; removing those rows changed the overall rates by less than 0.02.",
    "The numbers are aggregate statistics computed from the datasets; no dataset text is included. The datasets themselves remain under their own licences.",
)


def mapping_records(mappings: Graph) -> dict:
    """{(dataset, label): 記録の IRI}（方式 Plutchik2001Names、closeMatch だけ）。"""
    out = {}
    for r in mappings.subjects(MAP.inScheme, MAP.Plutchik2001Names):
        if mappings.value(r, MAP.matchType) == SKOS.closeMatch:
            out[(str(mappings.value(r, MAP.dataset)), str(mappings.value(r, MAP.sourceLabel)))] = r
    return out


def build(csv_path=CSV, mappings_path=os.path.join(HERE, "plutchik-mappings.ttl")) -> Graph:
    mappings = Graph().parse(mappings_path, format="turtle")
    rec = mapping_records(mappings)
    g = Graph()
    for pfx, ns in (("evd", EVD), ("map", MAP), ("plu", PLU), ("skos", SKOS), ("dcterms", DCTERMS), ("owl", OWL)):
        g.bind(pfx, ns)
    en = lambda s: Literal(s, lang="en")
    g.add((ONTO, RDF.type, OWL.Ontology)); g.add((ONTO, OWL.versionInfo, Literal(VERSION)))
    g.add((ONTO, OWL.imports, URIRef("https://w3id.org/efo-plutchik/mapping")))
    g.add((ONTO, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    g.add((ONTO, RDFS.label, en("EFO-Plutchik mapping evidence"))); g.add((ONTO, RDFS.label, Literal("EFO-Plutchik の写像の証拠", lang="ja")))
    g.add((ONTO, RDFS.comment, en("Generated by ontology/build_transfer_evidence.py; edit the script or the CSV, not this file.")))
    g.add((ONTO, RDFS.comment, en(f"Evidence module {VERSION}. It adds cross-dataset transfer evidence for pairs of mapping records of the mapping module, which is unchanged.")))
    for name, (lab, ja, definition) in CLASSES.items():
        g.add((EVD[name], RDF.type, OWL.Class)); g.add((EVD[name], RDFS.label, en(lab))); g.add((EVD[name], RDFS.label, Literal(ja, lang="ja"))); g.add((EVD[name], SKOS.definition, en(definition)))
    for name, (lab, kind, rng, definition) in PROPS.items():
        g.add((EVD[name], RDF.type, OWL.ObjectProperty if kind == "object" else OWL.DatatypeProperty))
        g.add((EVD[name], RDFS.label, en(lab))); g.add((EVD[name], SKOS.definition, en(definition))); g.add((EVD[name], RDFS.range, rng))
        g.add((EVD[name], RDFS.domain, EVD.TransferEvidence))
    for v in VERDICTS.values():
        g.add((EVD[v], RDF.type, EVD.Verdict)); g.add((EVD[v], RDFS.label, en(v)))
    study = EVD.CrossDatasetTransfer2026
    g.add((study, RDF.type, EVD.EvidenceStudy)); g.add((study, RDFS.label, en("Cross-dataset transfer of name-matched labels (2026-11)")))
    g.add((study, DCTERMS.date, Literal("2026-11-27", datatype=XSD.date)))
    g.add((study, DCTERMS.source, en("CombineEFOMoE issue #88 (pre-registered); mapping module 0.6.1")))
    g.add((study, DCTERMS.description, en("For each of 10 English emotion datasets a multi-label roberta-base classifier was trained on the dataset's own labels (learning rate 2e-5, at most 8,000 training rows, seeds 42-46) and applied to up to 5,000 fixed rows of every other dataset. A pair is included when both labels map to the same Plutchik term and the target label has at least 20 positive and 20 negative rows.")))
    with open(SOURCE, encoding="utf-8") as f:
        src = json.load(f)
    for name, digest in sorted({**src["inputs"], **src["scripts"]}.items()):
        g.add((study, DCTERMS.source, en(f"sha256 {digest} {name}")))
    for lim in STUDY_LIMITS:
        g.add((study, SKOS.scopeNote, en(lim)))
    dec = lambda x: Literal(Decimal(x), datatype=XSD.decimal)
    integer = lambda x: Literal(int(x), datatype=XSD.integer)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s, t = rec[(row["source_dataset"], row["source_label"])], rec[(row["target_dataset"], row["target_label"])]
            assert str(mappings.value(s, MAP.mapsTo)).endswith("#" + row["term"]) and mappings.value(s, MAP.mapsTo) == mappings.value(t, MAP.mapsTo), row
            e = EVD["t2026_" + str(s).split("#pn_")[-1] + "__" + str(t).split("#pn_")[-1]]
            g.add((e, RDF.type, EVD.TransferEvidence)); g.add((e, EVD.fromStudy, study)); g.add((e, EVD.sourceMapping, s)); g.add((e, EVD.targetMapping, t))
            for prop, col in (("matchedAuc", "matched_auc"), ("bestOtherAuc", "best_other_auc"), ("nativeAuc", "native_auc")):
                g.add((e, EVD[prop], dec(row[col])))
            for prop, col in (("rankOneSeeds", "rank1_seeds"), ("rankThreeSeeds", "rank3_seeds"), ("seedCount", "n_seeds"), ("sourceLabelCount", "n_source_labels"),
                              ("targetPositives", "target_positives"), ("targetRows", "target_rows"), ("nativePositives", "native_positives")):
                g.add((e, EVD[prop], integer(row[col])))
            g.add((e, EVD.preregisteredVerdict, EVD[VERDICTS[row["preregistered_verdict"]]]))
    return g


if __name__ == "__main__":
    graph = build()
    graph.serialize(OUT, format="turtle")
    print(f"[evidence] {len(list(graph.subjects(RDF.type, EVD.TransferEvidence)))} 件 → {OUT}")
