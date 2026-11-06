# Image Coding Map

従来型画像圧縮，学習型画像圧縮（Learned Image Compression，LIC），生成・拡散型画像圧縮，情報源・通信路分離符号化（Separate Source-Channel Coding，SSCC），アナログ型・デジタル型の深層結合情報源・通信路符号化（Deep Joint Source-Channel Coding，DeepJSCC），通信路符号の研究の関係を，**論文・手法をノード，論文間の関係をエッジ**とするグラフとして可視化する静的Webサイトである．
D3.js で描画し，GitHub Pages で公開する．

- 縦の位置は年代軸の年（古い年を上），横の位置は研究分野の列である．年代軸の年は，論文では**最初の公開年**（arXiv 初版と正式掲載の早い方）である．正式掲載の掲載先と年は詳細パネルに併記する（「年の扱い」を参照）．
- 研究分野は色・列・背景の範囲で表す．複数の分野に属する論文は，ノードの外周の色分けと，分野の範囲の重なりで表す．分野は論文とは別の種類の要素であり，ノードにはしない．
- エッジは「技術的改良・発展」「技術・モデルの利用」「共通研究課題」「比較対象」の4種類である．直接の派生関係が論文中で確認できない場合は派生関係として接続しない．初期表示では技術的な発展関係（前の2種類）のみを表示し，比較対象・共通研究課題は凡例のボタンで表示する．
- 書誌情報は OpenAlex・arXiv・Crossref の API から取得した値のみを用い，内容の項目で確認できないものは「未確認」と表示する．

## 収録範囲

2026年11月時点で44件（論文35件，標準規格の解説論文4件，公開ソフトウェア1件，SSCC の構成例3件，未公開の研究1件），関係73本（技術的改良・発展15本，技術・モデルの利用15本，共通研究課題8本，比較対象35本）を収録している．

| 分野 | 主な収録対象 |
| :--- | :--- |
| 生成・拡散型画像圧縮 | HiFiC，DDPM，CDC，DDCM，Turbo-DDCM，Robust Turbo-DDCM |
| 学習型画像圧縮（LIC） | Toderici（RNN），CAE（Theis），Ballé 2017，Scale Hyperprior，Minnen 2018，Cheng 2020，Channel-wise AR，Checkerboard，ELIC，TCM |
| 従来型画像圧縮 | JPEG，JPEG 2000，HEVC，BPG，VVC |
| SSCC | JPEG＋LDPC，BPG＋LDPC，LIC＋LDPC（いずれも論文中で比較対象として用いられた構成例） |
| 通信路符号化・関連技術 | Shannon 1948，LDPC（Gallager，MacKay），Turbo 符号，Polar 符号，学習型物理層（O'Shea） |
| デジタル型 DeepJSCC | NECST，IABF，DeepJSCC-Q，JCM，D²-JSCC，BlindSC，ESC-MVQ，BFR-CAE |
| アナログ型 DeepJSCC | DeepJSCC（Bourtsoulatze），DeepJSCC-f，DeepJSCC-l，ADJSCC，NTSCC，SwinJSCC |

分類上の約束は以下の通りである．

- JPEG は画像圧縮方式，LDPC は通信路符号であり，JPEG＋LDPC は分離設計（SSCC）の具体例である．
- LIC と DeepJSCC は排他的な分類ではない．NTSCC は LIC とアナログ型 DeepJSCC の両方に属する．
- アナログ型（連続値の通信路シンボル）とデジタル型（ビット・有限の変調シンボル）の DeepJSCC を区別する．
- 生成・拡散型画像圧縮は DeepJSCC の下位分類ではない．Robust Turbo-DDCM はビット誤り耐性を評価するが，通信路を含めた共同学習を行わないため DeepJSCC に分類しない．
- Robust Turbo-DDCM と BFR-CAE はビット誤り耐性という共通課題（related）でのみ結び，派生関係とはしない．
- BFR-CAE は，BSC を含めて符号化器・復号器を共同学習する条件の下でデジタル型 DeepJSCC に位置付ける．論文として未公開である．

## 使い方

