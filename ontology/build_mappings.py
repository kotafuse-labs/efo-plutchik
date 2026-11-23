"""データセットのラベル → EFO-Plutchik の写像（v0.5.0）を生成する。出力: ontology/plutchik-mappings.ttl

2 つの写像方式を並べて持つ（CombineEFOMoE Issue #33）。
- map:LimCheong2024（再現用）: Lim & Cheong (EMNLP 2024) Table 1 / 2。ラベルを 1〜2 個の基本感情の成分に写す。
  既知の問題（対極の合成・dyad 名の不一致）は mapping_audit_shapes.ttl で監査する（CombineEFOMoE #22）。
- map:Plutchik2001Names（v0.5.0 で新設）: ラベルを 1 つの Plutchik の感情（基本感情・強度の変種・dyad）に写す。
  根拠のあるものだけを写し、写さないラベルは理由つきで記録する。規則（優先順）:
    1. ラベル名が Plutchik (2001) の語（基本感情 8・強度の変種 16・dyad 24）と一致 → skos:closeMatch
       （名前が同じでも、データセット側の定義が Plutchik の概念と同一だとは確認していないため exactMatch にはしない）。
    2. 1 に当たらない GoEmotions のラベルは、Demszky et al. (2020) が公開する Ekman 6 感情への対応
       （google-research/goemotions/data/ekman_mapping.json、2026-11-14 取得）で、その Ekman 感情に対応する
       Plutchik の基本感情へ skos:broadMatch（Ekman の感情と Plutchik の基本感情の対応はコアの skos:closeMatch be:*）。
    3. どちらにも当たらないラベル（neutral）は写さない（map:UnmappedLabel、理由つき）。
  skos:exactMatch は使わない（上の理由）。1 と 2 が食い違うラベル（disapproval: 名前は Plutchik の dyad、
  Demszky は anger）は 1 を優先し、basis に食い違いを書く。
"""
import os

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS, XSD

PLU = Namespace("https://w3id.org/efo-plutchik#")
MAP = Namespace("https://w3id.org/efo-plutchik/mapping#")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "plutchik-mappings.ttl")

SEMEVAL = ["anger", "anticipation", "disgust", "fear", "joy", "love", "optimism", "pessimism", "sadness", "surprise", "trust"]
GOEMOTIONS = ["admiration", "amusement", "anger", "annoyance", "approval", "caring", "confusion", "curiosity", "desire",
              "disappointment", "disapproval", "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief", "joy",
              "love", "nervousness", "optimism", "pride", "realization", "relief", "remorse", "sadness", "surprise", "neutral"]

# Lim & Cheong (EMNLP 2024) Table 1 / 2（CombineEFOMoE ontology/label_mappings.ttl から移植。空 = 写さない）
LIM_CHEONG = {
    "semeval2018": {"anger": ["Anger"], "anticipation": ["Anticipation"], "disgust": ["Disgust"], "fear": ["Fear"],
                    "joy": ["Joy"], "love": ["Joy", "Trust"], "optimism": ["Anticipation", "Joy"],
                    "pessimism": ["Anticipation", "Sadness"], "sadness": ["Sadness"], "surprise": ["Surprise"],
                    "trust": ["Trust"]},
    "goemotions": {"admiration": ["Trust"], "amusement": [], "anger": ["Anger"], "annoyance": ["Anger"], "approval": [],
                   "caring": [], "confusion": ["Anticipation", "Surprise"], "curiosity": ["Surprise", "Trust"],
                   "desire": [], "disappointment": ["Sadness", "Surprise"], "disapproval": ["Sadness", "Surprise"],
                   "disgust": ["Disgust"], "embarrassment": [], "excitement": ["Fear", "Joy"], "fear": ["Fear"],
                   "gratitude": [], "grief": ["Sadness"], "joy": ["Joy"], "love": ["Joy", "Trust"], "nervousness": [],
                   "neutral": [], "optimism": ["Anticipation", "Joy"], "pride": ["Anger", "Joy"], "realization": [],
                   "relief": [], "remorse": ["Disgust", "Sadness"], "sadness": ["Sadness"], "surprise": ["Surprise"]},
}

