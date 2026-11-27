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

## F. 0.6.0 の設計判断（2026-11-27、CombineEFOMoE Issue #85）

ユーザーとの合意: 写像を 12 データセットに広げる。語形の違いは明示した表に載るものだけ認める。方式ごとに対象のデータセットを宣言する。
版は、パッケージと写像のモジュールを 0.6.0 とし、コアのオントロジー（`efo-plutchik.ttl`）は中身が変わらないので 0.5.0 のまま。

- **F-1 何を足したか**: `map:Plutchik2001Names` の対象に 10 データセットを足した（EmpatheticDialogues、crowd-enVENT、GoodNewsEveryone、
  BRIGHTER の英語、XED、SSEC、enISEAR、DailyDialog、SemEval-2018 EI-oc、Electoral Tweets。ラベル 119 個）。
  扱うのはラベルの名前と出典だけで、データの本文は入れない。利用条件は記録しない（配布元を `dcterms:source` で指す）。
- **F-2 語形の規則**: ラベルが形容詞・分詞の形（annoyed、terrified など）のとき、`map:NameVariantRule` の 16 組に載るものだけを
  `skos:closeMatch` にする（`map:nameVariantOf` に元の語）。表に無い語形と類義語（afraid、furious、jealous、happiness など）は写さない。
  SHACL は、記録の語形が表の組と一致することを検査する。表そのものが妥当かは、検査の対象ではない（人が読んで確かめる）。
- **F-3 写さないラベル**: 複数の語を "or" でつないだラベル（Electoral Tweets の 7 個）、限定のついたラベル（negative / positive surprise）、
  感情でない区分（neutral、no-emotion）、残りをまとめる区分（DailyDialog の no emotion）。理由を `map:basis` に書く。
  同じ文字列でも、GoEmotions では Ekman の対応で `skos:broadMatch` になり、追加のデータセットでは写さないものがある
  （disappointment、relief、caring）。Ekman の対応の出典が GoEmotions だけにあるため。
- **F-4 方式の対象**: `map:coversDataset` で、方式が対象とするデータセットを宣言する。`map:LimCheong2024` は SemEval-2018 E-c と
  GoEmotions だけ。網羅の検査は「対象のデータセットのラベルは、その方式に記録を 1 つ持つ。対象でなければ持たない」。
- **F-5 ラベルの付け方**: `map:labellingMethod` に、読み手の注釈（`map:ReaderAnnotated`）・書き手の選択（`map:WriterChosen`）・
  得点の区切り（`map:ScoreThresholded`）を記録する。CQ-M6 / M7 で、Plutchik の 48 語のうち、名前か語形で対応するラベルを持つ語を数える:
  どれかのデータセットにある 29、読み手の注釈である 23、書き手の選択だけ 6（Anxiety・Apprehension・Boredom・Hope・Sentimentality・Terror）、
  どこにも無い 19（強度の変種 7、dyad 12）。
- **F-6 強度のクラスは変種に写さない**: SemEval-2018 EI-oc の 4 段階は、人手の得点を区切った帯で、「annoyance」や「rage」という語を
  人が選んだものではない。ラベルは anger / fear / joy / sadness の 4 つとして基本感情に写し、強度の尺度は `map:intensityScale` に書く
  （CombineEFOMoE #81・#82 の結果に基づく）。
- **F-7 限界**: (1) closeMatch は名前（か表に載る語形）の一致で、概念が同じであることは示さない。特に dyad の名前
  （pride = anger + joy、guilt = joy + fear、shame、sentimentality、anxiety）は、日常語の意味と Plutchik の成分が合うとは限らない。
  dyad の成分まで降ろして使うときは注意する。(2) ラベルの名前は、論文・質問票・配布物の説明で確認した。データファイルの中の値まで
  確認したのは EI-oc と Electoral Tweets だけ（`map:labelsCheckedIn` に範囲を書く）。Electoral Tweets は 1 つの選択肢が、データでは
  空白 2 つで書かれている。(3) 「読み手の注釈で 23 語」のうち、Acceptance・Amazement・Vigilance は Electoral Tweets だけ、
  Curiosity・Disapproval・Grief・Remorse は GoEmotions だけが根拠。(4) どこにも無い 19 語のうち Serenity・Interest などは、
  Electoral Tweets の複合のラベルの中に語としては現れる。(5) GoodNewsEveryone の最初の注釈の段階にある「No emotion」は、
  15 個の区分に入っていないので一覧に無い。件数をデータセットの間で比べるときは注意する。