| 操作 | 方法 |
| :--- | :--- |
| 移動・拡大縮小 | ドラッグで移動，マウスホイールで拡大・縮小．「全体表示」で全体に戻る |
| 詳細の表示 | ノードをクリック（またはフォーカスして Enter）．書誌情報，原論文・arXiv・DOI・コード・Google Scholar へのリンク，情報源表現，通信路モデル，アナログ／デジタルの区分，貢献，学習方法，評価指標，長所，制約，関係と根拠を表示する |
| エッジの説明 | エッジにマウスを重ねると，関係の内容と根拠（要旨・本文など）を表示する |
| 検索 | 略称・別名・タイトル・著者・タグ・通信路モデル等で検索する．空白区切りで AND 検索となる．Enter で最初の一致を選択する |
| 分野の絞り込み | 「分野」のボタンで表示を切り替える．マウスを重ねると分野の範囲を強調する |
| エッジの切り替え | 「関係」のボタンで4種類のエッジを個別に表示・非表示にする．初期状態では比較対象・共通研究課題を非表示とする |
| 表示期間 | 「期間」で「2015年以降」「2020年以降」を選ぶと，該当する論文だけを表示して拡大する |
| 年スライダー | 指定した年までの論文だけを表示する．「再生」で年を進めながら表示する．表示期間と併用できる |
| 比較 | 詳細パネルの「比較に追加」で最大3件を選び，「比較」で項目ごとの比較表を表示する |
| 経路 | 比較画面に2件ずつの経路を表示し，「マップ上で表示」で強調する．「技術的系譜」（初期状態）と「関連経路」を切り替えられる（下表） |
| 一覧表 | 表示中の論文を表形式で表示する |
| パターン表 | 「パターン表」で，行＝改良パターン（または採用技術），列＝研究分野の対応表を表示する（下記） |
| 書き出し | 「書き出し」からマップ全体を SVG／PNG で保存する |
| 配色 | 「配色」で 自動 → ライト → ダーク を切り替える |
| 直接リンク | `#necst` のように ID を付けた URL で，その論文を選択した状態で開く．`#compare=necst,blindsc,deepjscc` で比較画面を開く |

ノードの形は，丸が論文，角の丸い四角が標準規格・公開ソフトウェア，破線の輪郭が SSCC の構成例，点線の輪郭が未公開の研究である．

| 経路の種類 | 探索に用いる関係 | 内容 | マップ上の強調 |
| :--- | :--- | :--- | :--- |
| 技術的系譜 | `derived_from`，`builds_on` のみ | (1) 一方が他方の派生元である直系の経路，(2) 共通の派生元から両者へ発展した経路，の順に探し，各段を「派生元 → 派生先」の向きで示す．無い場合は「技術的系譜は存在しない」と表示する | 赤 |
| 関連経路 | 4種類すべて（向きは無視） | 最短のつながりを示し，各段の関係の種類を明示する．比較対象・共通研究課題の段は「派生関係ではない」と表示する | 紫（関係ごとの線種を保持） |

例えば BlindSC と DeepJSCC（Bourtsoulatze）の間には技術的系譜が無く，関連経路では「DeepJSCC → DeepJSCC-Q（改良・発展）」と「BlindSC が DeepJSCC-Q を比較対象とした」の2段として示される．

## パターン表

「パターン表」は，論文・手法に付与した**改良パターン**（先行方式に対して何を改良したか）と**採用技術**（方式を構成する技術要素）を，研究分野ごとに集計する表である．分類の設計は `docs/pattern_taxonomy.md`，定義は `data/patterns.json` にある．