# Demszky et al. (2020) の Ekman 対応（ekman_mapping.json をそのまま転記）
DEMSZKY_EKMAN = {
    "anger": ["anger", "annoyance", "disapproval"],
    "disgust": ["disgust"],
    "fear": ["fear", "nervousness"],
    "joy": ["joy", "amusement", "approval", "excitement", "gratitude", "love", "optimism", "relief", "pride",
            "admiration", "desire", "caring"],
    "sadness": ["sadness", "disappointment", "embarrassment", "grief", "remorse"],
    "surprise": ["surprise", "realization", "confusion", "curiosity"],
}
EKMAN_TO_PLUTCHIK = {"anger": "Anger", "disgust": "Disgust", "fear": "Fear", "joy": "Joy", "sadness": "Sadness",
                     "surprise": "Surprise"}

CITE_LC = ("Lim, D. and Cheong, Y.-G. (2024). Integrating Plutchik's Theory with Mixture of Experts for Enhancing Emotion "
           "Classification. EMNLP 2024, 857-867; Table 1 (SemEval-2018) and Table 2 (GoEmotions).")
CITE_PLUTCHIK = "Plutchik, R. (2001). The Nature of Emotions. American Scientist 89(4), 344-350."
CITE_DEMSZKY = ("Demszky, D. et al. (2020). GoEmotions: A Dataset of Fine-Grained Emotions. ACL 2020, 4040-4054; "
                "Ekman grouping from google-research/goemotions/data/ekman_mapping.json (retrieved 2026-11-14).")
DATASET_LABEL = {"semeval2018": ("SemEval-2018 Task 1 E-c", "SemEval-2018 Task 1 E-c のラベル"),
                 "goemotions": ("GoEmotions", "GoEmotions のラベル")}


def plutchik_terms(core: Graph) -> dict:
    """コアの基本感情・強度の変種・dyad の英語ラベル（小文字）→ IRI。"""
    terms = {}
    for cls in (PLU.BasicEmotion, PLU.IntensityVariant, PLU.PrimaryDyad, PLU.SecondaryDyad, PLU.TertiaryDyad):
        for s in core.subjects(RDF.type, cls):
            for lab in core.objects(s, RDFS.label):
                if lab.language == "en":
                    terms[str(lab).lower()] = s
    return terms


def underlying_basics(core: Graph, e) -> set:
    """感情の土台の基本感情: 基本感情は自身、強度の変種は intensityOf、dyad は 2 成分。"""
    if (e, RDF.type, PLU.BasicEmotion) in core:
        return {e}
    return set(core.objects(e, PLU.intensityOf)) | set(core.objects(e, PLU.hasComponentEmotion))


def curated(dataset: str, label: str, terms: dict, core: Graph):
    """Plutchik2001Names 方式の写像: (target, matchType, basis) または (None, None, reason)。"""
    if label in terms:
        basis = f"Label name identical to the Plutchik (2001) term '{label}'."
        if dataset == "goemotions":
            ek = [e for e, ls in DEMSZKY_EKMAN.items() if label in ls]
            if ek and PLU[EKMAN_TO_PLUTCHIK[ek[0]]] not in underlying_basics(core, terms[label]):
                basis += (f" Demszky et al. (2020) group it under Ekman '{ek[0]}', which is not among its Plutchik "
                          f"components; the name match takes precedence.")
        return terms[label], SKOS.closeMatch, basis
    if dataset == "goemotions":
        ek = [e for e, ls in DEMSZKY_EKMAN.items() if label in ls]
        if ek:
            return (PLU[EKMAN_TO_PLUTCHIK[ek[0]]], SKOS.broadMatch,
                    f"No Plutchik (2001) term of this name; Demszky et al. (2020) group it under Ekman '{ek[0]}', "
                    f"which corresponds to the Plutchik basic emotion {EKMAN_TO_PLUTCHIK[ek[0]]}.")
    return None, None, "Not an emotion category (no Plutchik term and no Ekman grouping)." if label == "neutral" \
        else "No Plutchik (2001) term and no literature-backed grouping."


