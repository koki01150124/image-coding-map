# report_008：GitHub Actions での Playwright のブラウザ依存パッケージのインストール失敗の調査と修正

本レポートは，GitHub Actions の `python -m playwright install --with-deps chromium` が `Temporary failure resolving 'azure.archive.ubuntu.com'` で失敗した件について，原因の分析とワークフローの修正をまとめたものである．commit・push・ワークフローの再実行は行っていない．

## 1. 調査した事実

GitHub の公開 API（未認証）で，失敗した実行と直前の成功した実行を比較した（2026-11-12 に取得）．ログの本文は認証が必要なため参照していない．

| 実行 | コミット | 「Install Chromium」の結果 | 所要時間 |
| :--- | :--- | :--- | :--- |
| 42049944362 | 390f7bf | 成功 | 22秒 |
| 42255426911 | a5f48b6 | 成功 | 15秒 |
| 42623264808 | 3806427（2026-11-09） | 成功 | 18秒 |
| 43045680277 試行1 | 1229a52（2026-11-11 15:10Z） | 失敗 | 約10分 |
| 43045680277 試行2 | 1229a52（2026-11-11 15:25Z） | 失敗 | 約10分 |

- 失敗した実行では，それより前のステップ（依存ライブラリの導入，書誌情報の照合，データ検証，`graph.json` の生成）はすべて成功し，「Install Chromium」のみが失敗した．テスト以降は実行されていない．
- コミット 1229a52 の変更はデータ・サイト・文書のみであり，`.github/workflows/pages.yml` と `requirements_tools.txt` は変更していない．同じワークフローは2日前（3806427）に成功している．
- 「Install Chromium」は通常15〜22秒で終わるが，失敗時は2回とも約10分を要した．名前解決の失敗に対して apt が再試行し，待ち続けたためと考えられる．
- 現時点で `azure.archive.ubuntu.com` は公開の DNS（Cloudflare の DNS over HTTPS）で解決できる（`ubuntu-archive-asm.trafficmanager.net` → `cloud-mirror-lb.westus2.cloudapp.azure.com`）．名前が廃止されたわけではない．
- GitHub Status の障害の一覧には，2026-11-11 の Actions の障害は記載されていなかった．

## 2. 原因の分析

一時的な障害と恒常的な設定の問題を，以下のように区別した．

| 観点 | 結果 | 判断 |
| :--- | :--- | :--- |
| ワークフロー・依存の版の変更 | 無し | 設定の変更による失敗ではない |
| 同じ構成での直前の成功 | 2日前に成功 | 恒常的な設定の誤りではない |
| ミラーの名前の存在 | 現在は解決できる | 名前の廃止ではない |
| 失敗の箇所 | apt でのミラーへの接続のみ | ランナーの環境から Ubuntu のミラーへの名前解決が一時的に失敗した |

以上から，直接の原因は GitHub ホストランナーの環境で Ubuntu のミラー（`azure.archive.ubuntu.com`）の名前解決が一時的に失敗したことであると判断した．ただし，ログの本文と GitHub 側の記録を確認できないため，DNS とミラーのどちらで障害が起きていたかは特定していない．
一方で，構成上の弱点もある．`--with-deps` は実行のたびに `apt-get update` と `apt-get install` を行うため，テストの成否が，テストと無関係な外部のミラーと DNS の状態に左右される．今回の失敗は一時的な障害であるが，同じ構成のままでは同様の失敗が再び起こり得る．

## 3. 検討した構成

| 案 | 内容 | 評価 |
| :--- | :--- | :--- |
| A. 再試行を加える | `--with-deps` の失敗時に数回やり直す | 障害が数分続くと解消しない．失敗のたびに10分程度待つ |
| B. `--with-deps` を外す | ランナーのイメージに入っている依存に頼る | ランナーのイメージの更新で依存が欠ける可能性があり，安定しない |
| C. apt のキャッシュ | 依存パッケージをキャッシュする | apt のキャッシュは構成が複雑で，`apt-get update` の接続は残る |
| D. Playwright 公式 Docker イメージ | Chromium とシステム依存を含むイメージのコンテナで build ジョブを実行する | 実行時に apt を用いない．版を固定でき，再現性が高い（採用） |

D を採用した．イメージは `mcr.microsoft.com/playwright/python:v1.49.1-noble` とした．これは Ubuntu 24.04，Python 3.12 であり，`requirements_tools.txt` の `playwright==1.49.1` と同じ版である．
イメージの設定を Microsoft Container Registry（MCR）から確認した．amd64 版があり，圧縮時で約 878 MB，2024-12-10 作成，環境変数は `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright` である．イメージの Dockerfile（microsoft/playwright-python の v1.49.1）を見ると，Python 3.12 が外部管理の指定を外して導入されており，`python` コマンド，pip，git も入っている．Playwright の Python パッケージ自体はイメージに残っていないため，ワークフローで固定した版を導入する．