- 「改良パターン表」と「採用技術表」を切り替えられる．行の名前にマウスを重ねると定義と判断基準を表示する．
- セルの数は該当する論文・手法の数であり，件数に応じて色が濃くなる．行・列の「合計」は重複を除いた件数である．
- 複数分野に属する論文は各分野に計上する（重複集計）．
- セルの「0」は確認済みのデータに該当例が無いことを示し，その研究が存在しないことを意味しない．「未判定 n」は根拠が不足して判定していないノードの数であり，非該当とは区別する．
- 初期状態では論文（`kind: paper`）のみを集計する．「集計対象」で標準規格・ソフトウェア，構成例，未公開研究を加えられる．
- マップの表示期間・年スライダー・分野の絞り込みを反映する（非表示の分野は列から除く）．
- セル（または行の名前）を選ぶと該当する論文の一覧と根拠を表示し，「研究マップ上で強調」で該当する論文をマップ上で強調する．
- 詳細パネルにも，その論文の改良パターン・採用技術と根拠，判定の状態を表示する．

ノードとパターンの組は「該当」「非該当」「未判定」の3値で判定する．該当は根拠つきで付与したもの，非該当は判定済み（`assessed`）の軸で付与していないもの・対象外（`not_applicable`）の軸・定義の非該当の条件（例: 学習を行わない方式に学習型の技術は該当しない）に一致するもの，それ以外は未判定である．

## 年の扱い

`year`（年代軸の年）の意味は `year_basis` で定める．プレプリントと正式掲載版は同じノードにまとめ，`publication` に初出と正式掲載を記録する．

| 種別 | `year_basis` | `year` の意味 |
| :--- | :--- | :--- |
| 論文 | `first_public` | 最初の公開年．arXiv 初版（ID の年月）と正式掲載の早い方 |
| 標準規格 | `standard_overview` | 収録した解説論文の最初の公開年（標準規格の制定年ではない） |
| ソフトウェア | `software_release` | 最初の公開版の年 |
| 構成例 | `scheme_first_use` | 収録論文のうち，比較対象として最初に用いた論文の初出年 |
| 未公開研究 | `unpublished_placement` | 配置のための研究開発年．発表年としては表示しない（「未公開」と表示） |

正式掲載の掲載先と年は，`survey/library.json`（OpenAlex）か，論文の本文（ヘッダ・脚注）・arXiv のコメントで確認できたもののみを記録し，根拠を `evidence` に書く．年スライダー・表示期間は `year` で判定する．

## ディレクトリ構成

```text
.
├── data/
│   ├── nodes/<id>.json         # 論文・手法ごとに1ファイル（一次データ）
│   ├── domains.json            # 研究分野（ラベル，説明，色，列の順）
│   ├── edge_types.json         # エッジ種別（向き，系譜かどうか）
│   ├── vocab.json              # 種別・通信路モデル・根拠・年の基準などの表示名
│   ├── classification_rules.json # 分類の規則（検証で用いる）
│   ├── patterns.json           # 改良パターン・採用技術の定義（パターン表）
│   └── schema/node.schema.json # ノードの JSON スキーマ
├── survey/
│   ├── library.json            # API から取得した書誌情報（surveykit.py のみが編集する）
│   └── search_log.json         # 取得の記録
├── site/                       # GitHub Pages で配信する静的サイト
│   ├── index.html
│   ├── assets/app.js           # 描画・操作
│   ├── assets/layout.js        # 配置の計算
│   ├── assets/patterns.js      # パターンの判定と集計（tools/patterns.py と同じ規則）
│   ├── assets/style.css        # 配色（ライト／ダーク）とレイアウト
│   ├── vendor/                 # D3.js v7.9.0 とそのライセンス
│   └── data/graph.json         # 生成物（Git 管理外，CI で生成）
├── tools/
│   ├── common.py               # 読み込みの共通処理
│   ├── sync_bibliography.py    # library.json の書誌情報をノードへ転記・照合
│   ├── validate_data.py        # データ検証
│   ├── patterns.py             # パターンの判定と集計
│   └── build_graph.py          # data/ → site/data/graph.json
├── tests/
│   ├── test_validate_data.py   # 検証・生成のテスト
│   └── test_site.py            # ブラウザによる表示テスト（Playwright）
├── .github/workflows/pages.yml # 検証 → 生成 → テスト → Pages へデプロイ
└── requirements_tools.txt
```

## データの形式

`data/nodes/<id>.json` の主なキーを示す．厳密な定義は `data/schema/node.schema.json` である．未確認の項目は推測で埋めず `null` とする．