- **F-8 監査**: CombineEFOMoE #85 の独立監査で、ラベルの一覧 10 個と一次ソースの照合、既存の 2 データセットの記録が 1 つも変わらないこと
  （v0.5.0 の 875 triple がすべて残る）、下流の利用箇所の結果が同じことを確認した。監査が見つけた SHACL の抜け道（自己申告の語形、
  体系に属さない概念、記録とラベル概念の食い違い）は塞ぎ、テストに入れた。
- **F-9 0.6.1 の訂正（2026-11-27、CombineEFOMoE #88 のデータの入手で判明）**: GoodNewsEveryone のデータのラベルは、論文の名前
  （love、pessimism、optimism、negative surprise、positive surprise）ではなく、`love_including_like`・
  `negative_anticipation_including_pessimism`・`positive_anticipation_including_optimism`・`negative_surprise`・`positive_surprise` だった。
  `map:sourceLabel` は「データセットに書かれたとおり」なので、データの綴りに直した。前の 3 つは複数の区分をまとめた名前なので、
  F-3 の規則どおり写さない（0.6.0 では love / pessimism / optimism を closeMatch にしていた）。GoodNewsEveryone の closeMatch は 13 → 10、
  写さないラベルは 2 → 5。Love・Optimism は SemEval-2018 E-c と GoEmotions、Pessimism は SemEval-2018 E-c に残る。
  論文の名前だけでラベルを決めると、こういう食い違いを見逃す。

## G. 0.7.0 の設計判断: 転移の証拠のモジュール（2026-11-27、CombineEFOMoE Issue #88・#90）

