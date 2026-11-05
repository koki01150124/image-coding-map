# Image Compression Map

従来型画像圧縮，学習型画像圧縮（Learned Image Compression，LIC），生成・拡散型画像圧縮，情報源・通信路分離符号化（Separate Source-Channel Coding，SSCC），アナログ型・デジタル型の深層結合情報源・通信路符号化（Deep Joint Source-Channel Coding，DeepJSCC），通信路符号の研究の関係を，**論文・手法をノード，論文間の関係をエッジ**とするグラフとして可視化する静的Webサイトである．
D3.js で描画し，GitHub Pages で公開する．

- 縦の位置は発表年（古い年を上），横の位置は研究分野の列である．
- 研究分野は色・列・背景の範囲で表す．複数の分野に属する論文は，ノードの外周の色分けと，分野の範囲の重なりで表す．分野は論文とは別の種類の要素であり，ノードにはしない．
- エッジは「技術的改良・発展」「技術・モデルの利用」「共通研究課題」「比較対象」の4種類である．直接の派生関係が論文中で確認できない場合は派生関係として接続しない．
- 書誌情報は OpenAlex・arXiv・Crossref の API から取得した値のみを用い，内容の項目で確認できないものは「未確認」と表示する．

## 収録範囲

2026年11月時点で44件（論文35件，標準規格の解説論文4件，公開ソフトウェア1件，SSCC の構成例3件，未公開の研究1件），関係73本（技術的改良・発展15本，技術・モデルの利用16本，共通研究課題9本，比較対象33本）を収録している．

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
| エッジの切り替え | 「関係」のボタンで4種類のエッジを個別に表示・非表示にする |
| 年スライダー | 指定した年までの論文だけを表示する．「再生」で年を進めながら表示する |
| 比較 | 詳細パネルの「比較に追加」で最大3件を選び，「比較」で項目ごとの比較表を表示する |
| 系譜の経路 | 比較画面に2件ずつの経路を表示し，「マップ上で表示」で強調する．経路は (1) 派生・利用をたどる直系の系譜，(2) 共通の祖先・子孫を経由する系譜，(3) 共通課題・比較を含む関係のつながり，の順に探し，どの種類の経路かを明示する |
| 一覧表 | 表示中の論文を表形式で表示する |
| 書き出し | 「書き出し」からマップ全体を SVG／PNG で保存する |
| 配色 | 「配色」で 自動 → ライト → ダーク を切り替える |
| 直接リンク | `#necst` のように ID を付けた URL で，その論文を選択した状態で開く．`#compare=necst,blindsc,deepjscc` で比較画面を開く |

ノードの形は，丸が論文，角の丸い四角が標準規格・公開ソフトウェア，破線の輪郭が SSCC の構成例，点線の輪郭が未公開の研究である．

## ディレクトリ構成

