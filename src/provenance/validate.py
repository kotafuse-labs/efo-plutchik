"""
EFO-Plutchik provenance パイプラインの検証 (Phase 3, RQ-P)。

efo-plutchik.ttl (TBox) + sample_occurrences.ttl (基本感情 occurrence) をロード
  → infer_dyads.rq (SPARQL CONSTRUCT) で dyad occurrence を materialize
  → shapes.ttl で SHACL 構造検証
  → competency_questions.rq の 7 CQ を実行
という「推論 → 構造検証 → 意味検証」を一気通貫で回す。

実行: python3 src/provenance/validate.py
依存: rdflib, pyshacl (ローカル済み)。学習不要・完全にローカルで完結。
"""
import os

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Namespace, URIRef

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ONT = os.path.join(REPO, "ontology")
EFO_SRC = os.path.join(ONT, "efo-src")

# EFO の共有 namespace。efo-plutchik はこれらの IRI を subClassOf / subPropertyOf /
# skos:closeMatch で参照する (vocabulary-level alignment)。
EMO = "http://www.ontologydesignpatterns.org/ont/emotions/EmoCore.owl#"
BE = "http://www.ontologydesignpatterns.org/ont/emotions/BasicEmotions.owl#"
# owl:imports をローカル解決するための EFO スキーマ (EmoCore / BasicEmotions)。
# 上流 https://github.com/StenDoipanni/EFO にはライセンスの宣言がなく再配布できないので、
# リポには含めず、初回に固定コミットから ontology/efo-src/ (gitignore 済) へ取得して sha256 を照合する。
# 以後はそのキャッシュを使う (オフラインで動く)。データ KG (CREMA/FER) はスキーマでないため対象外。
EFO_UPSTREAM_COMMIT = "eeeda93251e989f87bac189a39ad8e41154ea579"
EFO_UPSTREAM_RAW = "https://raw.githubusercontent.com/StenDoipanni/EFO/" + EFO_UPSTREAM_COMMIT + "/"
EFO_LOCAL_SCHEMA = ("EmoCore_iswc.ttl", "BE_iswc.ttl")
EFO_SHA256 = {
    "EmoCore_iswc.ttl": "51b6b81c23de6624ad84faae7c998355eaf87e18c9422764df53762706667ef8",
    "BE_iswc.ttl": "374ced1e27747211d59e5e5db6d71b8a6dea5ebc0b45689b3599bd99bd1f7f73",
}


class EFOUnavailable(RuntimeError):
    """EFO スキーマがキャッシュになく、上流からも取得できない (オフライン等)。"""


def ensure_efo_schema(fetch=True):
    """EFO スキーマの 2 ファイルを ontology/efo-src/ に用意し、そのパスのリストを返す。

    キャッシュがあれば sha256 を照合して使う。なければ fetch=True のとき固定コミットから取得する。
    hash が一致しないファイルは使わない (上流の変更やファイルの破損を検出する)。
    """
    import hashlib
    import urllib.request

    os.makedirs(EFO_SRC, exist_ok=True)
    paths = []
    for fname in EFO_LOCAL_SCHEMA:
        path = os.path.join(EFO_SRC, fname)
        if not os.path.exists(path):
            if not fetch:
                raise EFOUnavailable(f"{path} がない (fetch=False)")
            try:
                with urllib.request.urlopen(EFO_UPSTREAM_RAW + fname, timeout=30) as r:
                    data = r.read()
            except OSError as e:
                raise EFOUnavailable(f"上流から {fname} を取得できない: {e}") from e
            if hashlib.sha256(data).hexdigest() != EFO_SHA256[fname]:
                raise EFOUnavailable(f"取得した {fname} の sha256 が固定値と一致しない")
            with open(path, "wb") as f:
                f.write(data)
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != EFO_SHA256[fname]:
                raise EFOUnavailable(f"キャッシュ {path} の sha256 が固定値と一致しない (削除すれば取得し直す)")
        paths.append(path)
    return paths

