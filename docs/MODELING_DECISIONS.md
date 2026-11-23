# 設計判断と限界 (MODELING_DECISIONS)

> オントロジーの設計判断・既知の限界・想定される査読/審査での指摘への先回りをまとめる。
> 「なぜこう作ったか」は `ONTOLOGY_CONSTRUCTION.md`。作成 2026-07-03。

このオントロジーの価値は「F1 で勝つ」ことではなく、**理論を検証可能な形で形式化し、注入知識の
影響を instance-level の provenance として外部化する**点にある。以下はその立場を弱めうる論点を
自分から明示し、対応（修正済み / 意図的判断 / future work）を切り分けたもの。

---

## A. 語彙再利用の厳密性

| # | 論点 | 状態 | 対応 |
|---|------|------|------|
| A-3 | `owl:imports` が検証時に dereference されず、EFO 互換が「共有 IRI レベル」に留まる | **解決済** | EFO スキーマ（EmoCore/BasicEmotions）を `efo-src/` にローカル取得し（2026-11-15 以降はリポに含めず上流の固定コミットから取得、sha256 照合）、`validate.py:check_efo_alignment` が**ローカル解決した融合グラフ**で用語の解決可否を検証（EFO-align 7/9）。互換が vocabulary-level であることも TTL コメントに明記。 |
| A-4 | `plu:` が `example.org` の placeholder | **解決済** | `https://w3id.org/efo-plutchik#` へ移行。versionIRI・dcterms メタデータ・vann prefix も付与。w3id への**実登録**は運用 backlog（`PROGRESS.md` B-4）。 |
| A-1 | `emo:EmotionSituation` を EmoCore の名前空間に新規宣言している（他人の名前空間に term を鋳造） | **既知・要判断** | 現状は EFO occurrence へ橋渡しする**意図的な local declaration**として `skos:definition` に明記し、validator が `local-bridge (1)` として可視化。よりクリーンには `plu:EmotionSituation` へ改名（`PROGRESS.md` A-1）。 |
| A-2 | `plu:isManifestationOf rdfs:subPropertyOf be:isManifestationOf` の上位が EFO **スキーマに未定義**（FER/CREMA などデータ KG 側の語彙） | **既知・要判断** | validator が `unresolved (1)` として明示。dangling superproperty を独自定義に切替えるか実在プロパティへ張替える（`PROGRESS.md` A-2）。 |

> **要点**: 「EFO 互換」は reasoner による融合検証まで含めて機械チェックしており（A-3）、
> 未解決の 2 用語は**隠さず validator が数え上げる**。これが「非空虚な検証」の一部。

補足: 基本感情→EFO-BE(Ekman) の対応に `skos:closeMatch` を用いている。SKOS mapping は本来
`skos:Concept` 向けで、ここでは OWL NamedIndividual に付与している点は緩い運用（相互運用上の
実害はないが、厳密には punning）。

## B. 理論の網羅範囲（スコープ）

- **B-1（v0.5.0 で更新）dyad 24・強度の変種 16 をコアに含める**: v0.4.0 は「注入経路で実際に使う構造」に
  絞って 8 基本 + 8 primary dyad に限定していた。v0.5.0（2026-11-14、CombineEFOMoE #33）で、理論の網羅性と
  強度つきラベル写像のために secondary / tertiary dyad と強度の変種を加えた（下の E 節）。**注入グラフ
  （`build_graph.py`）は v0.4.0 と同じ 16 ノードのまま**で、既存の実験を変えない。v0.4.0 は git tag `v0.4.0`。
- **B-2 dyad 強度 = `min`・閾値 3 種は operationalization**: Plutchik 自身は数値合成規則を
  定めていない。「弱い方の感情が dyad を律速する」という直観に基づく**本研究の設計判断**であり、
  理論の含意として提示しない。閾値 0.3/0.5/0.7 を並置して感度を CQ-6 で開示している。

## C. オントロジーはモデルをどれだけ駆動しているか

想定質問:「モデルへ渡すのは 16 ノードの隣接行列だけ。手描きグラフでも作れる。**オントロジーで
ある必然性は?**」

