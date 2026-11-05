# 収録範囲の網羅性監査（2026-11-05）

本文書は，Image Coding Map の既存44ノードに対して，定義した検索条件の下で未収録の重要研究を調査した結果である．調査は以下の条件に対する結果であり，対象分野の全論文を網羅したことを意味しない．

## 1. 調査の条件

| 項目 | 内容 |
| :--- | :--- |
| 検索日 | 2026-11-05 |
| 対象 | OpenAlex（関連度順・被引用数順，各50件），arXiv（新しい順，各40件），Semantic Scholar（関連度順，各50件），Crossref（DOI の解決） |
| 期間 | OpenAlex・Semantic Scholar は 2015年以降．arXiv は新しい順の上位40件．スノーボーリングの参考文献は期間を限定しない |
| 検索式 | 8課題（LIC，生成・拡散型，SSCC，アナログ型 DeepJSCC，デジタル型 DeepJSCC，拡散型 JSCC，ビット誤り耐性，パケット損失耐性）について計22式．一覧は `search_tables.md` |
| スノーボーリング | DeepJSCC（Bourtsoulatze），NECST，Scale Hyperprior，DDCM，Robust Turbo-DDCM，BlindSC，NTSCC の参考文献（全件）と被引用文献（被引用数の多い順に上位200件） |
| 本文の参考文献 | OpenAlex に参考文献の登録が無い Robust Turbo-DDCM について，本文の参考文献リストの8件をタイトルで照合 |
| 優先確認 | order_004 の7件を arXiv・Crossref・OpenAlex で照合 |

検索は88件のうち64件が成功した．Semantic Scholar は未認証の API がレート制限（HTTP 429）を返したため22件すべてが失敗し，結果に含まれていない．OpenAlex の2件（関連度順・被引用数順の各1件）も再試行後に失敗した．取得した記録は3,621件であり，DOI・arXiv ID・正規化したタイトルで照合して2,320件に統合した（649組を統合）．

## 2. 検索の再現率の目安

既存ノードのうち書誌情報を持つ39件について，今回の検索・スノーボーリングで再発見できたかを調べた．32件が再発見された．検索期間（2015年以降）に入る31件に限ると29件（94%）であり，再発見できなかったのは DDCM（タイトル "Compressed Image Generation with Denoising Diffusion Codebook Models"）と BlindSC（"Blind Training for Channel-Adaptive Digital Semantic Communications"）である．
いずれもタイトルに「compression」「joint source-channel coding」等の検索語を含まないため，同様の命名の未収録論文は今回の検索式では拾えていない可能性がある．

## 3. 優先確認論文の照合結果

| 名称 | 識別子（order） | 照合結果 | 初出 | 正式掲載 | 判断 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| BitFlat | arXiv:2610.25682 | arXiv・OpenAlex で実在を確認 | 2026（arXiv） | 未確認（プレプリント） | 追加推奨（A） |
| DiffJSCC | arXiv:2404.17736 | arXiv・OpenAlex で確認 | 2024（arXiv） | IEEE TMLCN 2025 | 追加推奨（A） |
| SGD-JSCC | arXiv:2501.01138 | arXiv・OpenAlex で確認 | 2025（arXiv） | IEEE TWC 2025 | 追加推奨（A） |
| CDDM | DOI:10.1109/TWC.2024.3379244 | Crossref で確認．検索結果で arXiv:2309.08895 と同一論文として統合 | 2023（arXiv） | IEEE TWC 2024 | 追加推奨（A） |
| ResiComp | DOI:10.1109/TCSVT.2025.3539747 | Crossref・OpenAlex で確認（arXiv:2502.10812） | 2025 | IEEE TCSVT 2025 | 追加推奨（A） |
| Towards Loss-Resilient Image Coding for Unstable Satellite Networks | タイトル | OpenAlex で確認（DOI 10.1609/aaai.v39i12.33363，arXiv:2501.11263） | 2025 | AAAI 2025 | 追加推奨（A） |
| A Survey on Robust Deep JSCC | arXiv:2604.04413 | arXiv で確認．OpenAlex ではタイトル完全一致なし | 2026（arXiv） | 未確認 | 参照のみ（サーベイ） |

7件すべての実在を確認した．実在の確認は，既存ノードからの派生を意味しない．既存ノードとの関係候補は `candidates.json` の `decision.relations` に，根拠（要旨の記述）と確度を付けて記録した．

## 4. 候補の分類

関連性はタイトル・要旨のキーワードによる一次判定（0〜3）であり，関連性0（画像の符号化・伝送に該当しない，または医用画像・音声等の対象外）の1,426件は候補から除いた．残る862件に優先度を付けた．

| 優先度 | 基準 | 件数 |
| :--- | :--- | ---: |
| A | 関連性3かつ，被引用50以上・3件以上の検索で出現・既存ノード2件以上と引用関係・優先確認論文のいずれか | 100 |
| B | 関連性2以上で A に該当しない | 626 |
| C | 関連性1 | 136 |

このうち45件を人手で判断した（`decisions.json`）．残る817件は一次判定のみであり，採否は未判断である．

| 判断 | 件数 | 内容 |
| :--- | ---: | :--- |
| 追加推奨（recommend_add） | 18 | 既存の系譜の欠落を埋める，または現在のマップに無い課題を代表する．`survey/library.json` に候補として登録した |
| 検討（consider） | 14 | 関連は高いが，既存ノードとの差分や範囲の判断に本文の確認が必要 |
| 会議版（conference_version） | 2 | 既存ノード（DeepJSCC-f，DeepJSCC-l）の会議版と考えられるもの．同一論文かは要確認 |
| 参照のみ（reference_only） | 6 | サーベイ・理論の論文．手法のノードではなく，探索の起点や位置付けに用いる |
| 対象外（out_of_scope） | 5 | タスク指向（VQA，検索），モデル圧縮など，画像の再構成を対象としないもの |