- **G-1 写像は変えず、証拠を別のモジュールにする**: 名前による対応（`skos:closeMatch`）は、名前が一致するという事実の記録で、0.6.1 のまま残す。転移の結果は、それとは別の種類の情報（ある設定での実測）なので、`plutchik-mapping-evidence.ttl`（名前空間 `…/mapping/evidence#`）に分けた。写像のファイルの hash は変わらない。
- **G-2 証拠は対応の組ごと**: 転移は 2 つのデータセットの間の量なので、1 つの記録の性質としては書けない。証拠 1 件は、学習側の記録と評価側の記録の順序つきの組に付く（A → B と B → A は別）。記録ごとの要約は CQ-T2・T3 が作る。
- **G-3 `matchType` を弱めない**: 移らなかった対応を `skos:relatedMatch` に下げることはしない。移らないことは、意味が違うことを示さない（粒度、頻度、文の種類、学習の件数でも起きる）。たとえば GoEmotions の disgust は、同じデータセットの annoyance・anger に負けるが、これは近いラベルがあることの効果である。
- **G-4 新しい判定を作らない**: 証拠は、数値（matched の AUC、名前の合うラベル以外で最良のラベルの AUC、順位の seed の数、陽性の数、native の AUC）と、もとの実験の事前登録の判定をそのまま持つ。事前登録の判定の規則には絶対水準の下限が無く、matched が 0.6 未満でも Partial になる組がある（CQ-T5 が一覧にする）。読むときは、判定だけでなく `matchedAuc` と `bestOtherAuc` を比べる。
- **G-5 限界は調査のノードに書く**: 設定（roberta-base、学習は最大 8,000 件、seed 5、英語）と既知の限界は、`evd:CrossDatasetTransfer2026` の `skos:scopeNote` に書き、SHACL で必須にした。別の設定の実験を足すときは、別の調査のノードにする。
- **G-6 データは含めない**: 入力の CSV は数値だけで、データセットの文は含まない。再配布できないデータセット（SemEval-2018 など）の文は、このリポジトリには入らない。
- **G-7 証拠の無い対応**: 名前による対応 のうち 23 個は、相手が無いか、実験に入れなかったデータセット（ElectoralTweets、SemEval-2018 EI-oc）のもので、証拠が無い（CQ-T4）。証拠が無いことは、支持も不支持も意味しない。
- **G-8 主な結果**（実験の側の事後の分析。詳細は CombineEFOMoE の `docs/ABLATION_RESULTS.md`）: 基本感情の 486 組では、名前の合うラベルが最良のほかのラベルを平均 +0.080 上回る（395 組）。基本感情でない語の 43 組では +0.009 で、0 と区別できない（データセットの組を標本にした bootstrap の 95% 区間が [−0.017, +0.034]）。
- **G-9 0.7.1 の訂正（独立監査）**:
  - `bestOtherAuc` は、seed ごとの最大値の平均である（平均の最大値ではない。最良のラベルは seed ごとに替わりうる）。定義文をそう書き直した。
  - AUC は小数 6 桁に丸めた値。0.7.0 の 4 桁では、名前の合うラベルと最良のほかのラベルが同点になる組が 1 つあり、CQ-T1 の数が実験の側の表と 1 つずれた。
  - 0.7.0 の制約は、`rdf:type` を持たないノードを見ていなかった。証拠の述語を 1 つでも持つノードを検査の対象にした。
  - 表（CSV）を作る手順が、どのリポジトリにも無かった。CombineEFOMoE に書き出しのスクリプトを置き、もとの json とスクリプトの sha256 を `.source.json` と調査のノード（`dcterms:source`）に記録した。もとの json は実験の側の `outputs/`（git の管理外）にあるので、照合できるのは、それを持つ環境だけである。
  - 事前登録の判定は 5 seed でだけ定義されている。`seedCount` を 5 に固定した。
- **G-10 残る限界**:
  - 学習の陽性が少なくて判断できない組（GoEmotions の pride、DailyDialog の fear が学習側）に、機械で読める印は付けていない。学習側の陽性の数が、もとの json に無いためである。調査のノードの注記を読む必要がある。
  - 証拠どうしの数値の整合（Supported なのに matched が bestOther より低い、など）は検査しない。順位と AUC は別々に記録された値で、seed ごとの値は持たない。
  - 版の固定: 写像のオントロジーには `owl:versionIRI` が無く、証拠が写像の 0.6.1 に対するものであることは、調査のノードの `dcterms:source` の文字列と、下流の manifest でしか分からない。
  - PROV-O・DQV・ML Schema への対応づけはしていない（独自のクラス）。
- **G-11 0.8.0: 再実行を 2 つめの調査として足す（CombineEFOMoE #91・#92）**:
  - 1 つめの調査（#88）は、まれなラベルを学習側にした組を NotSupported / Partial と記録していた。再実行（#91）で学習の陽性を 11〜24 件から 111〜124 件にすると、DailyDialog の fear は 8 単位すべてで Supported になった。GoEmotions の pride は 3 単位のうち Supported 2・Mixed 1 で、最良のほかのラベルとの差は小さい（+0.017）。1 つめの判定は、学習の件数を反映していた可能性が高い（学習の行が同じ学習元では差の変化が 0.016 程度なので。ただし設計上、seed の違いとは分けられない）。
  - 1 つめの証拠は消さない（実測の記録として残す）。調査のノードの注記に「再実行と合わせて読む」と書き、CQ-T6 が判定の食い違う 61 組を一覧にする。G-10 の 1 点目（学習側の陽性の数が無い）は、再実行の証拠では `evd:sourceTrainingPositives` で解消した。
  - 判定の規則は調査ごとに違う。再実行の規則は、絶対水準の下限（matched ≥ 0.6）と、名前の合うラベルが最良のほかのラベルを上回るか、を使う（Inconclusive / Supported / NotSupported / Mixed）。制約は調査ごとに規則を検査し、規則を知らない調査の証拠は弾く。新しい調査を足すときは、制約に規則を足す必要がある。
  - 再実行は独立な追試ではない（同じ 10 データセット、同じモデル。6 つの学習元は学習の行が同じ、3 つの評価先は評価行が同じ）。2 つの調査の一致を、独立な再現として数えない。
  - 再実行の主な結果（実験の側。区間はデータセットの組を標本にした bootstrap の 95%）: 基本感情の 486 単位で、名前の合うラベルは最良のほかのラベルを平均 +0.085 [+0.071, +0.101] 上回る。基本感情でない語の 46 単位では +0.015 [−0.009, +0.043]。後者は学習元に依存し、負ける相手の多くは同じ基本感情を共有する語（guilt と shame、pride と joy）である。