PREFIXES = """
PREFIX plu: <https://w3id.org/efo-plutchik#>
PREFIX emo: <http://www.ontologydesignpatterns.org/ont/emotions/EmoCore.owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


def load_kg():
    g = Graph()
    g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")
    g.parse(os.path.join(ONT, "sample_occurrences.ttl"), format="turtle")
    return g


def infer_dyads(g):
    with open(os.path.join(ONT, "infer_dyads.rq"), encoding="utf-8") as f:
        query = f.read()
    before = len(g)
    for triple in g.query(query):
        g.add(triple)
    print(f"[infer]  materialized dyad triples: +{len(g) - before}")


def run_shacl(g):
    from pyshacl import validate

    shapes = Graph()
    shapes.parse(os.path.join(ONT, "shapes.ttl"), format="turtle")
    conforms, _, text = validate(
        g, shacl_graph=shapes, inference="none", advanced=True, debug=False
    )
    print(f"[SHACL]  conforms = {conforms}")
    if not conforms:
        print(text)
    return conforms


def run_cqs(g):
    with open(os.path.join(ONT, "competency_questions.rq"), encoding="utf-8") as f:
        content = f.read()
    for block in content.split("### "):
        if not block.startswith("CQ-"):
            continue
        title, _, body = block.partition("\n")
        try:
            rows = list(g.query(PREFIXES + body))
            preview = "; ".join(
                ", ".join(str(x).split("#")[-1] for x in row) for row in rows[:4]
            )
            print(f"[{title.strip()}] {len(rows)} row(s): {preview}")
        except Exception as e:  # noqa: BLE001
            print(f"[{title.strip()}] ERROR: {e}")


INJ_PREFIXES = (
    PREFIXES
    + "PREFIX inj: <https://w3id.org/efo-plutchik/injection#>\n"
    + "PREFIX prov: <http://www.w3.org/ns/prov#>\n"
)


def _check_injection_graph(g, verbose=True):
    """efo-plutchik TBox + 注入 provenance KG をマージ済みの Graph に SHACL + CQ を適用する。"""
    from pyshacl import validate

    shapes = Graph()
    shapes.parse(os.path.join(ONT, "injection_shapes.ttl"), format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    if verbose:
        print(f"[inj-SHACL] conforms = {conforms}")
        if not conforms:
            print(text)

    with open(os.path.join(ONT, "injection_cq.rq"), encoding="utf-8") as f:
        content = f.read()
    for block in content.split("### "):
        if not block.startswith("CQ-"):
            continue
        title, _, body = block.partition("\n")
        try:
            rows = list(g.query(INJ_PREFIXES + body))
            preview = "; ".join(", ".join(str(x).split("#")[-1] for x in row) for row in rows[:4])
            if verbose:
                print(f"[{title.strip()}] {len(rows)} row(s): {preview}")
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f"[{title.strip()}] ERROR: {e}")
    return conforms


def validate_injection_graph(kg_graph, verbose=True):
    """注入知識 provenance KG (rdflib Graph) を injection_shapes + injection_cq で検証する。

    本研究の核「verifiable provenance of knowledge influence」の検証側 (RQ4)。
    efo-plutchik.ttl (plu: 個体定義) と生成 KG をマージし、SHACL 構造検証 → CQ を回す。
    学習済 checkpoint 不要 (モック pooled 由来の KG でも検証できる)。
    """
    g = Graph()
    g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")  # plu: 個体定義
    g += kg_graph                                                    # 注入 provenance KG
    return _check_injection_graph(g, verbose)


def validate_injection_kg(kg_path, verbose=True):
    """注入知識 provenance KG (TTL ファイル) を検証する (validate_injection_graph のファイル版)。"""
    kg = Graph()
    kg.parse(kg_path, format="turtle")
    return validate_injection_graph(kg, verbose)


# ====== 理論グラフ (TBox) 自体の検証 — Tier2 ④⑤ ======

def validate_theory_graph(graph=None, verbose=True):
    """理論グラフ (efo-plutchik.ttl) 自体の構造健全性を検証する (Tier2 ④)。

    theory_shapes.ttl の SHACL (primary dyad の構成 2 感情・非対極、基本感情の対極ちょうど 1・非反射) に加え、
    全体カーディナリティ (v0.5.0: 基本 8 / dyad 8+8+8 / 強度の変種 16 / opposite 4 / adjacency 8 / component 48) を SPARQL で sanity 確認する。
    dyad 定義の typo を機械的に弾く。graph=None なら efo-plutchik.ttl をロード。
    """
    from pyshacl import validate

    g = Graph()
    if graph is None:
        g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")
    else:
        g += graph

    shapes = Graph()
    shapes.parse(os.path.join(ONT, "theory_shapes.ttl"), format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    if verbose:
        print(f"[theory-SHACL] conforms = {conforms}")
        if not conforms:
            print(text)

    def count(q):
        return int(list(g.query(PREFIXES + q))[0][0])

    expected = {
        "basic (a plu:BasicEmotion)": ("SELECT (COUNT(?x) AS ?c) WHERE { ?x a plu:BasicEmotion }", 8),
        "primary dyad (a plu:PrimaryDyad)": ("SELECT (COUNT(?x) AS ?c) WHERE { ?x a plu:PrimaryDyad }", 8),
        "opposite triples": ("SELECT (COUNT(*) AS ?c) WHERE { ?a plu:hasOpposite ?b }", 4),
        "secondary dyad (a plu:SecondaryDyad)": ("SELECT (COUNT(?x) AS ?c) WHERE { ?x a plu:SecondaryDyad }", 8),
        "tertiary dyad (a plu:TertiaryDyad)": ("SELECT (COUNT(?x) AS ?c) WHERE { ?x a plu:TertiaryDyad }", 8),
        "intensity variant (a plu:IntensityVariant)": ("SELECT (COUNT(?x) AS ?c) WHERE { ?x a plu:IntensityVariant }", 16),
        "adjacency triples": ("SELECT (COUNT(*) AS ?c) WHERE { ?a plu:isAdjacentTo ?b }", 8),
        "component triples": ("SELECT (COUNT(*) AS ?c) WHERE { ?a plu:hasComponentEmotion ?b }", 48),
    }
    counts_ok = True
    for label, (q, exp) in expected.items():
        got = count(q)
        ok = got == exp
        counts_ok = counts_ok and ok
        if verbose:
            print(f"[theory-count] {label} = {got} (期待 {exp}) {'OK' if ok else '✗'}")
    return conforms and counts_ok


_CLASH_Q = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?x ?c1 ?c2 WHERE {
    { { ?c1 owl:disjointWith ?c2 } UNION { ?c2 owl:disjointWith ?c1 } }
    UNION
    { ?adc a owl:AllDisjointClasses ; owl:members ?l .
      ?l rdf:rest*/rdf:first ?c1 . ?l rdf:rest*/rdf:first ?c2 . }
    ?x a ?c1, ?c2 . FILTER(?c1 != ?c2)
}"""