## 4. 変更内容

| ファイル | 変更 |
| :--- | :--- |
| `.github/workflows/pages.yml` | build ジョブを公式イメージのコンテナ（`options: --ipc=host`）で実行する．`actions/setup-python` と `playwright install --with-deps chromium` を削除した．イメージの Chromium が導入した Playwright と一致し起動できることを確かめるステップ（2分で打ち切り）を，テストの前に追加した．ジョブ全体の上限は30分とした |
| `tests/test_workflow.py`（新規，4件） | イメージのタグの版と `requirements_tools.txt` の一致，実行時に apt を用いないこと，`pytest -q tests` を省略・無視しないこと，デプロイがテストを含む build の成功に依存することを検査する |
| `document.md`，`README.md` | CI の構成と，Playwright を更新する場合にイメージのタグも変更する必要があることを記載した |

既存のテスト（`tests/test_site.py`，`tests/test_validate_data.py`，`tests/test_patterns.py`，`tests/test_taxonomy.py`），データ検証，ビルドの処理は変更していない．deploy ジョブも変更していない．ブラウザテストは従来どおり `python -m pytest -q tests` で全件実行し，失敗すればデプロイしない．

変更後の build ジョブの手順は以下の通りである．

```text
コンテナの起動（公式イメージの取得）→ checkout → pip で jsonschema・pytest・playwright の固定版を導入
→ 書誌情報の照合 → データ検証 → graph.json の生成 → Chromium の確認 → テスト（全件）→ Pages の成果物のアップロード
```

## 5. ローカルでの検証

ローカルには Docker が無いため，コンテナそのものは起動していない．以下で代替した．

1. ワークフローの YAML を解析し，`container` の設定が読み取れることを確認した．actionlint による検査は，外部バイナリの実行が許可されなかったため行っていない．
2. 新規の仮想環境（Python 3.12.14）に，ワークフローと同じコマンドで固定版（jsonschema 4.23.0，pytest 8.3.4，playwright 1.49.1）を導入した．
3. ワークフローの `run` を YAML から取り出し，その順に実行した．`PLAYWRIGHT_BROWSERS_PATH` はローカルの Chromium（ビルド 1148，Playwright 1.49.1 用）に設定した．結果は以下の通りである．

```text
[sync] 不一致 0 件，エラー 0 件
[validate] nodes=44 edges=73 errors=0 warnings=1
[build] site/data/graph.json: nodes=44 edges=73
[stamp] app.js?v=fe6cb94fa3 style.css?v=3bbd56e7fe
Python 3.12.14
Version 1.49.1
Chromium OK: .../chromium-1148/chrome-linux/chrome
91 passed in 17.98s
```

4. Chromium が無い場合（空のディレクトリを `PLAYWRIGHT_BROWSERS_PATH` に指定）に，Chromium の確認のステップが「Chromium がイメージに無い（Playwright とイメージの版の不一致）」を表示して終了コード1で失敗することを確認した．
5. `.venv_tools` でテストを全件実行し，91件（既存の87件と `tests/test_workflow.py` の4件）が成功した．

コンテナ内での実際の動作は，push 後の GitHub Actions で初めて確認できる．確認すべき点は以下の通りである．

- 「Initialize containers」でイメージの取得が成功する．
- 「Check Chromium …」で `Chromium OK: /ms-playwright/chromium-1148/...` が表示される．
- テストが91件成功し，deploy ジョブが成功する．

## 6. 未解決事項と今後の改善候補

- 失敗した実行のログの本文を確認していないため，DNS の障害かミラーの障害かは特定していない．認証した `gh run view 43045680277 --log-failed` で確認できる．
- 新しい構成では，実行時に apt を用いない代わりに，MCR からのイメージの取得（約 878 MB）に依存する．MCR の障害時は「Initialize containers」で失敗するため，その場合は「Re-run failed jobs」で再実行する．取得には数十秒を要するため，ジョブの所要時間が延びる可能性がある．
- コンテナ内でのジョブはまだ実行していない．push 後の最初の実行で上記の確認点を確かめる必要がある．
- `requirements_tools.txt` の `playwright` を更新する際は，イメージのタグも同時に更新する必要がある．不一致は `tests/test_workflow.py` とワークフローの Chromium の確認で検出される．
- `actions/checkout@v4` などのアクションは版のタグで指定しており，コミットのハッシュでは固定していない．