| キー | 内容 |
| :--- | :--- |
| `id` | ノードID（ファイル名と一致，英小文字・数字・`_`） |
| `kind` | `paper`，`standard`，`software`，`scheme`（構成例），`unpublished` |
| `short_name`，`aliases` | 表示名と検索用の別名 |
| `bib_key` | `survey/library.json` の引用キー．論文・標準規格（`paper`，`standard`）では必須 |
| `bibliography` | タイトル，著者，年，掲載先，DOI，arXiv ID，原論文 URL，出典．`bib_key` がある場合は `sync_bibliography.py` が転記する |
| `year`，`year_basis`，`year_note` | 年代軸の年とその基準（「年の扱い」を参照）．補足や，書誌情報の年が初出・正式掲載のいずれとも異なる場合の根拠を `year_note` に書く |
| `publication` | 初出 `first_public` と正式掲載 `formal`（それぞれ `{venue, year, evidence}` または `null`） |
| `domains` | 研究分野（複数可，先頭が主分野） |
| `source_representation` | 情報源表現・潜在表現 |
| `channel_models` | 通信路モデル（`AWGN`，`Rayleigh`，`BSC`，`BEC`，`B-DMC`，`feedback`，`general`）．通信路を扱わない場合は空配列 |
| `transmission` | `analog`，`digital`，`not_applicable` |
| `joint_channel_training` | 通信路（雑音・ビット反転）を含めて符号化器・復号器を共同学習するか（`true`／`false`／未確認 `null`）．DeepJSCC に分類する条件 |
| `contributions`，`training`，`metrics`，`strengths`，`limitations` | 主要な技術的貢献，学習方法，評価指標，長所，制約・弱点 |
| `relations` | 関係 `{target, type, note, evidence: {kind, detail}}` の配列．`kind` は `abstract`，`full_text`，`official_page`，`source_code`，`project_doc` |
| `verification` | 確認した範囲（`read_level`）と注記 |
| `patterns` | `improvements`（改良パターン）と `techniques`（採用技術）．それぞれ判定の状態 `assessment`（`assessed`／`partial`／`not_applicable`／`unassessed`），理由 `note`，項目 `items`（`{id, evidence: {kind, detail}, from?}`）．`from` は改良元のノード（系譜の関係にあるもの） |

エッジ種別の意味と向きは以下の通りである．関係は新しい側（関係を登録するノード）から参照先へ書く．

| 種別 | 意味 | 系譜 | 描画 |
| :--- | :--- | :---: | :--- |
| `derived_from` | 参照先の手法を直接改良・拡張した（論文中で改良元として明示） | ○ | 実線の矢印（元 → 新） |
| `builds_on` | 参照先の手法・モデル・構成要素を部品や前提として利用した | ○ | 破線の矢印（元 → 新） |
| `related` | 直接の派生関係は無いが，同じ研究課題を扱う | － | 点線（向きなし） |
| `compared_with` | 実験で比較対象（ベースライン）とした | － | 一点鎖線（向きなし） |

系譜（○）のエッジは循環してはならず，派生元は派生先より新しくてはならない．発表年の先後だけを根拠にエッジを作らない．

分類の規則は `data/classification_rules.json` に記述し，検証で検査する．現在の規則は，DeepJSCC に属するノードは通信路を含む共同学習を行わないもの（`false`）であってはならない，アナログ型・デジタル型の DeepJSCC の区分は `analog`・`digital` である，構成例の主分野は SSCC で書誌情報を持たない，情報理論の基礎研究（タグ「情報理論（基礎）」）を SSCC にしない，種別ごとに年の基準を定める，である．

## 論文の追加手順

1. `survey/library.json` に書誌情報を登録する（記憶から書かない）．

   ```bash
   python .ai/ai-survey-kit/scripts/surveykit.py add --title "論文のタイトル"
   python .ai/ai-survey-kit/scripts/surveykit.py add --arxiv 2501.02273
   python .ai/ai-survey-kit/scripts/surveykit.py set <key> --status included
   ```

