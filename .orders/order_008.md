# order_008：GitHub Actions での Playwright のブラウザ依存パッケージのインストール失敗の調査と修正

## 指示（チャットより）

GitHub Actions で Playwright のブラウザ依存パッケージのインストールに失敗している．

エラー：`Temporary failure resolving 'azure.archive.ubuntu.com'`

`python -m playwright install --with-deps chromium` の実行中に発生している．以下を確認・修正する．

1. GitHub Actions のワークフローを調査する．
2. 一時的な DNS 障害と，恒常的な環境設定の問題を区別する．
3. Chromium と必要なシステム依存関係を安定して利用できる構成を検討する．
4. 必要なら，Playwright 公式 Docker イメージなどの利用を検討する．
5. ブラウザテストを省略してデプロイを成功させる方法は採用しない．
6. 既存のテスト内容は変更しない．
7. 修正後はローカルで可能な範囲の検証を実施する．

変更内容と原因分析を報告する．自動 commit・push は行わない．

## AIエディタによる解釈

- 調査対象は `.github/workflows/pages.yml` と，失敗した実行（コミット 1229a52）の公開 API で取得できる情報（ジョブ・ステップの結果と所要時間）とする．ログの本文は認証が必要なため参照できない前提で，確認できた事実と推定を区別する．
- 修正はワークフローの変更に限り，データ検証・ビルド・テストの内容（`tools/`，`tests/` の既存テスト）は変更しない．ワークフローの構成を検証するテストの追加は「既存のテスト内容の変更」に当たらないものとして行う．
- Playwright 公式 Docker イメージを用いる場合は，`requirements_tools.txt` の `playwright==1.49.1` と同じ版のイメージを用い，版の不一致を検出する手段を設ける．
- ローカルに Docker が無い場合は，コンテナ内で実行するコマンドを同じ版の環境で実行して代替とし，実施できなかった検証を明記する．
- commit・push・ワークフローの再実行（GitHub への書き込み）は行わない．
- 成果物は `.reports/report_008.md` と，必要に応じて `document.md`・`README.md` の更新とする．
