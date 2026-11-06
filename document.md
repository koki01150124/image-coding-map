# image-coding-map（Image Coding Map）

画像圧縮・DeepJSCC・通信路符号の研究系譜を可視化する静的Webサイトと，その論文データ・検証ツールのプロジェクトである．
公開用のリポジトリ名は `image-coding-map` を想定している．サイトの機能，データ形式，論文の追加手順は `README.md` に記載する．

## ディレクトリとファイルの役割

| パス | 役割 |
| :--- | :--- |
| `data/nodes/<id>.json` | 論文・手法ごとの一次データ（44件） |
| `data/domains.json` | 研究分野の定義（ラベル，説明，ライト／ダークの色，列の順） |
| `data/edge_types.json` | エッジ種別の定義（向き，系譜かどうか） |
| `data/vocab.json` | 種別・通信路モデル・根拠・確認範囲・年の基準の表示名 |
| `data/patterns.json` | 改良パターン（13種）・採用技術（16種）の定義（ID，表示名，定義，判断基準，非該当の条件） |
| `docs/pattern_taxonomy.md` | パターンの分類体系の設計（検討した案，採用案，判断基準，点検） |
| `tools/patterns.py`，`site/assets/patterns.js` | パターンの判定（該当／非該当／未判定）と集計．同じ規則を Python と JavaScript で実装し，テストで照合する |
| `data/classification_rules.json` | 分類の規則（DeepJSCC の条件，アナログ／デジタル，構成例，年の基準）．`validate_data.py` が用いる |
| `data/schema/node.schema.json` | ノードの JSON スキーマ（Draft 2020-12） |
| `survey/library.json` | OpenAlex・arXiv・Crossref から取得した書誌情報（44件．採録39件，除外5件）．`surveykit.py` のみが編集する |
| `survey/search_log.json`，`survey/plan.md` 等 | ai-survey-kit の `init` が作成した取得の記録と雛形 |
| `tools/common.py` | JSON・ライブラリの読み込み，掲載先名の整理，書誌情報の変換 |
| `tools/sync_bibliography.py` | `library.json` の書誌情報をノードの `bibliography` へ転記する．`--check` で照合のみ行う |
| `tools/validate_data.py` | データ検証（スキーマ，ID，参照，エッジ種別，循環，書誌情報，年，重複，分類の規則） |
| `tools/build_graph.py` | `data/` を統合して `site/data/graph.json` を生成する |
| `site/index.html`，`site/assets/*` | 配信するサイト（D3.js による描画と操作） |
| `site/vendor/` | D3.js v7.9.0（ISC License）とそのライセンス |
| `tests/test_validate_data.py` | 検証・生成と，学術的な分類の約束のテスト |
| `tests/test_site.py` | Playwright（Chromium）による表示テスト |
| `.github/workflows/pages.yml` | 検証 → 生成 → テスト → GitHub Pages へのデプロイ |
| `requirements_tools.txt` | ツール・テスト用の Python ライブラリ |
| `programs/audit_coverage/collect.py` | 収録範囲の監査の文献収集（既存ノードの台帳，横断検索，スノーボーリング，優先確認論文・本文の参考文献の照合） |
| `programs/audit_coverage/build_candidates.py` | 収集結果の重複排除・関連性の一次判定・優先度付けと，`audit/decisions.json` の人手の判断の反映 |
| `audit/` | 監査の成果物（`coverage_report.md`，`candidates.json`／`.csv`，`decisions.json`，`search_log.json`，`search_tables.md`，`dedup_log.json`，`priority_check.json`，`existing_inventory.csv`，`raw/` は API の応答を正規化したもの）．本番データ（`data/nodes/`）には反映していない |
| `.orders/`，`.reports/` | 作業指示と作業報告 |

## 処理の流れと依存関係

```mermaid
flowchart LR
    API[("OpenAlex / arXiv / Crossref")] -->|surveykit.py add| LIB[("survey/library.json")]
    N[("data/nodes/*.json")] --> SYNC["sync_bibliography.py"]
    LIB --> SYNC
    SYNC -->|bibliography を転記| N
    N --> V["validate_data.py"]
    S[("data/schema/node.schema.json")] --> V
    D[("domains.json / edge_types.json / vocab.json / classification_rules.json")] --> V
    LIB --> V
    N --> B["build_graph.py"]
    D --> B
    B --> G[("site/data/graph.json")]
    G --> APP["site/assets/app.js"]
    LAY["site/assets/layout.js"] --> APP
    D3["site/vendor/d3.v7.9.0.min.js"] --> APP
    G --> T["tests/test_site.py"]
    V --> TV["tests/test_validate_data.py"]
    B --> TV
```

Python のツールは `common.py` を共有し，`validate_data.py` は `sync_bibliography.diff_bibliography` を用いて書誌情報を照合する．`app.js` は試験用に `window.ICM`（経路探索の関数と状態）を公開しており，`tests/test_site.py` が全ての論文の組の経路の検査に用いる．
`build_graph.py` は検証を行わないため，CI では `validate_data.py` の後に実行する．