def check_theory_consistency(graph=None, verbose=True):
    """OWL-RL 閉包後に論理一貫性を検証する (Tier2 ⑤)。

    owlrl で OWL-RL 推論閉包を計算し、互いに素クラス (owl:disjointWith) への同時所属
    (disjoint clash) や owl:Nothing 所属がないかを確認する。基本感情が dyad に混入する等の
    定義ミスは、Dyad ⊂ CompoundEmotion の閉包で BasicEmotion と衝突して検出される。
    graph=None なら efo-plutchik.ttl をロード。
    """
    import owlrl

    g = Graph()
    if graph is None:
        g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")
    else:
        g += graph

    owlrl.DeductiveClosure(
        owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False
    ).expand(g)

    clashes = list(g.query(_CLASH_Q))
    nothing = list(
        g.query("PREFIX owl: <http://www.w3.org/2002/07/owl#> SELECT ?x WHERE { ?x a owl:Nothing }")
    )
    consistent = not clashes and not nothing
    if verbose:
        print(f"[OWL-RL] consistent = {consistent}")
        for r in clashes[:5]:
            print("  clash:", ", ".join(str(x).split("#")[-1] for x in r))
    return consistent


# ====== ドキュメント完全性検証 (FAIR Reusability) ======

_DOC_TYPES = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.NamedIndividual)