- **G-12 0.8.1 の訂正（独立監査）**:
  - 再実行の注記の 1 つが数値と合わなかった（「GoEmotions か GoodNewsEveryone が学習元だと、名前の合うラベルは最良のほかのラベルを上回らない」）。正しくは、基本感情でない語に限り、この 2 つを合わせた 18 単位で −0.031。GoodNewsEveryone の基本感情は +0.025 で正。書き直した。
  - 「上書きする」「移った」は言い過ぎだった。再実行は独立でなく、seed の違いと分けられない。pride は fear ほど明確でない。注記と README を「合わせて読む」「可能性が高い」に直した。
  - CQ-T1〜T3 は、再実行の判定（Mixed・Inconclusive）を列に持たなかった。列を足した。CQ-T5 は調査を返し、「NotSupported なのに matched が 0.8 以上」（水準は高いが近いラベルに負けた組）も一覧にする。
  - 型の無いノードの検査の対象に、数値の述語を全部足した。
  - 再実行の証拠には評価行の数（`evd:targetRows`）が無い（実験の側の出力に無いため）。評価側の陽性が行数より少ないことは、再実行では検査されない。
  - G-10 の 2 点目（数値どうしの整合は検査しない）は、再実行では、判定の規則の検査が matched・最良のほかのラベル・学習の陽性の数を使うので、一部解消している。
- **G-13 0.8.2 の訂正（0.8.1 に対する独立監査）**:
  - データ（1,061 件の値・件数・判定・sha256・再生成）は、実験の生の出力からの再計算と不一致 0 だった。直したのは制約の穴と言い回しである。
  - 再実行の証拠は `evd:rankThreeSeeds` を持たないので、`evd:rankOneSeeds` に上限が無かった（99 でも通った）。seed の数と直接比べる制約を足した。
  - seed の数と AUC の矛盾を弾く制約を足した（全 seed で 1 位なら matched ≥ 最良のほか、どの seed でも 1 位でないなら matched < 最良のほか。最良のほかは seed ごとの最大の平均なので、この 2 つは定義から従う）。中間の数（1〜4 seed）と AUC の関係は、定義からは決まらないので検査しない。
  - 評価行の数がある証拠（1 つめの調査）で、陰性が 20 以上あることを検査する。
  - 1 つめの調査の注記の「all 8 pairs … ranked first」は、正しくは「8 組とも Supported（5 seed 中 4 以上で 1 位）」。学習の陽性の数は、fear が 11〜16 → 124、pride が 16〜24 → 111 と、ラベルごとに書いた。README の「再実行を代わりに読む」は G-12 の訂正が漏れていたので、「合わせて読む」に直した。
  - 残る限界: 証拠が指す写像の記録が、実験に入ったデータセットのものかは検査しない（同じ語・別のデータセット・closeMatch であれば通る）。証拠の IRI と中身の対応も検査しない。再実行の評価側の陽性の上限は無い（G-12）。G-10 の 2 点目の例（Supported なのに matched が最良のほかより低い）は仮の例で、実データには無い（0.8.2 では、全 seed で 1 位の場合に限り制約が弾く）。
  - 注記と `dcterms:relation` があること自体は、制約ではなくテストが見ている。

