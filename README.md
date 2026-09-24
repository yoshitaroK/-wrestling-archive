# レスリング配信アーカイブ

Japan Wrestling Channel の配信アーカイブを大会別に整理して表示するサイトです。
GitHub Actions が毎日自動で最新の配信情報を取得し、`data.json` を更新します。

## ファイル構成

- `index.html` — サイト本体(このリポジトリを Pages で公開すると、そのままこれが表示されます)
- `data.json` — 大会ごとに整理された動画データ(自動更新される)
- `update_site.py` — YouTube から動画情報を取得し、大会ごとに分類して `data.json` を作るスクリプト
- `.github/workflows/update.yml` — 毎日自動で `update_site.py` を実行する設定

## セットアップ手順

### 1. このファイル一式をリポジトリにアップロード

GitHubのリポジトリ画面で「Add file」→「Upload files」から、このフォルダの中身をすべてドラッグ&ドロップしてください。
(`.github` フォルダも含めて、フォルダ構造を保ったままアップロードします)

### 2. YouTube Data API キーをシークレットに登録

1. リポジトリの「Settings」タブを開く
2. 左メニューの「Secrets and variables」→「Actions」を開く
3. 「New repository secret」を押す
4. Name に `YOUTUBE_API_KEY`、Secret に自分のAPIキーを貼り付けて保存

### 3. GitHub Pages を有効化

1. リポジトリの「Settings」タブ →「Pages」
2. 「Source」を「Deploy from a branch」に設定
3. Branch を `main`、フォルダを `/ (root)` にして保存
4. 数分待つと `https://あなたのユーザー名.github.io/リポジトリ名/` で公開されます

### 4. 動作確認(手動で1回実行してみる)

1. リポジトリの「Actions」タブを開く
2. 「Update wrestling archive data」ワークフローを選択
3. 「Run workflow」ボタンを押して手動実行
4. 数分で完了し、`data.json` が最新化されます(2回目以降は毎日自動実行されます)

## 自動更新の頻度を変える

`.github/workflows/update.yml` の `cron: '0 21 * * *'` の部分を変更すると、実行時刻・頻度を調整できます(現在は毎日 日本時間6:00)。