サイト側の主要な関数の関係を以下に示す．`app.js` は `graph.json` のみを読み，論文の内容・分野・エッジ種別をデータから決めるため，論文を追加しても JavaScript の変更は不要である．

```mermaid
flowchart TD
    main --> loadGraph
    main --> computeLayout["layout.js: computeLayout<br/>年の行・分野の列・行内の段組み"]
    main --> renderFrame["renderFrame<br/>列と年の軸"]
    main --> renderAll
    renderAll --> renderRegions["renderRegions<br/>layout.js: regionPath（ガウス関数の和の等高線）"]
    renderAll --> renderEdges["renderEdges<br/>layout.js: edgePath"]
    renderAll --> renderNodes["renderNodes<br/>形・外周の分野リング"]
    renderAll --> applyFocus["applyFocus<br/>選択・検索・経路の強調"]
    select --> renderPanel["renderPanel<br/>詳細パネル"]
    select --> zoomToNodes
    renderCompare --> pathBox["pathBox<br/>技術的系譜／関連経路の切り替え"]
    pathBox --> findTechnicalLineage["findTechnicalLineage<br/>derived_from・builds_on のみ（直系 → 共通の派生元）"]
    pathBox --> findRelatedPath["findRelatedPath<br/>4種類の関係（向きを無視）"]
    findTechnicalLineage --> bfs
    findRelatedPath --> bfs
    pathBox --> showPathOnMap
    setupPeriod --> setPeriod["setPeriod<br/>表示期間"]
    renderPanel --> yearDetail["yearDetail<br/>年代軸の年・初出・正式掲載"]
    exportSvg --> serializableSvg
    exportPng --> serializableSvg
    readHash --> select
    readHash --> renderCompare
```

## Python 環境の構築

ツールと表示テストの環境は `.venv_tools`（Python 3.12）である．GPU は使用しない．

```bash
uv venv -p 3.12 .venv_tools
uv pip install -p .venv_tools -r requirements_tools.txt
.venv_tools/bin/python -m playwright install chromium
.venv_tools/bin/python -m ipykernel install --user --name venv_tools --display-name "Python (.venv_tools)"
```

使用したバージョンは Python 3.12，jsonschema 4.23.0，pytest 8.3.4，playwright 1.49.1（Chromium Headless Shell 131）である．
`tools/` のスクリプトは `jsonschema`（スキーマ検証）以外は標準ライブラリのみで動作する．Node.js は不要である．

## 実行方法

```bash
.venv_tools/bin/python tools/sync_bibliography.py          # 書誌情報の転記（--check で照合のみ）
.venv_tools/bin/python tools/validate_data.py              # データ検証
.venv_tools/bin/python tools/build_graph.py                # site/data/graph.json の生成
.venv_tools/bin/python -m pytest -q tests                  # テスト（63件）
python3 -m http.server 8000 -d site                        # http://localhost:8000/ で確認
```

書誌情報を追加する場合は `python3 .ai/ai-survey-kit/scripts/surveykit.py add --title "..."` を用いる．

監査の実行方法は以下の通りである（API の待機を含むため数十分を要する）．

```bash
.venv_tools/bin/python programs/audit_coverage/collect.py inventory
.venv_tools/bin/python programs/audit_coverage/collect.py priority
.venv_tools/bin/python programs/audit_coverage/collect.py search openalex_relevance,openalex_cited,arxiv_date
.venv_tools/bin/python programs/audit_coverage/collect.py snowball
.venv_tools/bin/python programs/audit_coverage/collect.py textrefs
cd programs/audit_coverage && ../../.venv_tools/bin/python build_candidates.py
```

## 生成物と文書の保存場所

- `site/data/graph.json` はビルドの生成物であり Git 管理外である．CI で毎回生成する．
- 作業報告は `.reports/report_{n:03}.md`，作業指示は `.orders/order_{n:03}.md` にある．
- 論文の PDF は保存しない（`survey/pdfs/` は Git 管理外）．

## APIキーと設定

- 書誌情報の取得（OpenAlex，arXiv，Crossref）に API キーは不要である．`SURVEYKIT_MAILTO` を設定すると OpenAlex・Crossref の polite pool を利用できる．
- `tokens.json` は本プロジェクトでは使用しない（`.gitignore` 済み）．
- GitHub Pages は Settings → Pages の Source を GitHub Actions にする．

## Git 管理上の注意

- `.ai/` の各 kit はサブモジュールである．公開リポジトリ（`image-coding-map`）にサブモジュールを含めるかは公開時に判断する．CI はサブモジュールを必要としない．
- `survey/library.json` は検証で参照するため Git で管理する．
- 参考にした `optimizer_map` にはライセンスの表示が無く，コードは流用していない．本リポジトリのライセンスは未設定である．