追加推奨の18件は以下の通りである（被引用は OpenAlex の値）．

| 分野 | 論文（初出年） | 主な理由 |
| :--- | :--- | :--- |
| LIC | Context-adaptive Entropy Model（Lee ら，2018） | エントロピーモデルの系譜（Minnen 2018 と並ぶ）の欠落．被引用344 |
| LIC（パケット損失） | ResiComp（2025），Loss-Resilient Image Coding for Unstable Satellite Networks（2025） | パケット損失耐性の課題が現在のマップに無い |
| LIC＋SSCC（ビット誤り） | Deep Learning-Based Image Compression for Wireless Communications（Naseri ら，2024） | ハイパープライアのビット誤りへの脆弱性を評価．Robust Turbo-DDCM の参考文献 |
| 生成型 | GAN for Extreme Learned Image Compression（Agustsson ら，2018） | HiFiC 以前の生成型圧縮．被引用597 |
| 生成型 | Lossy Compression with Gaussian Diffusion（Theis ら，2022），Lossy Compression with Pretrained Diffusion Models（2025） | 逆チャネル符号化に基づく拡散型圧縮（DiffC）の系統．Robust Turbo-DDCM の評価対象 |
| 生成型（ビット誤り） | BitFlat（2026） | 拡散型圧縮のビット誤り耐性．Robust Turbo-DDCM と共通課題 |
| アナログ型 DeepJSCC | WITT（2022），OFDM-Guided DeepJSCC（2021），DeepJSCC-MIMO（2023），適応レート制御の DeepJSCC（2021） | Transformer・OFDM・MIMO・レート適応の系統が現在のマップに無い |
| アナログ型 DeepJSCC＋生成型 | Generative JSCC（Erdemir ら，2022），CDDM（2023），DiffJSCC（2024），SGD-JSCC（2025） | 生成モデル・拡散モデルと DeepJSCC の重なりが現在のマップに無い |
| デジタル型 DeepJSCC | VQ-DeepSC（2022），Channel-Adaptive Digital Semantic Communications の JSCC（2023） | ベクトル量子化・適応変調によるデジタル型の系統．後者は BlindSC の参考文献 |

## 5. 網羅できていない分野の分析

既存44ノードと候補の分布を比べると，以下の分野で収録が不足している．件数は一次判定の候補（862件）に対する課題の該当数であり，重複して数える．

| 課題 | 既存ノード | 候補（うち A） | 分析 |
| :--- | ---: | ---: | :--- |
| アナログ型 DeepJSCC | 6 | 415（83） | 最も候補が多い．OFDM・MIMO・フェージング，レート・SNR 適応，Transformer の骨格，マルチユーザなどの系統が未収録である．意味通信（semantic communication）の文脈の論文が多く，画像の再構成を対象とするものとタスク指向のものの区別が必要である |
| デジタル型 DeepJSCC | 8 | 210（29） | ベクトル量子化（VQ-DeepSC 等），適応変調，OFDM のデジタル型が未収録である |
| 拡散・生成型と JSCC の重なり | 0 | 生成型 244（27） | 現在のマップでは生成型と DeepJSCC の両方に属するノードが無い．CDDM，DiffJSCC，SGD-JSCC，Generative JSCC 等が該当する |
| パケット損失耐性 | 0 | 34（11） | 課題として未収録である．ResiComp，衛星網向けの LIC のほか，2026年のプレプリントが多い |
| ビット誤り耐性 | 4（Robust Turbo-DDCM，BFR-CAE，IABF，BlindSC のタグ） | 246（50） | 拡散型（BitFlat）と，学習型圧縮の誤り耐性の評価（Naseri ら）が未収録である．キーワード "robust" が広く一致するため候補数は過大である |
| LIC | 15 | 208（14） | 主要な系譜は収録済みであるが，Lee らの Context-adaptive モデル，可変レート，Transformer のエントロピーモデル（Entroformer，MLIC）が未収録である |
| SSCC | 4 | 323（80） | 候補の多くは比較対象として LDPC・BPG に言及する DeepJSCC の論文であり，SSCC 自体の新しい構成例は少ない．D²-JSCC が比較に用いた BPG＋Polar 符号は未登録である |
| 従来型・通信路符号 | 7・9 | 調査対象外 | 検索期間を2015年以降としたため，今回の調査では評価していない |

年別では候補の初出年が2024年138件，2025年159件，2026年226件と近年に集中している．arXiv の新しい順の検索の影響を含むため，近年の論文の数が過大に見えている．2026年の論文の多くは被引用が無く，評価が定まっていない．

## 6. 調査の限界

- Semantic Scholar の検索結果を含まない（API キーが無く，全件がレート制限で失敗した）．
- 被引用文献は起点ごとに被引用数の多い順の上位200件に限っており，DeepJSCC（総数1,492件），Scale Hyperprior（1,555件），NTSCC（365件）では一部のみを確認した．
- DDCM と Robust Turbo-DDCM は OpenAlex に参考文献の登録が無く，参考文献の追跡は Robust Turbo-DDCM の本文の8件の照合に留まる．
- 関連性はキーワードによる一次判定であり，人手で判断したのは45件である．関係候補は要旨の記述のみを根拠とし，派生関係（`derived_from`，`builds_on`）の候補はすべて本文の確認を要する．
- 映像（video）の論文は対象外とはしていないが，検索式は画像を対象としている．