def validate_documentation(verbose=True):
    """efo-plutchik.ttl の各 term が rdfs:label + skos:definition を持つか機械検証する。

    doc_shapes.ttl の SHACL (全 owl:Class / ObjectProperty / DatatypeProperty /
    NamedIndividual に rdfs:label と言語タグ付き skos:definition を必須化) を適用し、さらに
    「型付き term のうち label / 定義を欠くもの 0 件」を SPARQL で件数明示に確認する
    (定義文の網羅=FAIR Reusability を機械検証可能な事実へ。新 term を定義なしで足すと即 non-conforming)。
    """
    from pyshacl import validate

    g = Graph()
    g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")

    shapes = Graph()
    shapes.parse(os.path.join(ONT, "doc_shapes.ttl"), format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)

    # 型付き term (クラス/プロパティ/個体) を集め、label / definition の欠落を数える。
    terms = set()
    for t in _DOC_TYPES:
        terms |= set(g.subjects(RDF.type, t))
    missing_label = sorted(str(s).split("#")[-1] for s in terms if not list(g.objects(s, RDFS.label)))
    missing_def = sorted(str(s).split("#")[-1] for s in terms if not list(g.objects(s, SKOS.definition)))
    # v0.5.0: @en / @ja の両方を要求する（片方の言語だけの term も欠落として数える）。
    def _langs(s, p):
        return {getattr(o, "language", None) for o in g.objects(s, p)}
    missing_label += sorted(str(s).split("#")[-1] for s in terms
                            if list(g.objects(s, RDFS.label)) and not {"en", "ja"} <= _langs(s, RDFS.label))
    missing_def += sorted(str(s).split("#")[-1] for s in terms
                          if list(g.objects(s, SKOS.definition)) and not {"en", "ja"} <= _langs(s, SKOS.definition))
    documented = len(terms) - len(set(missing_label) | set(missing_def))

    if verbose:
        print(f"[doc-SHACL] conforms = {conforms}")
        if not conforms:
            print(text)
        print(f"[doc-complete] {documented}/{len(terms)} 型付き term が label+定義を持つ "
              "(class/objprop/dtprop/individual、@en と @ja の両方)")
        if missing_label:
            print(f"  label 欠落 ({len(missing_label)}): {', '.join(missing_label)}")
        if missing_def:
            print(f"  定義欠落 ({len(missing_def)}): {', '.join(missing_def)}")
    return conforms and not missing_label and not missing_def


# ====== owl:imports のローカル解決 + EFO 整合性検証 — Tier1 ③ ======

def load_efo_local(fetch=True):
    """owl:imports をローカルキャッシュ (efo-src/) で解決した EFO スキーマグラフを返す。

    rdflib は owl:imports を自動解決しないため、EmoCore / BasicEmotions の ttl をマージして
    「実際の EFO 定義」を手元に再構成する。ファイルは ensure_efo_schema() が用意する
    (初回のみ上流の固定コミットから取得、以後はキャッシュ)。取得できなければ EFOUnavailable。
    """
    g = Graph()
    for path in ensure_efo_schema(fetch=fetch):
        g.parse(path, format="turtle")
    return g


_ALIGN_PREDS = (RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range, SKOS.closeMatch)