- 事実として、ML 注入（別リポの `build_graph.py` 由来の adjacency）が使うのは静的な隣接構造のみで、
  occurrence・intensity・min 集約・SHACL といった richness は**provenance KG の検証**に使われる。
- したがって本モジュールの価値は**注入の accuracy 寄与ではなく、traceability と形式検証**にある:
  「どの注入知識がどの予測に効いたか」を PROV-O KG 化し、dyad へ接地しない知識（例: 共起のみの
  cooccur）を SHACL が **conforms=False で正しく棄却**する——この**非空虚な検証**は素の隣接行列
  では成立しない。オントロジーである必然性はこの検証可能性に宿る。

> この C の問いは論文本文で**先回りして明示的に answer** しておくと守りが固い
> （新規性 = verifiable provenance of knowledge influence）。

## D. 参考: 検証で担保していること
- 理論構造（dyad 構成・対極）の SHACL 適合、`BasicEmotion ⊓ CompoundEmotion = ∅` の OWL-RL 一貫性。
- 全 40 型付き term の label + 定義（FAIR Reusability）。
- 推論（dyad materialization）→ SHACL → 7 CQ の一気通貫、CQ-7 で provenance 完全性 = 0 違反。


## E. v0.5.0 の設計判断（2026-11-14、CombineEFOMoE Issue #33）

ユーザーとの合意: 目的は F1・provenance・オントロジーの質・理論の網羅性の 4 つ。正本はこのリポ。v0.4.0 は残す。

- **E-1 感情は個体のまま**: EmoCore / EFO の流儀に合わせ、強度・dyad・wheel の幾何を個体間の関係で書く。
  クラスにする案（MFOEM の流儀）は、注入グラフへの変換と既存 provenance KG の互換性を崩すので採らない。
- **E-2 強度の変種**: `plu:IntensityVariant`（基本感情・複合感情と互いに素）と `plu:intensityOf`（functional）、
  段階は `plu:IntensityLevel` の 3 個体（`intensityRank` 1/2/3）。基本感情そのものを medium とし、変種は low / high。
  名前と配置は Plutchik (2001) の wheel（内側 = high、外側 = low）。日本語名は本リポの訳で、定訳ではない。
- **E-3 dyad 24**: primary / secondary / tertiary を互いに素なクラスにし、`plu:wheelPosition` から計算する円周距離
  （1/2/3）とクラスの一致、「対極でない 28−4 = 24 組それぞれにちょうど 1 つの dyad」を SHACL で検証する。
  `infer_dyads.rq` は 24 dyad すべてで事例を作る（min の規則だけ、#15）。
- **E-4 VAD は語彙だけ**: `plu:VADReading`（prov:Entity）に値・引いた語・辞書（`prov:wasDerivedFrom`）を持たせる。
  NRC VAD は研究・非商用の条件で CC BY 4.0 と合わないので、値は `build_vad.py` で手元に別ファイルとして作り、同梱しない。
  `plu:vadDominance` は三次 dyad の `plu:Dominance` と別物（名前の衝突を定義文に明記）。
- **E-5 ラベル写像を 2 方式で**: `map:LimCheong2024`（成分写像、再現用、監査で既知の Violation 1・Warning 2）と
  `map:Plutchik2001Names`（概念写像）。後者は「名前が Plutchik (2001) の語と一致 → skos:closeMatch」
  「GoEmotions で一致しないものは Demszky et al. (2020) の Ekman 対応 → 対応する基本感情へ skos:broadMatch」
  「どちらでもない → 写さない（理由つき）」。exactMatch は使わない（データセット側の定義が Plutchik の概念と同一だとは確認していない）。
  名前と Demszky の対応が食い違う admiration / disapproval は名前を優先し、basis に書く。
  `plutchik-mappings.ttl` は `build_mappings.py` の生成物（テストで一致を確認）。
- **E-6 バイリンガル**: 全 term に `@en` / `@ja` の label と定義（doc SHACL で両言語を必須化、94/94）。
- **E-7 限界**: 強度の変種・二次 / 三次 dyad の名前は Plutchik (2001) の図に基づき、心理学的な妥当性を本モジュールが
  主張するものではない。写像の closeMatch は名前の一致に基づく操作的な判断で、データセットの注釈者の意図とは別。
