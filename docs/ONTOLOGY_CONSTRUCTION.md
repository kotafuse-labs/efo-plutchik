# EFO-Plutchik オントロジーの作り方 (ONTOLOGY_CONSTRUCTION)

> `ontology/efo-plutchik.ttl` を **どう作ったか** の記録。EFO の再利用 → TBox → 推論層 →
> 検証層 → ML 用グラフへの変換までを一気通貫でまとめる。設計判断・限界は `MODELING_DECISIONS.md`。
> 一次資料: TTL 内コメント（設計仕様書 v0.4.0 §5–§7 準拠）・`build_graph.py`・`validate.py`。

---

## 0. 結論（3 行）

1. **EFO を上位語彙として再利用**し、その「理論をモジュールとして差し込む」設計思想に乗せて
   **EFO 互換の Plutchik モジュール**（`plu:`, namespace `https://w3id.org/efo-plutchik#`）を著した。
2. Plutchik 理論（8 基本感情・4 対極・8 primary dyad・dyad 合成規則）を **TBox + 感情個体**として記述。
3. その上に **instance-level 推論層**（dyad 生成 SPARQL）と **検証層**（SHACL + CQ + OWL-RL）を載せ、
   完全ローカルに **conforms=True** を確認。最後に ML 注入用の隣接行列 JSON へコンパイルできる。

## 1. 出発点 = EFO（再利用したもの）

**Emotion Frame Ontology**（De Giorgis & Gangemi, 2024, arXiv:2401.10751）。感情を**意味フレーム**
として捉え DOLCE に整合させた OWL オントロジーで、**複数の感情理論をモジュールとして相互リンク**
できる設計。論文では Ekman を EFO-BE モジュールとして例示する。**この「理論＝モジュール」思想が
本作業の土台**で、Plutchik も 1 モジュールとして著せば EFO-BE 等と相互運用できる。

EFO 一次資料（`ontology/efo-src/`, スキーマのみ。リポには含めず、`validate.py` が上流 StenDoipanni/EFO@eeeda93 から取得してキャッシュする）:
- `EmoCore_iswc.ttl` — `emo:Emotion` を frame として定義（上位クラスの供給元）
- `BE_iswc.ttl` — Ekman Basic Emotions（`skos:closeMatch` の対応先）

> 数 MB のデータ KG（FER-kg / CREMA-kg / WASSA など）は**スキーマでない**ため本パッケージには含めない。

再利用した名前空間: `emo:`(EmoCore) / `be:`(BasicEmotions) / `framester:`(FrameOccurrence) /
`prov:`(PROV-O) / `skos:` / `dcterms:` / `vann:`、独自は `plu:`。

## 2. 作成方針 = 「EFO 互換モジュール」として著す

新規語彙を発明せず、**EFO/標準の上位概念へ `subClassOf`/`subPropertyOf`/`closeMatch` で接続**して
互換を担保する。

| 本モジュールの語彙 | 接続先 | 接続関係 |
|---|---|---|
| `plu:PlutchikEmotion` | `emo:Emotion` | `rdfs:subClassOf` |
| `emo:EmotionSituation` | `framester:FrameOccurrence` | `rdfs:subClassOf`（※local-bridge, `MODELING_DECISIONS.md` A-1）|
| `plu:isManifestationOf` | `be:isManifestationOf` | `rdfs:subPropertyOf`（※未解決, A-2）|
| `plu:derivedFrom` | `prov:wasDerivedFrom` | `rdfs:subPropertyOf` |
| `plu:sourceModel` | `prov:wasAttributedTo` | `rdfs:subPropertyOf` |
| 基本 8 感情の各個体 | `be:Fear` / `be:Anger` / `be:Enjoyment`(Joy) 等 | `skos:closeMatch`（6 本）|

## 3. エンコードした Plutchik 理論（TBox + 個体, §5）

### クラス階層
```
emo:Emotion
└─ plu:PlutchikEmotion
   ├─ plu:BasicEmotion
   └─ plu:CompoundEmotion
      └─ plu:Dyad
         └─ plu:PrimaryDyad
emo:EmotionSituation ⊑ framester:FrameOccurrence
plu:DerivationRule / plu:IntensityReading
```
論理一貫性の公理: `plu:BasicEmotion owl:disjointWith plu:CompoundEmotion`（基本感情が dyad に
混入する定義ミスを OWL-RL 閉包 + 一貫性チェックが検出）。