```text
.
├── data/
│   ├── nodes/<id>.json         # 論文・手法ごとに1ファイル（一次データ）
│   ├── domains.json            # 研究分野（ラベル，説明，色，列の順）
│   ├── edge_types.json         # エッジ種別（向き，系譜かどうか）
│   ├── vocab.json              # 種別・通信路モデル・根拠などの表示名
│   └── schema/node.schema.json # ノードの JSON スキーマ
├── survey/
│   ├── library.json            # API から取得した書誌情報（surveykit.py のみが編集する）
│   └── search_log.json         # 取得の記録
├── site/                       # GitHub Pages で配信する静的サイト
│   ├── index.html
│   ├── assets/app.js           # 描画・操作
│   ├── assets/layout.js        # 配置の計算
│   ├── assets/style.css        # 配色（ライト／ダーク）とレイアウト
│   ├── vendor/                 # D3.js v7.9.0 とそのライセンス
│   └── data/graph.json         # 生成物（Git 管理外，CI で生成）
├── tools/
│   ├── common.py               # 読み込みの共通処理
│   ├── sync_bibliography.py    # library.json の書誌情報をノードへ転記・照合
│   ├── validate_data.py        # データ検証
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
| `bib_key` | `survey/library.json` の引用キー．論文（`paper`）では必須 |
| `bibliography` | タイトル，著者，年，掲載先，DOI，arXiv ID，原論文 URL，出典．`bib_key` がある場合は `sync_bibliography.py` が転記する |
| `year`，`year_note` | マップ上の年．書誌情報の年と異なる場合は根拠を `year_note` に書く |
| `domains` | 研究分野（複数可，先頭が主分野） |
| `source_representation` | 情報源表現・潜在表現 |
| `channel_models` | 通信路モデル（`AWGN`，`Rayleigh`，`BSC`，`BEC`，`B-DMC`，`feedback`，`general`）．通信路を扱わない場合は空配列 |
| `transmission` | `analog`，`digital`，`not_applicable` |
| `contributions`，`training`，`metrics`，`strengths`，`limitations` | 主要な技術的貢献，学習方法，評価指標，長所，制約・弱点 |
| `relations` | 関係 `{target, type, note, evidence: {kind, detail}}` の配列．`kind` は `abstract`，`full_text`，`official_page`，`source_code`，`project_doc` |
| `verification` | 確認した範囲（`read_level`）と注記 |

エッジ種別の意味と向きは以下の通りである．関係は新しい側（関係を登録するノード）から参照先へ書く．

| 種別 | 意味 | 系譜 | 描画 |
| :--- | :--- | :---: | :--- |
| `derived_from` | 参照先の手法を直接改良・拡張した（論文中で改良元として明示） | ○ | 実線の矢印（元 → 新） |
| `builds_on` | 参照先の手法・モデル・構成要素を部品や前提として利用した | ○ | 破線の矢印（元 → 新） |
| `related` | 直接の派生関係は無いが，同じ研究課題を扱う | － | 点線（向きなし） |
| `compared_with` | 実験で比較対象（ベースライン）とした | － | 一点鎖線（向きなし） |

系譜（○）のエッジは循環してはならない．発表年の先後だけを根拠にエッジを作らない．

## 論文の追加手順

1. `survey/library.json` に書誌情報を登録する（記憶から書かない）．

   ```bash
   python .ai/ai-survey-kit/scripts/surveykit.py add --title "論文のタイトル"
   python .ai/ai-survey-kit/scripts/surveykit.py add --arxiv 2501.02273
   python .ai/ai-survey-kit/scripts/surveykit.py set <key> --status included
   ```

2. `data/nodes/<id>.json` を作成する．`bib_key` に引用キーを書き，`bibliography` は空の雛形（全て `null`）でよい．関係には根拠（要旨・本文の該当箇所など）を必ず書く．
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
- 系譜関係（`derived_from`，`builds_on`）の循環
- 書誌情報と `survey/library.json` の一致，年の不一致に対する `year_note` の有無，論文の `bib_key` の有無

`tests/test_site.py` は，GitHub Pages と同じサブパス（`/image-compression-map/`）でサイトを配信し，全ノード・エッジの描画，URL による選択，検索，分野・エッジ・年の絞り込み，比較と経路，配色の切り替え，SVG／PNG の書き出し，ホイールによる拡大を確認する．

## GitHub Pages への公開

1. リポジトリ（例: `image-compression-map`）を作成して push する．
2. Settings → Pages の Source を **GitHub Actions** にする．
3. `main` への push で `.github/workflows/pages.yml` が書誌情報の照合，データ検証，`graph.json` の生成，テストを行い，`site/` をデプロイする．プルリクエストでは検証とテストのみを行う．

サイトは相対パスのみを用いるため，リポジトリ名（公開時のサブパス）に依存しない．

## 注意事項

- 論文の内容の項目は，API で取得した要旨と，arXiv 等で公開された本文の該当箇所の照合に基づく．全文を精読したものではない．各ノードの「確認した範囲」に照合の範囲を記録している．
- 論文の PDF はリポジトリに保存しない．リンクのみを表示する．
- `survey/library.json` の書誌情報は API の応答をそのまま用いる．応答の誤りが判明しているもの（Turbo 符号の年，DDPM の要旨）は各ノードの `year_note`・`verification.notes` に記録している．
- 設計は [optimizer_map](https://github.com/yryo1005/optimizer_map) を参考にした．同リポジトリにはライセンスの表示が無いため，コードは流用せず新規に実装している．
- 同梱の D3.js は ISC License である（`site/vendor/d3.LICENSE.txt`）．本リポジトリのコードとデータのライセンスは未設定である．