def check_efo_alignment(verbose=True):
    """efo-plutchik が参照する EFO 用語 (emo:/be:) が同梱 EFO 定義に解決するか機械検証する (Tier1 ③)。

    owl:imports は宣言上の参照に留まり、実際の整合は vocabulary-level alignment
    (共有 IRI + skos:closeMatch)。本チェックは efo-plutchik.ttl が subClassOf /
    subPropertyOf / domain / range / skos:closeMatch で参照する emo:/be: 用語を集め、
    同梱ローカル EFO (EmoCore_iswc + BE_iswc) に定義 (subject として出現) があるか照合する。

    - resolved     : 同梱 EFO スキーマに定義あり (真の語彙整合)。
    - local-bridge : efo-plutchik 自身が型宣言する EFO-namespace 用語 (例 emo:EmotionSituation)。
                     EFO core になく本モジュールが framester 等へ橋渡しする自前宣言。
    - unresolved   : 同梱スキーマに定義なし (be:isManifestationOf 等、EFO のデータ KG 側語彙)。

    戻り値: skos:closeMatch で整合する基本感情用語が全て同梱 EFO に解決すれば True。
    """
    plu_g = Graph()
    plu_g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")
    efo_g = load_efo_local()
    efo_subjects = set(efo_g.subjects())
    locally_typed = set(plu_g.subjects(RDF.type, None))

    targets = set()
    for p in _ALIGN_PREDS:
        for o in plu_g.objects(None, p):
            if isinstance(o, URIRef) and (str(o).startswith(EMO) or str(o).startswith(BE)):
                targets.add(o)

    resolved, bridges, unresolved = [], [], []
    for t in sorted(targets):
        short = str(t).split("#")[-1]
        if t in efo_subjects:
            resolved.append(short)
        elif t in locally_typed:
            bridges.append(short)
        else:
            unresolved.append(short)

    if verbose:
        print(f"[EFO-align] ローカルキャッシュの EFO ({len(efo_g)} triples) で {len(resolved)}/{len(targets)} 用語が解決")
        print(f"  resolved     ({len(resolved)}): {', '.join(resolved)}")
        if bridges:
            print(f"  local-bridge ({len(bridges)}): {', '.join(bridges)}  ← EFO へ橋渡しする自前宣言")
        if unresolved:
            print(f"  unresolved   ({len(unresolved)}): {', '.join(unresolved)}  ← EFO データ KG 側語彙 (同梱スキーマに型定義なし)")

    # skos:closeMatch で整合する基本感情用語が全て同梱 EFO に解決することを検証の要とする。
    # (PREFIX 不一致で targets が空になる「黙った合格」を防ぐため件数も確認する)
    closematch = {o for o in plu_g.objects(None, SKOS.closeMatch) if isinstance(o, URIRef)}
    return bool(closematch) and all(o in efo_subjects for o in closematch)


# ====== データセットラベル写像（モジュール 0.6.1。v0.5.0 = CombineEFOMoE #33、追加のデータセット = #85）======

def _mapping_graph():
    g = Graph()
    g.parse(os.path.join(ONT, "efo-plutchik.ttl"), format="turtle")
    g.parse(os.path.join(ONT, "plutchik-mappings.ttl"), format="turtle")
    return g