def build(core_path=os.path.join(HERE, "efo-plutchik.ttl")) -> Graph:
    core = Graph(); core.parse(core_path)
    terms = plutchik_terms(core)
    g = Graph()
    for p, ns in (("plu", PLU), ("map", MAP), ("skos", SKOS), ("dcterms", DCTERMS), ("owl", OWL)):
        g.bind(p, ns)
    onto = URIRef("https://w3id.org/efo-plutchik/mapping")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal("EFO-Plutchik dataset label mappings", lang="en")))
    g.add((onto, RDFS.label, Literal("EFO-Plutchik のデータセットラベル写像", lang="ja")))
    g.add((onto, OWL.versionInfo, Literal("0.5.0")))
    g.add((onto, OWL.imports, URIRef("https://w3id.org/efo-plutchik/0.5.0")))
    g.add((onto, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    g.add((onto, RDFS.comment, Literal("Generated by ontology/build_mappings.py; edit the script, not this file.", lang="en")))

    def term(s, typ, en, ja, den, dja):
        g.add((s, RDF.type, typ))
        g.add((s, RDFS.label, Literal(en, lang="en"))); g.add((s, RDFS.label, Literal(ja, lang="ja")))
        g.add((s, SKOS.definition, Literal(den, lang="en"))); g.add((s, SKOS.definition, Literal(dja, lang="ja")))

    # TBox（小さな語彙）
    term(MAP.LabelMapping, OWL.Class, "Label Mapping", "ラベル写像",
         "A reified mapping from one dataset label to Plutchik emotions under a mapping scheme.",
         "ある写像方式のもとで、データセットのラベル 1 つを Plutchik の感情へ写すことを表す個体。")
    term(MAP.ComponentMapping, OWL.Class, "Component Mapping", "成分写像",
         "A label mapping that maps a label to one or two Plutchik basic emotions as its components.",
         "ラベルを 1〜2 個の基本感情の成分に写すラベル写像。")
    term(MAP.ConceptMapping, OWL.Class, "Concept Mapping", "概念写像",
         "A label mapping that maps a label to exactly one Plutchik emotion with a SKOS match type.",
         "ラベルを SKOS の対応の種類つきで Plutchik の感情 1 つに写すラベル写像。")
    term(MAP.UnmappedLabel, OWL.Class, "Unmapped Label", "写さないラベル",
         "A record that a dataset label is not mapped under a scheme, with the reason.",
         "ある写像方式でデータセットのラベルを写さないことと、その理由の記録。")
    term(MAP.MappingScheme, OWL.Class, "Mapping Scheme", "写像方式",
         "A documented scheme for mapping dataset labels to Plutchik emotions.",
         "データセットのラベルを Plutchik の感情に写す、出典つきの方式。")
    for c in (MAP.ComponentMapping, MAP.ConceptMapping):
        g.add((c, RDFS.subClassOf, MAP.LabelMapping))
    for p, typ, en, ja, den, dja, rng in [
        (MAP.dataset, OWL.DatatypeProperty, "dataset", "データセット", "The dataset the label belongs to.", "ラベルが属するデータセット。", XSD.string),
        (MAP.sourceLabel, OWL.DatatypeProperty, "source label", "元のラベル", "The label as written in the dataset.", "データセットに書かれたとおりのラベル。", XSD.string),
        (MAP.basis, OWL.DatatypeProperty, "basis", "根拠", "Why the label is mapped (or not mapped) as stated.", "そのように写す（または写さない）根拠。", XSD.string),
        (MAP.mapsTo, OWL.ObjectProperty, "maps to", "写す先", "The Plutchik emotion a label mapping targets.", "ラベル写像の写す先の Plutchik の感情。", PLU.PlutchikEmotion),
        (MAP.inScheme, OWL.ObjectProperty, "in scheme", "写像方式", "The mapping scheme a mapping record belongs to.", "写像の記録が属する写像方式。", MAP.MappingScheme),
        (MAP.label, OWL.ObjectProperty, "label", "ラベル", "The dataset label concept a mapping record is about.", "写像の記録が対象とするデータセットのラベル概念。", SKOS.Concept),
        (MAP.matchType, OWL.ObjectProperty, "match type", "対応の種類", "The SKOS mapping property (closeMatch / broadMatch) that holds from the label concept to the target.", "ラベル概念から写す先へ成り立つ SKOS の対応関係（closeMatch / broadMatch）。", RDF.Property),
    ]:
        term(p, typ, en, ja, den, dja)
        g.add((p, RDFS.range, rng))

    schemes = {
        "LimCheong2024": ("Lim & Cheong (2024) mapping", "Lim & Cheong (2024) の写像", CITE_LC,
                          "The component mapping used by Lim & Cheong (2024); kept for reproducing CombineEFOMoE experiments.",
                          "Lim & Cheong (2024) が使った成分写像。CombineEFOMoE の実験を再現するために残す。"),
        "Plutchik2001Names": ("Plutchik (2001) names mapping", "Plutchik (2001) の名前に基づく写像", f"{CITE_PLUTCHIK} {CITE_DEMSZKY}",
                              "Maps each label to one Plutchik emotion (basic, intensity variant or dyad) by name, falling back to the Demszky et al. (2020) Ekman grouping; unmapped labels carry a reason.",
                              "各ラベルを名前で Plutchik の感情（基本感情・強度の変種・dyad）1 つに写し、当たらなければ Demszky et al. (2020) の Ekman 対応を使う。写さないラベルには理由を付ける。"),
    }
    for k, (en, ja, cite, den, dja) in schemes.items():
        term(MAP[k], OWL.NamedIndividual, en, ja, den, dja)
        g.add((MAP[k], RDF.type, MAP.MappingScheme))
        g.add((MAP[k], DCTERMS.bibliographicCitation, Literal(cite)))

    for ds, labels in (("semeval2018", SEMEVAL), ("goemotions", GOEMOTIONS)):
        cs = MAP[f"{ds}_labels"]
        g.add((cs, RDF.type, SKOS.ConceptScheme))
        g.add((cs, RDFS.label, Literal(DATASET_LABEL[ds][0], lang="en"))); g.add((cs, RDFS.label, Literal(DATASET_LABEL[ds][1], lang="ja")))
        for lab in labels:
            c = MAP[f"{ds}/{lab}"]
            g.add((c, RDF.type, SKOS.Concept)); g.add((c, SKOS.inScheme, cs))
            g.add((c, SKOS.prefLabel, Literal(lab, lang="en"))); g.add((c, SKOS.notation, Literal(lab)))
            # Lim & Cheong
            r = MAP[f"lc_{ds}_{lab}"]
            g.add((r, MAP.inScheme, MAP.LimCheong2024)); g.add((r, MAP.label, c))
            g.add((r, MAP.dataset, Literal(ds))); g.add((r, MAP.sourceLabel, Literal(lab)))
            tg = LIM_CHEONG[ds][lab]
            if tg:
                g.add((r, RDF.type, MAP.ComponentMapping))
                for t in tg:
                    g.add((r, MAP.mapsTo, PLU[t]))
                g.add((r, MAP.basis, Literal(f"Lim & Cheong (2024): {lab} -> {' + '.join(tg)}.")))
            else:
                g.add((r, RDF.type, MAP.UnmappedLabel))
                g.add((r, MAP.basis, Literal("Dropped by Lim & Cheong (2024).")))
            # Plutchik 2001 names
            r = MAP[f"pn_{ds}_{lab}"]
            g.add((r, MAP.inScheme, MAP.Plutchik2001Names)); g.add((r, MAP.label, c))
            g.add((r, MAP.dataset, Literal(ds))); g.add((r, MAP.sourceLabel, Literal(lab)))
            target, mt, basis = curated(ds, lab, terms, core)
            g.add((r, MAP.basis, Literal(basis)))
            if target is None:
                g.add((r, RDF.type, MAP.UnmappedLabel))
            else:
                g.add((r, RDF.type, MAP.ConceptMapping))
                g.add((r, MAP.mapsTo, target)); g.add((r, MAP.matchType, mt))
                g.add((c, mt, target))   # 直接の SKOS 対応（Plutchik2001Names 方式のみ）
    return g


if __name__ == "__main__":
    g = build()
    header = ("# EFO-Plutchik v0.5.0 のデータセットラベル写像。ontology/build_mappings.py が生成する（直接編集しない）。\n"
              "# 方式 2 つ: map:LimCheong2024（再現用、成分写像）/ map:Plutchik2001Names（名前に基づく、強度・dyad まで）。\n")
    open(OUT, "w", encoding="utf-8").write(header + g.serialize(format="turtle"))
    print(f"wrote {OUT} ({len(g)} triples)")
