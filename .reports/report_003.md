# Report 003：GitHub Pages の configure-pages エラーの調査

## 確認した事実

公開 API（未認証）で `koki01150124/image-coding-map` を確認した（2026-11-05）．

| 項目 | 結果 |
| :--- | :--- |
| リポジトリ | 公開（public），既定ブランチ `main`，作成 05:53:04Z，push 05:57:18Z |
| `has_pages` | `true`（調査時点） |
| `GET /repos/.../pages`（未認証） | 404．未認証のため，Pages が未設定であることの根拠にはならない |
| Actions の実行 41977232910 | `build` ジョブの手順 1〜9（検証・ビルド・テスト）は成功，手順 10 `configure-pages` が失敗，`deploy` はスキップ |
| `configure-pages` の実行時刻 | 05:58:16Z〜05:58:17Z |
| 環境 `github-pages` の作成時刻 | 05:58:34Z（失敗の17秒後） |
| `https://koki01150124.github.io/image-coding-map/` | 404（未デプロイ） |

`pages.yml` の権限は `contents: read`，`pages: write`，`id-token: write` であり，`configure-pages`（Pages の取得），`upload-pages-artifact`，`deploy-pages`（OIDC による認証）に必要な権限を満たす．ワークフローに明示した `permissions` は，リポジトリの既定のトークン権限（読み取りのみ等）より優先される．

## 原因

`configure-pages` は Pages のサイト情報を取得する（`GET /repos/{owner}/{repo}/pages`）．実行時点（05:58:16Z）では Pages のサイトが作成されておらず 404 となった．
その17秒後に `github-pages` 環境が作成され，調査時点で `has_pages` が `true` であることから，失敗の直後に Settings → Pages で Source が設定（Pages が有効化）されたと推定される．権限の設定は原因ではない．

推定であるため，Settings → Pages の「Build and deployment」の Source が **GitHub Actions** になっていることを確認する必要がある（「Deploy from a branch」の場合は Actions の成果物はデプロイされない）．

## `enablement: true` について

`enablement: true` は Pages が無い場合にサイトを作成する（`POST /repos/{owner}/{repo}/pages`）．サイトの作成にはリポジトリの管理（Administration）の書き込み権限が必要であり，`GITHUB_TOKEN` には `permissions` で Administration を付与できないため，`GITHUB_TOKEN` のままでは作成に失敗する．
自動で有効化する場合は，Administration（Read and write）と Pages（Read and write）を持つ fine-grained PAT か GitHub App のトークンを Secret に登録して `token:` に渡す必要がある．Pages の有効化は一度で済むため，本リポジトリでは推奨しない．

## 最小限の修正案

1. Settings → Pages → Build and deployment → Source が「GitHub Actions」であることを確認する（未設定なら設定する）．
2. 失敗した実行を「Re-run all jobs」で再実行する（または Actions の画面から `workflow_dispatch` で実行する）．
3. ワークフロー（`.github/workflows/pages.yml`）の変更は不要である．

## 未確認の事項

- 認証が無いため，Pages の `build_type`（`workflow`／`legacy`）と `github-pages` 環境の保護規則（デプロイを許可するブランチ）は確認していない．既定では `main` からのデプロイが許可される．
