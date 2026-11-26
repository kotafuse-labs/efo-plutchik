"""データセットのラベル → EFO-Plutchik の写像（写像のモジュール 0.6.1。コアのオントロジーは 0.5.0 のまま）を生成する。出力: ontology/plutchik-mappings.ttl

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
  追加のデータセット（CombineEFOMoE #85）では、1 に次の規則を足す:
    1b. ラベルが、Plutchik (2001) の語の形容詞・分詞の形として NAME_VARIANTS の表に載っている → skos:closeMatch
        （map:nameVariantOf に元の語を記録する。表に無い語形・類義語は写さない）。
    4. 複数の語を "or" でつないだラベル、限定のついたラベル（negative surprise など）、感情でないラベルは写さない（理由つき）。
  追加のデータセットは map:Plutchik2001Names だけが対象で、map:LimCheong2024 は SemEval-2018 E-c と GoEmotions だけを対象にする
  （方式ごとの対象は map:coversDataset）。ラベルの付け方（読み手の注釈・書き手の選択・得点の区切り）を map:labellingMethod に記録する。
  データの本文は扱わない（ラベルの名前と出典だけ）。
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

# ---- CombineEFOMoE #85: 追加のデータセット。ラベルの名前は 2026-11-25〜26 に論文・質問票・配布物の説明で確認した（checked に、どこで確認したかを書く）。
# データファイルの中の値まで確認したのは SemEval-2018 EI-oc・Electoral Tweets・GoodNewsEveryone（0.6.1）。利用条件は記録しない（配布元の dcterms:source を見ること）。----
# method: ReaderAnnotated（読み手が付けた）/ WriterChosen（書き手に与えられた、または書き手が選んだ）/ ScoreThresholded（得点を区切った）
READER, WRITER, SCORE = "ReaderAnnotated", "WriterChosen", "ScoreThresholded"
PLUTCHIK8 = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
EXTRA = {
    "empatheticdialogues": {
        "name": ("EmpatheticDialogues", "EmpatheticDialogues のラベル"), "method": WRITER, "cardinality": "single", "intensity": None,
        "labels": ["afraid", "angry", "annoyed", "anticipating", "anxious", "apprehensive", "ashamed", "caring", "confident", "content",
                   "devastated", "disappointed", "disgusted", "embarrassed", "excited", "faithful", "furious", "grateful", "guilty", "hopeful",
                   "impressed", "jealous", "joyful", "lonely", "nostalgic", "prepared", "proud", "sad", "sentimental", "surprised", "terrified",
                   "trusting"],
        "cite": "Rashkin, H., Smith, E. M., Li, M. and Boureau, Y.-L. (2019). Towards Empathetic Open-domain Conversation Models: A New Benchmark and Dataset. ACL 2019. arXiv:1811.00207.",
        "source": "https://github.com/facebookresearch/EmpatheticDialogues",
        "checked": "Paper, Figure 3 (32 emotion labels). The values in the data files were not checked."},
    "crowdenvent": {
        "name": ("crowd-enVENT", "crowd-enVENT のラベル"), "method": WRITER, "cardinality": "single", "intensity": "writer self-rating, 1-5",
        "labels": ["anger", "boredom", "disgust", "fear", "guilt", "joy", "pride", "relief", "sadness", "shame", "surprise", "trust", "no-emotion"],
        "cite": "Troiano, E., Oberlaender, L. and Klinger, R. (2023). Dimensional Modeling of Emotions in Text with Appraisal Theories: Corpus Creation, Annotation Reliability, and Prediction. Computational Linguistics 49(1), 1-72. doi:10.1162/coli_a_00461.",
        "source": "https://www.ims.uni-stuttgart.de/data/appraisalemotion",
        "checked": "Paper, Section 3 (12 emotion labels and a no-emotion category). The values in the data files were not checked."},
    "goodnewseveryone": {
        "name": ("GoodNewsEveryone", "GoodNewsEveryone のラベル"), "method": READER, "cardinality": "single (dominant emotion)", "intensity": "low / medium / high",
        "labels": ["anger", "annoyance", "disgust", "fear", "guilt", "joy", "love_including_like", "negative_anticipation_including_pessimism",
                   "negative_surprise", "positive_anticipation_including_optimism", "positive_surprise", "pride", "sadness", "shame", "trust"],
        "cite": "Bostan, L. A. M., Kim, E. and Klinger, R. (2020). GoodNewsEveryone: A Corpus of News Headlines Annotated with Emotions, Semantic Roles, and Reader Perception. LREC 2020. arXiv:1912.03184.",
        "source": "https://www.ims.uni-stuttgart.de/data/goodnewseveryone",
        "checked": "Label values of the gold dominant emotion in the released data (gne-release-v1.0.jsonl, 15 values), checked 2026-11-27. The paper (Section 3.4) lists the same 15 categories under shorter names (love, pessimism, optimism, negative surprise, positive surprise); the data name five of them as composites, and those are not mapped. The first annotation phase also offered 'No emotion', which is not one of the 15 categories."},
    "brighter_eng": {
        "name": ("BRIGHTER (English) / SemEval-2025 Task 11", "BRIGHTER（英語）/ SemEval-2025 Task 11 のラベル"), "method": READER, "cardinality": "multi", "intensity": "0-3 per emotion (Track B)",
        "labels": ["anger", "fear", "joy", "sadness", "surprise"],
        "cite": "Muhammad, S. H. et al. (2025). BRIGHTER: BRIdging the Gap in Human-Annotated Textual Emotion Recognition Datasets for 28 Languages. arXiv:2502.11926.",
        "source": "https://huggingface.co/datasets/brighter-dataset/BRIGHTER-emotion-categories",
        "checked": "Paper, Section 2 (the English data do not include disgust; intensity 0-3)."},
    "xed": {
        "name": ("XED (English)", "XED（英語）のラベル"), "method": READER, "cardinality": "multi", "intensity": None, "labels": PLUTCHIK8 + ["neutral"],
        "cite": "Oehman, E., Pamies, M., Kajava, K. and Tiedemann, J. (2020). XED: A Multilingual Dataset for Sentiment Analysis and Emotion Detection. COLING 2020.",
        "source": "https://github.com/Helsinki-NLP/XED",
        "checked": "Paper; repository README (label numbers 1-8, neutral 0); dataset card."},
    "ssec": {
        "name": ("SSEC", "SSEC のラベル"), "method": READER, "cardinality": "multi", "intensity": None, "labels": PLUTCHIK8,
        "cite": "Schuff, H., Barnes, J., Mohme, J., Pado, S. and Klinger, R. (2017). Annotation, Modelling and Analysis of Fine-Grained Emotions on a Stance and Sentiment Detection Corpus. WASSA 2017.",
        "source": "https://www.romanklinger.de/ssec/",
        "checked": "Paper, Section 1 (the eight Plutchik emotions; multi-label). The values in the data files were not checked."},
    "enisear": {
        "name": ("enISEAR", "enISEAR のラベル"), "method": WRITER, "cardinality": "single", "intensity": "writer self-rating, 4 levels",
        "labels": ["anger", "disgust", "fear", "guilt", "joy", "sadness", "shame"],
        "cite": "Troiano, E., Pado, S. and Klinger, R. (2019). Crowdsourcing and Validating Event-focused Emotion Corpora for German and English. ACL 2019, 4005-4011.",
        "source": "https://www.romanklinger.de/data-sets/deISEARenISEAR.zip",
        "checked": "Paper, Sections 1 and 3; readme and column header of the data (the values of the label column were not checked)."},
    "dailydialog": {
        "name": ("DailyDialog", "DailyDialog のラベル"), "method": READER, "cardinality": "single", "intensity": None,
        "labels": ["no emotion", "anger", "disgust", "fear", "happiness", "sadness", "surprise"],
        "cite": "Li, Y., Su, H., Shen, X., Li, W., Cao, Z. and Niu, S. (2017). DailyDialog: A Manually Labelled Multi-turn Dialogue Dataset. IJCNLP 2017, 986-995.",
        "source": "http://yanran.li/dailydialog",
        "checked": "Paper, Section 3 (six emotions and one additional category for other emotions). The additional category is written 'no emotion' here, the name commonly used for class 0 of the released data; that name was not checked in the data files."},
    "semeval2018_eioc": {
        "name": ("SemEval-2018 Task 1 EI-oc", "SemEval-2018 Task 1 EI-oc のラベル"), "method": SCORE, "cardinality": "single (one emotion per file)",
        "intensity": "0-3 ordinal classes cut from best-worst-scaling scores",
        "labels": ["anger", "fear", "joy", "sadness"],
        "cite": "Mohammad, S. M., Bravo-Marquez, F., Salameh, M. and Kiritchenko, S. (2018). SemEval-2018 Task 1: Affect in Tweets. SemEval 2018.",
        "source": "https://competitions.codalab.org/competitions/17751",
        "checked": "Paper, Sections 2 and 3.4.3; class strings in the data files. The intensity classes are not mapped to Plutchik intensity variants: a low class is a band of scores, not the label 'annoyance'."},
    "electoraltweets": {
        "name": ("Electoral Tweets (Questionnaire 2)", "Electoral Tweets（質問票 2）のラベル"), "method": READER, "cardinality": "single (per response)", "intensity": "low / medium / high",
        "labels": ["acceptance", "admiration", "calmness or serenity", "joy or happiness or elation", "like", "trust",
                   "anger or annoyance or hostility or fury", "disappointment", "dislike", "disgust", "fear or apprehension or panic or terror", "hate",
                   "indifference", "sadness or gloominess or grief or sorrow", "amazement", "anticipation or expectancy or interest", "surprise",
                   "uncertainty or indecision or confusion", "vigilance"],
        "cite": "Mohammad, S. M., Zhu, X., Kiritchenko, S. and Martin, J. (2015). Sentiment, emotion, purpose, and style in electoral tweets. Information Processing & Management 51(4), 480-499. doi:10.1016/j.ipm.2014.09.003.",
        "source": "https://saifmohammad.com/WebDocs/ElectoralTweetsData.zip",
        "checked": "Annotation questionnaire in the data archive (19 options, 7 of them composite). The data files write one option with two spaces ('anticipation or  expectancy or interest'); the questionnaire spelling is used here. The paper itself was not read."},
}
# 規則 1b: 形容詞・分詞の形 → Plutchik (2001) の語（表に無い語形と類義語は写さない）
NAME_VARIANTS = {"angry": "anger", "annoyed": "annoyance", "anticipating": "anticipation", "anxious": "anxiety", "apprehensive": "apprehension",
                 "ashamed": "shame", "disgusted": "disgust", "guilty": "guilt", "hopeful": "hope", "joyful": "joy", "proud": "pride", "sad": "sadness",
                 "sentimental": "sentimentality", "surprised": "surprise", "terrified": "terror", "trusting": "trust"}
NOT_EMOTION = {"neutral", "no-emotion"}
RESIDUAL = {"no emotion"}                   # DailyDialog: 論文では「ほかの感情」をまとめる追加の区分
QUALIFIED = {"negative_surprise": "surprise", "positive_surprise": "surprise"}
# GoodNewsEveryone のデータの複合のラベル（論文では love / pessimism / optimism と書かれるが、データでは別の語を含む名前）
INCLUDING = {"love_including_like": "love", "negative_anticipation_including_pessimism": "anticipation, pessimism",
             "positive_anticipation_including_optimism": "anticipation, optimism"}
LC_DATASETS = ("semeval2018", "goemotions")
# 元の 2 データセットのラベルの付け方と出典（CombineEFOMoE #85 で追記。ラベルの一覧そのものは v0.5.0 のまま）
ORIGINAL_META = {
    "semeval2018": {"method": READER, "cardinality": "multi", "intensity": None,
                    "cite": "Mohammad, S. M., Bravo-Marquez, F., Salameh, M. and Kiritchenko, S. (2018). SemEval-2018 Task 1: Affect in Tweets. SemEval 2018.",
                    "source": "https://competitions.codalab.org/competitions/17751",
                    "checked": "Task paper (11 emotions; crowdsourced annotation, seven annotators per tweet requested). Label list unchanged from release 0.5.0."},
    "goemotions": {"method": READER, "cardinality": "multi", "intensity": None,
                   "cite": "Demszky, D., Movshovitz-Attias, D., Ko, J., Cowen, A., Nemade, G. and Ravi, S. (2020). GoEmotions: A Dataset of Fine-Grained Emotions. ACL 2020, 4040-4054.",
                   "source": "https://github.com/google-research/google-research/tree/master/goemotions",
                   "checked": "Paper (27 emotion labels and neutral; three or five raters per example). Label list unchanged from release 0.5.0."},
}
ALL_DATASETS = {"semeval2018": SEMEVAL, "goemotions": GOEMOTIONS, **{k: v["labels"] for k, v in EXTRA.items()}}


def slug(label: str) -> str:
    """ラベル → IRI の local name に使える形（空白を _ に）。"""
    return label.replace(" ", "_")


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
    if dataset in EXTRA:
        if label in terms:
            return terms[label], SKOS.closeMatch, f"Label name identical to the Plutchik (2001) term '{label}'."
        if label in NAME_VARIANTS:
            t = NAME_VARIANTS[label]
            return terms[t], SKOS.closeMatch, f"Label is the adjective or participle form of the Plutchik (2001) term '{t}' (listed name variant)."
        if label in NOT_EMOTION:
            return None, None, "Not an emotion category."
        if label in RESIDUAL:
            return None, None, "Residual category (no emotion or other emotions); not an emotion category of its own."
        if " or " in label:
            hit = [x for x in label.split(" or ") if x in terms]
            return None, None, ("Composite label listing several terms" + (f" (Plutchik terms among them: {', '.join(hit)})" if hit else "")
                                + "; not mapped to a single Plutchik emotion.")
        if label in INCLUDING:
            return None, None, (f"Composite label covering more than one category (Plutchik terms among them: {INCLUDING[label]}); "
                                "not mapped to a single Plutchik emotion.")
        if label in QUALIFIED:
            return None, None, f"Qualified form of the Plutchik term '{QUALIFIED[label]}' (valence-specific); not the same category."
        return None, None, "No Plutchik (2001) term of this name and no listed name variant."
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
    g.add((onto, OWL.versionInfo, Literal("0.6.1")))
    g.add((onto, RDFS.comment, Literal("Mapping module 0.6.1 (12 datasets, labelling methods, name-variant rules). It imports the core ontology 0.5.0, which is unchanged.", lang="en")))
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
    term(MAP.LabellingMethod, OWL.Class, "Labelling Method", "ラベルの付け方",
         "How the instances of a dataset received their emotion labels.", "データセットの事例に感情のラベルが付いた方法。")
    for k, en, ja, den, dja in [
        (READER, "reader-annotated", "読み手の注釈", "Labels assigned by readers of the text (crowd workers, students or experts).", "本文の読み手（クラウドワーカー・学生・専門家）が付けたラベル。"),
        (WRITER, "writer-chosen", "書き手の選択", "Labels given to or chosen by the writer, who then wrote the text for that label.", "書き手に与えられた、または書き手が選んだラベル。本文はそのラベルに合わせて書かれた。"),
        (SCORE, "score-thresholded", "得点の区切り", "Classes obtained by cutting a continuous human-derived score into bands.", "人手に由来する連続の得点を区切って作ったクラス。"),
    ]:
        term(MAP[k], OWL.NamedIndividual, en, ja, den, dja)
        g.add((MAP[k], RDF.type, MAP.LabellingMethod))
    for p, typ, en, ja, den, dja, rng in [
        (MAP.dataset, OWL.DatatypeProperty, "dataset", "データセット", "The dataset the label belongs to.", "ラベルが属するデータセット。", XSD.string),
        (MAP.sourceLabel, OWL.DatatypeProperty, "source label", "元のラベル", "The label as written in the dataset.", "データセットに書かれたとおりのラベル。", XSD.string),
        (MAP.basis, OWL.DatatypeProperty, "basis", "根拠", "Why the label is mapped (or not mapped) as stated.", "そのように写す（または写さない）根拠。", XSD.string),
        (MAP.mapsTo, OWL.ObjectProperty, "maps to", "写す先", "The Plutchik emotion a label mapping targets.", "ラベル写像の写す先の Plutchik の感情。", PLU.PlutchikEmotion),
        (MAP.inScheme, OWL.ObjectProperty, "in scheme", "写像方式", "The mapping scheme a mapping record belongs to.", "写像の記録が属する写像方式。", MAP.MappingScheme),
        (MAP.label, OWL.ObjectProperty, "label", "ラベル", "The dataset label concept a mapping record is about.", "写像の記録が対象とするデータセットのラベル概念。", SKOS.Concept),
        (MAP.coversDataset, OWL.ObjectProperty, "covers dataset", "対象のデータセット", "A dataset label scheme that a mapping scheme covers; every label of a covered dataset has one record in the scheme.", "写像方式が対象とするデータセットのラベル体系。対象のデータセットのラベルは、その方式に記録を 1 つずつ持つ。", SKOS.ConceptScheme),
        (MAP.labellingMethod, OWL.ObjectProperty, "labelling method", "ラベルの付け方", "How the instances of the dataset received their labels.", "そのデータセットの事例にラベルが付いた方法。", MAP.LabellingMethod),
        (MAP.datasetKey, OWL.DatatypeProperty, "dataset key", "データセットのキー", "The short key of the dataset; mapping records of its labels carry the same value in map:dataset.", "データセットの短いキー。そのラベルの写像の記録は、map:dataset に同じ値を持つ。", XSD.string),
        (MAP.variantForm, OWL.DatatypeProperty, "variant form", "語形", "The adjective or participle form listed by a name-variant rule.", "語形の規則が挙げる形容詞・分詞の形。", XSD.string),
        (MAP.variantOfTerm, OWL.ObjectProperty, "variant of term", "語形の元の感情", "The Plutchik emotion whose name a name-variant rule relates the form to.", "語形の規則が、その形を名前に結びつける Plutchik の感情。", PLU.PlutchikEmotion),
        (MAP.nameVariantOf, OWL.DatatypeProperty, "name variant of", "語形の元の語", "The Plutchik (2001) term of which the dataset label is a listed adjective or participle form.", "データセットのラベルが、その形容詞・分詞の形として表に載っている Plutchik (2001) の語。", XSD.string),
        (MAP.labelCardinality, OWL.DatatypeProperty, "label cardinality", "ラベルの数", "Whether an instance carries one label or several.", "1 つの事例が持つラベルが 1 つか複数か。", XSD.string),
        (MAP.intensityScale, OWL.DatatypeProperty, "intensity scale", "強度の尺度", "The scale on which the dataset records emotion intensity, if it does.", "データセットが感情の強度を記録する場合の尺度。", XSD.string),
        (MAP.labelsCheckedIn, OWL.DatatypeProperty, "labels checked in", "ラベルの確認元", "Where the label list was checked, and what was not checked.", "ラベルの一覧を確認した場所と、確認していない点。", XSD.string),
        (MAP.matchType, OWL.ObjectProperty, "match type", "対応の種類", "The SKOS mapping property (closeMatch / broadMatch) that holds from the label concept to the target.", "ラベル概念から写す先へ成り立つ SKOS の対応関係（closeMatch / broadMatch）。", RDF.Property),
    ]:
        term(p, typ, en, ja, den, dja)
        g.add((p, RDFS.range, rng))

    schemes = {
        "LimCheong2024": ("Lim & Cheong (2024) mapping", "Lim & Cheong (2024) の写像", CITE_LC,
                          "The component mapping used by Lim & Cheong (2024); kept for reproducing CombineEFOMoE experiments.",
                          "Lim & Cheong (2024) が使った成分写像。CombineEFOMoE の実験を再現するために残す。"),
        "Plutchik2001Names": ("Plutchik (2001) names mapping", "Plutchik (2001) の名前に基づく写像", f"{CITE_PLUTCHIK} {CITE_DEMSZKY}",
                              "Maps each label to one Plutchik emotion (basic, intensity variant or dyad) by an identical name or by a listed adjective or participle form of the name (map:NameVariantRule). For GoEmotions only, labels without such a name fall back to the Demszky et al. (2020) Ekman grouping. Composite, qualified and non-emotion labels are not mapped; unmapped labels carry a reason. A match by name does not establish that the dataset label and the Plutchik emotion are the same concept.",
                              "各ラベルを、名前の一致か、表に載る形容詞・分詞の形（map:NameVariantRule）で、Plutchik の感情（基本感情・強度の変種・dyad）1 つに写す。GoEmotions だけは、当たらないラベルに Demszky et al. (2020) の Ekman 対応を使う。複数の語をつないだラベル・限定のついたラベル・感情でないラベルは写さず、理由を記録する。名前の一致は、データセットのラベルと Plutchik の感情が同じ概念であることまでは示さない。"),
    }
    term(MAP.NameVariantRule, OWL.Class, "Name Variant Rule", "語形の規則",
         "A listed pair of an adjective or participle form and the Plutchik (2001) term it derives from; the only forms accepted as name variants.",
         "形容詞・分詞の形と、その元になる Plutchik (2001) の語の組。語形として認めるのは、ここに挙げたものだけ。")
    for form, t in sorted(NAME_VARIANTS.items()):
        v = MAP[f"variant_{form}"]
        g.add((v, RDF.type, MAP.NameVariantRule)); g.add((v, MAP.variantForm, Literal(form))); g.add((v, MAP.variantOfTerm, terms[t]))
    for k, (en, ja, cite, den, dja) in schemes.items():
        term(MAP[k], OWL.NamedIndividual, en, ja, den, dja)
        g.add((MAP[k], RDF.type, MAP.MappingScheme))
        g.add((MAP[k], DCTERMS.bibliographicCitation, Literal(cite)))

    for ds, labels in ALL_DATASETS.items():
        cs = MAP[f"{ds}_labels"]
        g.add((cs, RDF.type, SKOS.ConceptScheme))
        g.add((MAP.Plutchik2001Names, MAP.coversDataset, cs))
        if ds in LC_DATASETS:
            g.add((MAP.LimCheong2024, MAP.coversDataset, cs))
        x = ORIGINAL_META[ds] if ds in LC_DATASETS else EXTRA[ds]
        en, ja = DATASET_LABEL[ds] if ds in LC_DATASETS else x["name"]
        g.add((cs, MAP.datasetKey, Literal(ds)))
        g.add((cs, MAP.labellingMethod, MAP[x["method"]])); g.add((cs, MAP.labelCardinality, Literal(x["cardinality"])))
        g.add((cs, DCTERMS.bibliographicCitation, Literal(x["cite"]))); g.add((cs, DCTERMS.source, URIRef(x["source"])))
        g.add((cs, MAP.labelsCheckedIn, Literal(x["checked"])))
        if x["intensity"]:
            g.add((cs, MAP.intensityScale, Literal(x["intensity"])))
        g.add((cs, RDFS.label, Literal(en, lang="en"))); g.add((cs, RDFS.label, Literal(ja, lang="ja")))
        for lab in labels:
            c = MAP[f"{ds}/{slug(lab)}"]
            g.add((c, RDF.type, SKOS.Concept)); g.add((c, SKOS.inScheme, cs))
            g.add((c, SKOS.prefLabel, Literal(lab, lang="en"))); g.add((c, SKOS.notation, Literal(lab)))
            if ds in LC_DATASETS:                  # Lim & Cheong（SemEval-2018 E-c と GoEmotions だけ）
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
            r = MAP[f"pn_{ds}_{slug(lab)}"]
            g.add((r, MAP.inScheme, MAP.Plutchik2001Names)); g.add((r, MAP.label, c))
            g.add((r, MAP.dataset, Literal(ds))); g.add((r, MAP.sourceLabel, Literal(lab)))
            target, mt, basis = curated(ds, lab, terms, core)
            g.add((r, MAP.basis, Literal(basis)))
            if target is None:
                g.add((r, RDF.type, MAP.UnmappedLabel))
            else:
                g.add((r, RDF.type, MAP.ConceptMapping))
                g.add((r, MAP.mapsTo, target)); g.add((r, MAP.matchType, mt))
                if ds in EXTRA and lab in NAME_VARIANTS and lab not in terms:
                    g.add((r, MAP.nameVariantOf, Literal(NAME_VARIANTS[lab])))
                g.add((c, mt, target))   # 直接の SKOS 対応（Plutchik2001Names 方式のみ）
    return g


if __name__ == "__main__":
    g = build()
    header = ("# EFO-Plutchik のデータセットラベル写像（写像のモジュール 0.6.1。コアのオントロジーは 0.5.0 のまま）。ontology/build_mappings.py が生成する（直接編集しない）。\n"
              "# 方式 2 つ: map:LimCheong2024（再現用、成分写像。2 データセット）/ map:Plutchik2001Names（名前に基づく、強度・dyad まで。12 データセット）。\n")
    open(OUT, "w", encoding="utf-8").write(header + g.serialize(format="turtle"))
    print(f"wrote {OUT} ({len(g)} triples)")