### 個体として書き下した理論
- **8 基本感情**: Joy, Trust, Fear, Surprise, Sadness, Disgust, Anger, Anticipation
  （うち 6 個に `skos:closeMatch be:*`。Trust/Anticipation は Ekman 非対応＝付けない）
- **4 対極ペア**（`hasOpposite`, `owl:SymmetricProperty`）: Joy↔Sadness / Trust↔Disgust /
  Fear↔Anger / Surprise↔Anticipation
- **8 primary dyad**（`hasComponentEmotion` で構成 2 感情, 計 16 本）:
  Love=Joy+Trust / Submission=Trust+Fear / Awe=Fear+Surprise / Disapproval=Surprise+Sadness /
  Remorse=Sadness+Disgust / Contempt=Disgust+Anger / Aggressiveness=Anger+Anticipation / Optimism=Anticipation+Joy
- **3 派生規則**: `Rule_DyadMin`(TH=0.5) / `_TH03`(0.3) / `_TH07`(0.7) ＝ dyad 強度を構成 2 感情の
  **min** で集約（`MODELING_DECISIONS.md` B-2）。

### 規模（実測）
クラス 8（`plu:` 新規 7 ＋ `emo:EmotionSituation` local-bridge 1）／プロパティ 13（Object 9・
Datatype 4）／個体 19（基本 8 ＋ dyad 8 ＋ rule 3）。**型付き 40 term すべてが label + 定義**を持つ
（`doc_shapes.ttl` + `validate.py:validate_documentation` で機械検証, 40/40）。

## 4. instance-level 推論層（§6）— dyad を生成する

- **入力**: `sample_occurrences.ttl`（事前学習分類器の出力を基本感情 occurrence に写像。閾値未満は
  materialize しない）。各 occ は `sourceText`・`sourceModel` を持つ。
- **規則**: `infer_dyads.rq`（SPARQL CONSTRUCT）。同一 `sourceText` の E1/E2 が両方 TH 以上のとき
  dyad occurrence を生成、強度 = `min(s1,s2)`、`derivedFrom` で 2 基本 occ にリンク、`derivedByRule`
  で規則を記録。3 閾値すべてで生成し感度分析を可能にする。

## 5. 検証層（§7）— 構造と意味を形式検証する

`python src/provenance/validate.py` が以下を完全ローカルで回す（学習・torch 不要）:

| 検証 | 実装 | 期待 |
|------|------|------|
| 理論グラフ構造（dyad 構成・対極の健全性）| `theory_shapes.ttl` | SHACL conforms |
| 論理一貫性（disjoint 公理）| OWL-RL（owlrl）| consistent = True |
| ドキュメント完全性（label + 定義）| `doc_shapes.ttl` | 40/40 |
| EFO 整合（owl:imports をローカル解決）| `efo-src/` + `check_efo_alignment` | 7/9 resolved（1 bridge, 1 open）|
| provenance パイプライン | `infer_dyads.rq`→`shapes.ttl`→`competency_questions.rq` | conforms・CQ-7 完全性 0 |

SHACL 4 Shape（`shapes.ttl`）: 全 occurrence は `isManifestationOf` を 1+／dyad occ は
`derivedFrom` ちょうど 2 + `derivedByRule`／`derivedFrom+` の非循環／派生 occ は各 source と同一
`sourceText`。CQ は 7 問（CQ-7＝provenance 完全性 = derivedFrom を欠く dyad occ が 0）。

## 6. ML 注入用グラフへのコンパイル（`build_graph.py`）

`rdflib` で TTL をパース → 基本 8 感情（**アルファベット順**）＋ dyad 8 のノードと
`hasComponentEmotion`/`hasOpposite` エッジを抽出 → `plutchik_graph.json`（16 ノード, `adjacency`
ほか）を出力。**先頭 8 ノードが分類器ラベル（num_labels=8）と 1:1 対応**する。numpy のみ依存で
torch は不要。実際の注入（GCN 伝播・dyad 損失・gate 初期化）は下流の CombineEFOMoE 側にある。

## 7. 設計上の判断（要約）

- 新規語彙を最小化し EFO/PROV-O/SKOS の標準へ接続 → 「独自オントロジーの再発明」批判を避ける。
- 理論を TBox に固定し、強度は instance（occurrence）側に置く → 不変の構造と可変の観測を分離、
  dyad は「規則で導く」ので provenance が自然に付く。
- 検証を最初から組み込む（SHACL + CQ + OWL-RL）→ 正しさを主張でなく**形式検証**で示す。
- 詳しい限界・査読対策は `MODELING_DECISIONS.md`。
