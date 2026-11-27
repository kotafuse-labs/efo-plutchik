"""転移の証拠のモジュール 0.2.2 を生成する（CombineEFOMoE #88 → #90、#91 → #92）。

調査は 2 つ。CrossDatasetTransfer2026（#88）と、その再実行 CrossDatasetTransfer2026b（#91。新しい seed、まれなラベルの陽性を学習に残す、判定の規則を直す）。

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
VERSION = "0.2.2"
SOURCE = os.path.join(HERE, "evidence", "crossdata_transfer_2026-11.source.json")
CSV_B = os.path.join(HERE, "evidence", "crossdata_transfer_2026-11b.csv")
SOURCE_B = os.path.join(HERE, "evidence", "crossdata_transfer_2026-11b.source.json")
VERDICTS = {"supported": "Supported", "partial": "Partial", "not_supported": "NotSupported", "mixed": "Mixed", "inconclusive": "Inconclusive"}

CLASSES = {
    "EvidenceStudy": ("Evidence study", "証拠の調査", "An experiment that produced transfer evidence, with its setting and known limitations."),
    "TransferEvidence": ("Transfer evidence", "転移の証拠", "For two mapping records that map labels of two different datasets to the same Plutchik term: how well a classifier trained on the source dataset's label separates the target dataset's label. It is evidence about one experimental setting, not a judgement that the mapping is right or wrong."),
    "Verdict": ("Pre-registered verdict", "事前登録の判定", "The per-pair verdict defined in the study's pre-registration. The rule differs between studies; see evd:preregisteredVerdict and the study's description."),
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
    "sourceTrainingPositives": ("source training positives", "data", XSD.integer, "Number of positive training rows of the source label (the minimum over seeds). Recorded from study CrossDatasetTransfer2026b on; the first study did not record it."),
    "preregisteredVerdict": ("pre-registered verdict", "object", EVD.Verdict, "Study CrossDatasetTransfer2026b: Inconclusive if the source label had fewer than 50 training positives; otherwise Supported if rank one in at least 4 of 5 seeds and the matched AUC is at least 0.6; otherwise NotSupported if the matched AUC does not exceed the best other AUC; otherwise Mixed. Study CrossDatasetTransfer2026: defined for five seeds. Supported: rank one in at least 4 of 5 seeds. Partial: within rank three in at least 4 of 5 seeds. NotSupported: otherwise. The rule has no absolute floor on the AUC."),
}
STUDY_LIMITS = (
    "One model (roberta-base), one training setting (at most 8,000 training rows, no model selection on validation data), five seeds, English only.",
    "Transfer does not show that two labels denote the same concept, and a lack of transfer does not show that they differ: granularity, label frequency, text type and the number of training positives also change the result.",
    "Datasets with many closely related labels (for example 28 or 32) lose rank to those neighbours; this is an effect of granularity.",
    "Rare labels had about 20 training positives or fewer after sampling (for example GoEmotions 'pride', DailyDialog 'fear'); for pairs with these as the source this study cannot tell whether the label fails to transfer or the training sample was too small (their verdicts remain NotSupported or Partial as pre-registered).",
    "The verdict rule has no absolute floor: some pairs with a matched AUC below 0.6 are Partial. Compare matchedAuc with bestOtherAuc instead of relying on the verdict alone.",
    "Within rank three is easy to reach by chance when the source model has few labels (probability 0.60 with 5 labels); see sourceLabelCount.",
    "The highest values are for pairs in which both datasets were labelled by the writer; all of these datasets consist of event descriptions, so labelling method and text type cannot be separated.",
    "The evaluation rows are fixed; the seeds vary only the initialisation and data order of training, so agreement across seeds does not measure uncertainty across datasets or labels.",
    "In some target datasets the label word itself occurs in the positive texts (about 20% in GoEmotions, 7% in EmpatheticDialogues), which favours name-matched transfer; removing those rows changed the overall rates by less than 0.02.",
    "The numbers are aggregate statistics computed from the datasets; no dataset text is included. The datasets themselves remain under their own licences.",
    "To be read together with the re-run CrossDatasetTransfer2026b, which kept the positives of rare labels in the training sample (DailyDialog 'fear': 124 instead of 11-16; GoEmotions 'pride': 111 instead of 16-24). With DailyDialog 'fear' as the source, all 8 pairs were then Supported (name-matched label ranked first in at least 4 of 5 seeds); with GoEmotions 'pride' as the source, 2 of 3 pairs were, by a small margin. For these two sources the NotSupported and Partial verdicts of this study most likely reflect too few training positives; the design cannot separate this from the change of seeds.",
)
STUDY_B_LIMITS = (
    "A re-run of CrossDatasetTransfer2026 on the same 10 datasets with the same model and mapping; it is not an independent replication. Six source datasets use the same training rows as the first study, three target datasets the same evaluation rows, and 17% of the pairs differ only in the seeds.",
    "One model (roberta-base), one training setting, five seeds (47-51), English only.",
    "Transfer does not show that two labels denote the same concept, and a lack of transfer does not show that they differ.",
    "For terms that are not basic emotions, the best other label shares an underlying basic emotion with the term in 62% of the seed-wise comparisons (for example guilt and shame, pride and joy); against unrelated labels the name-matched label is ahead on average.",
    "Results depend strongly on the source dataset. For terms that are not basic emotions, the 18 pairs whose source is GoEmotions or GoodNewsEveryone taken together have the name-matched label behind the best other label on average (-0.031), while the other 28 pairs have it ahead (+0.045). For basic emotions the mean difference by source dataset ranges from -0.001 (GoEmotions) to +0.227 (BRIGHTER).",
    "Rare labels enter the training sample with all their positives in every seed, and the label distribution of the sample differs from the natural one.",
    "The thresholds of the verdict rule (50 training positives, AUC 0.6, 4 of 5 seeds) were chosen by the authors. One source label has 53 training positives, just above the threshold.",
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
    for v in VERDICTS.values():  # noqa
        g.add((EVD[v], RDF.type, EVD.Verdict)); g.add((EVD[v], RDFS.label, en(v)))
    dec = lambda x: Literal(Decimal(x), datatype=XSD.decimal)
    integer = lambda x: Literal(int(x), datatype=XSD.integer)

    def add_study(study, label, source_text, description, limits, source_path, csv_file, prefix, columns):
        g.add((study, RDF.type, EVD.EvidenceStudy)); g.add((study, RDFS.label, en(label)))
        g.add((study, DCTERMS.date, Literal("2026-11-27", datatype=XSD.date)))
        g.add((study, DCTERMS.source, en(source_text)))
        g.add((study, DCTERMS.description, en(description)))
        with open(source_path, encoding="utf-8") as f:
            src = json.load(f)
        for name, digest in sorted({**src["inputs"], **src["scripts"]}.items()):
            g.add((study, DCTERMS.source, en(f"sha256 {digest} {name}")))
        for lim in limits:
            g.add((study, SKOS.scopeNote, en(lim)))
        with open(csv_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                s, t = rec[(row["source_dataset"], row["source_label"])], rec[(row["target_dataset"], row["target_label"])]
                assert str(mappings.value(s, MAP.mapsTo)).endswith("#" + row["term"]) and mappings.value(s, MAP.mapsTo) == mappings.value(t, MAP.mapsTo), row
                e = EVD[prefix + str(s).split("#pn_")[-1] + "__" + str(t).split("#pn_")[-1]]
                g.add((e, RDF.type, EVD.TransferEvidence)); g.add((e, EVD.fromStudy, study)); g.add((e, EVD.sourceMapping, s)); g.add((e, EVD.targetMapping, t))
                for prop, col in (("matchedAuc", "matched_auc"), ("bestOtherAuc", "best_other_auc"), ("nativeAuc", "native_auc")):
                    g.add((e, EVD[prop], dec(row[col])))
                for prop, col in columns:
                    g.add((e, EVD[prop], integer(row[col])))
                g.add((e, EVD.preregisteredVerdict, EVD[VERDICTS[row["preregistered_verdict" if "preregistered_verdict" in row else "verdict"]]]))

    common = (("rankOneSeeds", "rank1_seeds"), ("seedCount", "n_seeds"), ("sourceLabelCount", "n_source_labels"), ("targetPositives", "target_positives"), ("nativePositives", "native_positives"))
    add_study(EVD.CrossDatasetTransfer2026, "Cross-dataset transfer of name-matched labels (2026-11)", "CombineEFOMoE issue #88 (pre-registered); mapping module 0.6.1",
              "For each of 10 English emotion datasets a multi-label roberta-base classifier was trained on the dataset's own labels (learning rate 2e-5, at most 8,000 training rows, seeds 42-46) and applied to up to 5,000 fixed rows of every other dataset. A pair is included when both labels map to the same Plutchik term and the target label has at least 20 positive and 20 negative rows.",
              STUDY_LIMITS, SOURCE, csv_path, "t2026_", common + (("rankThreeSeeds", "rank3_seeds"), ("targetRows", "target_rows")))
    add_study(EVD.CrossDatasetTransfer2026b, "Cross-dataset transfer of name-matched labels, re-run with rare labels kept (2026-11b)", "CombineEFOMoE issue #91 (pre-registered); mapping module 0.6.1",
              "A re-run of CrossDatasetTransfer2026 with seeds 47-51, evaluation rows re-drawn with a new seed (identical for the three target datasets that have at most 5,000 rows; the number of evaluation rows is not recorded per pair), and a training sample that first takes up to 200 positives of every label and then fills up to 8,000 rows at random. The pre-registered measure is the matched AUC minus the best other AUC; the verdict rule is given at evd:preregisteredVerdict.",
              STUDY_B_LIMITS, SOURCE_B, CSV_B, "t2026b_", common + (("sourceTrainingPositives", "source_training_positives"),))
    g.add((EVD.CrossDatasetTransfer2026b, DCTERMS.relation, EVD.CrossDatasetTransfer2026))
    return g


if __name__ == "__main__":
    graph = build()
    graph.serialize(OUT, format="turtle")
    print(f"[evidence] {len(list(graph.subjects(RDF.type, EVD.TransferEvidence)))} 件 → {OUT}")
