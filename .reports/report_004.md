# report_004：論文収録範囲の網羅性監査

本レポートは，order_004 に基づき，Image Coding Map の既存44ノードに対して未収録の重要研究を調査した結果をまとめたものである．調査は定義した検索条件・期間に対する結果であり，全論文を網羅したことを主張するものではない．候補は本番データ（`data/nodes/`）に追加していない．詳細な分析は `audit/coverage_report.md` に記載した．

## 1. 実施内容

| 手順 | 内容 | 成果物 |
| :--- | :--- | :--- |
| 1 | 既存44ノードの ID・タイトル・DOI・arXiv ID・初出年・正式掲載を整理した | `audit/existing_inventory.csv` |
| 2 | OpenAlex（関連度順・被引用数順），arXiv（新しい順），Semantic Scholar を22の検索式で横断検索した | `audit/search_log.json`，`audit/search_tables.md`，`audit/raw/` |
| 3 | 主要7ノードの参考文献・被引用文献を OpenAlex で追跡し，Robust Turbo-DDCM の本文の参考文献8件を照合した | 同上 |
| 4 | 優先確認論文7件を arXiv・Crossref・OpenAlex で照合した | `audit/priority_check.json` |
| 5 | DOI・arXiv ID・正規化タイトルで重複を統合し，既存ノードと照合した | `audit/dedup_log.json` |
| 6 | キーワードで関連性を一次判定して優先度（A／B／C）を付け，45件を人手で判断した | `audit/candidates.json`，`audit/candidates.csv`，`audit/decisions.json` |
| 7 | 分野ごとの不足を分析した | `audit/coverage_report.md`，`audit/coverage_stats.json` |

プログラムは `programs/audit_coverage/collect.py`（収集）と `programs/audit_coverage/build_candidates.py`（統合・判定）である．追加推奨の18件は `surveykit.py add` で `survey/library.json` に候補（candidate）として登録した．

## 2. 検索の結果

検索日は 2026-11-05 である．検索は88件のうち64件が成功し，2,687件を取得した．スノーボーリングと照合を含めて3,621件の記録を得て，重複を統合して2,320件とした．

| 対象 | 成功／実行 | 備考 |
| :--- | :--- | :--- |
| OpenAlex（関連度順） | 21／22 | 2015年以降，各50件 |
| OpenAlex（被引用数順） | 21／22 | 2015年以降，各50件 |
| arXiv（新しい順） | 22／22 | 各40件 |
| Semantic Scholar | 0／22 | API キーが無く，全件がレート制限（HTTP 429） |
| スノーボーリング | 7／7 | 被引用文献は被引用数の多い順に上位200件 |

既存ノードの再発見率を検索の再現率の目安とした．検索期間（2015年以降）に入る既存31件のうち29件（94%）を再発見した．DDCM と BlindSC は，タイトルに検索語を含まないため再発見できなかった．

## 3. 優先確認論文

order_004 の7件はすべて実在を確認した．CDDM は DOI（IEEE TWC 2024）と arXiv:2309.08895 を同一論文として統合した．A Survey on Robust Deep JSCC は手法ではないため参照のみとし，その他の6件を追加推奨とした．実在の確認は既存手法からの派生を意味しない．派生関係の候補は全て要本文確認とした．

## 4. 候補の分類と判断

既存ノードと一致した32件と，関連性0の1,426件を除き，862件を候補とした（A 100件，B 626件，C 136件）．人手で判断した45件の内訳は，追加推奨18件，検討14件，会議版2件，参照のみ6件，対象外5件である．残る817件は一次判定のみである．
追加推奨の18件は，LIC の Context-adaptive エントロピーモデル（Lee ら），パケット損失耐性の LIC（ResiComp，衛星網向け），学習型圧縮のビット誤りの評価（Naseri ら），生成型圧縮（Agustsson らの GAN，Theis らの Gaussian Diffusion，DiffC の実装，BitFlat），アナログ型 DeepJSCC（WITT，OFDM-Guided，DeepJSCC-MIMO，適応レート制御），生成型 JSCC（Generative JSCC，CDDM，DiffJSCC，SGD-JSCC），デジタル型 DeepJSCC（VQ-DeepSC，チャネル適応のデジタル型 JSCC）である．

既存ノードとの関係候補は，要旨に比較対象として明示された `compared_with`（例: OFDM-Guided DeepJSCC → BPG＋LDPC，VQ-DeepSC → BPG・DeepJSCC，ResiComp → VVC（VTM＋FEC））と，要本文確認の `builds_on`・`derived_from`・`related` に分けて記録した．`derived_from` の候補は SGD-JSCC → DeepJSCC の1件のみであり，要旨の "advances the DeepJSCC framework" が特定の論文を指すかは本文で確認する必要がある．
DeepJSCC-f と DeepJSCC-l については，会議版と考えられる論文（ICASSP 2020，SPAWC 2019）が見つかった．同一論文として扱うかは本文で確認する必要があり，別ノードとして追加しない判断とした．

## 5. 網羅できていない分野

`audit/coverage_report.md` の分析の要点は以下の通りである．

- **アナログ型 DeepJSCC**：OFDM・MIMO・フェージング，レート・SNR 適応，Transformer の骨格の系統が未収録である．候補が最も多い（415件，A 83件）．
- **拡散・生成型と JSCC の重なり**：両方に属するノードが現在は無い．CDDM，DiffJSCC，SGD-JSCC 等が該当する．
- **パケット損失耐性**：課題そのものが未収録である（候補34件，A 11件）．
- **デジタル型 DeepJSCC**：ベクトル量子化と適応変調の系統が未収録である．
- **LIC**：主要な系譜は収録済みであるが，Context-adaptive モデル，可変レート，Transformer のエントロピーモデルが未収録である．
- **従来型・通信路符号**：検索期間を2015年以降としたため，今回は評価していない．

## 6. 未解決の論点と限界

- Semantic Scholar の結果を含まない．API キーを用いて再実行する必要がある．
- 被引用文献の追跡は上位200件に限った．DeepJSCC と Scale Hyperprior の被引用文献の大部分は未確認である．
- 関連性の一次判定はキーワードによるもので，"robust"，"semantic communication" 等が広く一致するため，ビット誤り耐性・アナログ型 DeepJSCC の候補数は過大である．
- 人手で判断したのは862件のうち45件である．
- 関係候補は要旨のみを根拠としており，本文は確認していない．
- タイトルに検索語を含まない論文（DDCM，BlindSC のような命名）は拾えていない可能性がある．

## 7. 次に検討すべき作業の候補

1. 追加推奨18件の本文を確認し，関係（特に `builds_on`・`derived_from`）の根拠を確定してから，`data/nodes/` への追加を判断する．追加する場合は，パケット損失耐性を課題タグとして定義する．
2. Semantic Scholar の API キーを取得して検索を再実行し，結果の差分を確認する．
3. DeepJSCC と Scale Hyperprior の被引用文献を被引用数の順に追加で取得し，優先度 B の候補の人手の判断を進める．
4. A Survey on Robust Deep JSCC（arXiv:2604.04413）の参考文献を追跡し，ビット誤り耐性・通信路の不一致に対する頑健性の論文を補う．
5. 会議版と考えられる2件について，既存ノード（DeepJSCC-f，DeepJSCC-l）との同一性を本文で確認する．
