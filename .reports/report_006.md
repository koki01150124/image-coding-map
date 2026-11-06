# Report 006：パターン表のボタンが反応しない不具合の調査と修正

## 調査

- 公開サイト（`https://koki01150124.github.io/image-coding-map/`）では，新しい `index.html`（パターン表のボタンを含む），`assets/patterns.js`，パターンを含む `data/graph.json`（生成日 2026-11-06）が配信されていた．新しいブラウザ（Chromium）で開くと，PC（1440×900）とスマートフォンの幅（390×844）の両方でパターン表が開き，エラーは無かった．
- 配信されるファイルには `Cache-Control: max-age=600` が付いており，`app.js` 等の URL は更新の前後で同じであった．
- 新しい `index.html` と更新前（コミット 390f7bf）の `app.js` を組み合わせて配信すると，ボタンは表示されるが押しても何も起きず，エラーも出なかった．報告の症状と一致する．
- `max-age=600` を返すサーバーで，更新前の版を開いた後に新しい版へ置き換えて再読み込みすると，HTML だけが取り直され，`app.js` はキャッシュの古いものが使われて，同じ症状が再現した．

## 原因

GitHub Pages のキャッシュ（10分）により，更新直後の再読み込みで新しい HTML と古い JS が組み合わさった．古い `app.js` にはパターン表のボタンの処理が無いため，ボタンが反応しなかった．プログラムの誤りではなく，配信の更新とブラウザのキャッシュの組み合わせによるものである．

## 修正

- `tools/stamp_assets.py` を追加し，`index.html` の `style.css`・`app.js` の参照と，`app.js` の `layout.js`・`patterns.js` の import に，内容のハッシュ（`?v=` の後に SHA-256 の先頭10文字）を付けるようにした．内容が変わったファイルは別の URL になるため，必ず取り直される．
- `tools/build_graph.py` の最後で `stamp_assets` を呼ぶため，CI（`pages.yml`）の手順は変更していない．同じ内容に対して何度実行しても結果は変わらない．
- `tests/test_validate_data.py::test_assets_are_stamped` で，参照のハッシュが現在の内容と一致することを検査する．

修正の確認として，上記の再読み込みの再現条件で，修正前はボタンが反応せず，修正後はパターン表が開くことを確認した．

## テスト結果

```text
[validate] nodes=44 edges=73 errors=0 warnings=1
[stamp] app.js?v=20eb4590ad style.css?v=dda5261b10
64 passed in 13.51s
```

## 残る事項

- 修正は push してデプロイした後に有効になる．すでに古い `app.js` をキャッシュしているブラウザでは，今回のデプロイ後の初回の読み込みでハッシュ付きの新しい URL を取りに行くため，以後は同じ問題は起きない．デプロイまでの間は，強制再読み込み（Windows: Ctrl+Shift+R，Mac: Cmd+Shift+R）で回避できる．
- `site/` の JS・CSS を変更した後は，`python tools/build_graph.py` を実行して参照を更新する必要がある（テストが検出する）．