2. `data/nodes/<id>.json` を作成する．`bib_key` に引用キーを書き，`bibliography` は空の雛形（全て `null`）でよい．`publication` に初出（arXiv 初版など）と正式掲載を根拠とともに書き，`year` を初出年にする．関係には根拠（要旨・本文の該当箇所など）を必ず書く．プレプリントと正式掲載版を別のノードにしない．
3. 書誌情報を転記し，検証・生成・テストを実行する．

   ```bash
   python tools/sync_bibliography.py
   python tools/validate_data.py
   python tools/build_graph.py
   python -m pytest -q tests
   ```

分野・エッジ種別・語彙を追加する場合も，`data/` の JSON とスキーマのみを変更すればよく，描画コードの変更は不要である．

## ローカルでの実行

```bash
uv venv -p 3.12 .venv_tools
uv pip install -p .venv_tools -r requirements_tools.txt
.venv_tools/bin/python -m playwright install chromium
.venv_tools/bin/python tools/build_graph.py
python3 -m http.server 8000 -d site
```

ブラウザで `http://localhost:8000/` を開く．

## 検証

`tools/validate_data.py` は以下を検査し，エラーがあれば終了コード1を返す．

- JSON スキーマ（必須キー，型，語彙）
- ID とファイル名の一致，重複 ID
- 未定義の分野・エッジ種別
- 存在しない参照先，自己参照，重複した関係
- 系譜関係（`derived_from`，`builds_on`）の循環，派生元が派生先より新しい関係
- 書誌情報と `survey/library.json` の一致，論文・標準規格の `bib_key` の有無
- 年代軸の年と `year_basis`・初出・正式掲載・arXiv ID の整合，構成例の年
- 同じ論文の重複（`bib_key`，arXiv ID，DOI，タイトル）
- 分類の規則（`data/classification_rules.json`）
- パターン定義（`data/patterns.json`）の重複 ID・書式と，ノードの参照（未定義・重複の ID，対象外の軸の項目，改良元，非該当の条件との矛盾）

`tests/test_site.py` は，GitHub Pages と同じサブパス（`/image-coding-map/`）でサイトを配信し，全ノード・エッジの描画（初期表示は系譜のエッジのみ），URL による選択，初出年と正式掲載年の表示，未公開研究の年の表示，検索，分野・エッジ・期間・年の絞り込み，比較，技術的系譜と関連経路（全ての論文の組で，技術的系譜に比較対象・共通研究課題が含まれないこと），ノードとラベルの重なりと文字の対比（ライト・ダーク），配色の切り替え，SVG／PNG の書き出し，ホイールによる拡大を確認する．

## GitHub Pages への公開

1. リポジトリ（例: `image-coding-map`）を作成して push する．
2. Settings → Pages の Source を **GitHub Actions** にする．
3. `main` への push で `.github/workflows/pages.yml` が書誌情報の照合，データ検証，`graph.json` の生成，テストを行い，`site/` をデプロイする．プルリクエストでは検証とテストのみを行う．

サイトは相対パスのみを用いるため，リポジトリ名（公開時のサブパス）に依存しない．

## 注意事項

- 論文の内容の項目は，API で取得した要旨と，arXiv 等で公開された本文の該当箇所の照合に基づく．全文を精読したものではない．各ノードの「確認した範囲」に照合の範囲を記録している．
- 論文の PDF はリポジトリに保存しない．リンクのみを表示する．
- `survey/library.json` の書誌情報は API の応答をそのまま用いる（著者名の「姓, 名」の表記のみ「名 姓」にそろえて表示する）．応答の誤りが判明しているもの（Turbo 符号の年，DDPM の要旨，D²-JSCC の著者名の表記）は各ノードの `year_note`・`verification.notes` に記録している．
- 設計は [optimizer_map](https://github.com/yryo1005/optimizer_map) を参考にした．同リポジトリにはライセンスの表示が無いため，コードは流用せず新規に実装している．
- 同梱の D3.js は ISC License である（`site/vendor/d3.LICENSE.txt`）．本リポジトリのコードとデータのライセンスは未設定である．