def validate_mappings(graph=None, verbose=True):
    """Plutchik2001Names 方式の写像と全ラベルの網羅を mapping_shapes.ttl で検証する（conforms が必須）。"""
    from pyshacl import validate

    g = _mapping_graph() if graph is None else graph
    shapes = Graph()
    shapes.parse(os.path.join(ONT, "mapping_shapes.ttl"), format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    if verbose:
        print(f"[mapping-SHACL] conforms = {conforms}")
        if not conforms:
            print(text)
    return conforms


def audit_mappings(graph=None, verbose=True):
    """Lim & Cheong 方式の成分写像を mapping_audit_shapes.ttl で監査し、severity 別の (dataset/label) を返す。

    監査であって合否ではない（既知: GoEmotions confusion の対極合成 = Violation、excitement / disappointment の
    dyad 名不一致 = Warning、CombineEFOMoE #22）。
    """
    from pyshacl import validate

    SH = Namespace("http://www.w3.org/ns/shacl#")
    MAPNS = Namespace("https://w3id.org/efo-plutchik/mapping#")
    g = _mapping_graph() if graph is None else graph
    shapes = Graph()
    shapes.parse(os.path.join(ONT, "mapping_audit_shapes.ttl"), format="turtle")
    _, report, _ = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    out = {}
    for r in report.subjects(RDF.type, SH.ValidationResult):
        sev = str(report.value(r, SH.resultSeverity)).split("#")[-1]
        focus = report.value(r, SH.focusNode)
        key = f"{g.value(focus, MAPNS.dataset)}/{g.value(focus, MAPNS.sourceLabel)}"
        out.setdefault(sev, set()).add(key)
    out = {k: sorted(v) for k, v in out.items()}
    if verbose:
        for sev in ("Violation", "Warning", "Info"):
            print(f"[mapping-audit] {sev:9s} ({len(out.get(sev, []))}): {', '.join(out.get(sev, []))}")
    return out


MAP_PREFIXES = PREFIXES + """PREFIX map: <https://w3id.org/efo-plutchik/mapping#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""


def run_mapping_cqs(graph=None, verbose=True):
    """写像の provenance CQ (mapping_cq.rq の CQ-M1〜M7) を回し、{見出し: 行のリスト} を返す。CQ-M2 / M3 は空が期待値。"""
    g = _mapping_graph() if graph is None else graph
    with open(os.path.join(ONT, "mapping_cq.rq"), encoding="utf-8") as f:
        content = f.read()
    out = {}
    for block in content.split("### "):
        if not block.startswith("CQ-"):
            continue
        title, _, body = block.partition("\n")
        rows = [tuple(None if x is None else str(x) for x in row) for row in g.query(MAP_PREFIXES + body)]
        key = title.split(":")[0].strip()
        out[key] = rows
        if verbose:
            preview = "; ".join(", ".join("" if x is None else x.split("#")[-1] for x in row) for row in rows[:3])
            print(f"[{title.strip()}] {len(rows)} row(s): {preview}")
    return out


# ====== 転移の証拠（証拠のモジュール 0.2.1、CombineEFOMoE #88 → #90、#91 → #92）======

EVD_PREFIXES = MAP_PREFIXES + "PREFIX evd: <https://w3id.org/efo-plutchik/mapping/evidence#>\n"


def _evidence_graph():
    g = _mapping_graph()
    g.parse(os.path.join(ONT, "plutchik-mapping-evidence.ttl"), format="turtle")
    return g


def validate_transfer_evidence(graph=None, verbose=True):
    """転移の証拠を evidence_shapes.ttl で検証する（conforms が必須）。証拠は、写像のモジュールと合わせたグラフで見る。"""
    from pyshacl import validate

    g = _evidence_graph() if graph is None else graph
    shapes = Graph()
    shapes.parse(os.path.join(ONT, "evidence_shapes.ttl"), format="turtle")
    conforms, _, text = validate(g, shacl_graph=shapes, inference="none", advanced=True)
    if verbose:
        print(f"[evidence-SHACL] conforms = {conforms}")
        if not conforms:
            print(text[:3000])
    return conforms


def run_evidence_cqs(graph=None, verbose=True):
    """転移の証拠の CQ (evidence_cq.rq の CQ-T1〜T6) を回し、{見出し: 行のリスト} を返す。どれも一覧で、空が期待値のものは無い。"""
    g = _evidence_graph() if graph is None else graph
    with open(os.path.join(ONT, "evidence_cq.rq"), encoding="utf-8") as f:
        content = f.read()
    out = {}
    for block in content.split("### "):
        if not block.startswith("CQ-"):
            continue
        title, _, body = block.partition("\n")
        rows = [tuple(None if x is None else str(x) for x in row) for row in g.query(EVD_PREFIXES + body)]
        out[title.split(":")[0].strip()] = rows
        if verbose:
            print(f"[{title.strip()[:60]}] {len(rows)} row(s)")
    return out


def main():
    print("=== 理論グラフ自己検証 (Tier2 ④⑤) ===")
    validate_theory_graph()
    check_theory_consistency()
    print("\n=== ドキュメント完全性 (label + 定義, FAIR Reusability) ===")
    validate_documentation()
    print("\n=== EFO 整合性 (owl:imports をローカル解決, Tier1 ③) ===")
    try:
        check_efo_alignment()
    except EFOUnavailable as e:
        print(f"[EFO-align] skip: {e}")
    print("\n=== データセットラベル写像 (モジュール 0.6.1) ===")
    validate_mappings()
    audit_mappings()
    run_mapping_cqs()
    print("\n=== 転移の証拠 (証拠のモジュール 0.2.1) ===")
    validate_transfer_evidence()
    run_evidence_cqs()
    print("\n=== 修論パイプライン (推論→SHACL→CQ) ===")
    g = load_kg()
    print(f"[load]   {len(g)} triples (TBox + sample occurrences)")
    infer_dyads(g)
    print(f"[graph]  {len(g)} triples after inference")
    run_shacl(g)
    run_cqs(g)
    print("done.")


if __name__ == "__main__":
    main()
