---
name: design
description: japanwrestlingchannel.com(このリポジトリ)の見た目・デザインを変えるときの決まり。「/design ニュースページをヤフーニュース風に」のように、やりたいことを続けて書いて使う。ページの見た目、色、レイアウト、新しいページのデザインを頼まれたときに読む。
---

# /design — サイトのデザインを変えるときの決まり

`/design` のあとに書かれたことが、運営者からのデザインの依頼です。何も書かれていなければ、何をどう変えたいかを聞いてください。
運営者は初心者です。説明・質問はすべて日本語で、GitHub や Cloudflare の画面の操作がわかるように書きます。

## 作業の前に

- README の「データを直す PR の決まり(#75)」を読む。
- 依頼があいまいなとき(どのページか、どこまで変えるか)は、推測した内容を短く伝えて確かめてから作業する。

## 見た目の決まり

- 色は `index.html` の `:root` のトークンだけを使う(`--bg` `--bg2` `--surface` `--surface-2` `--ink` `--ink2` `--ink3` `--line` `--line-hi` `--pink` `--pink-fill` `--pink-deep` `--pink-tint` `--pink-line` `--navy` `--navy-2` `--on-navy` `--on-navy-2` など)。CSS に色を直接書かない(ヘッダーの白い検索欄は例外)。
- 標準は黒のテーマ。`:root[data-theme="light"]` の白テーマも必ず確かめる。
- ヘッダー・フッターは白テーマでも黒(`--navy`・`--navy-2`)。アクセントの赤は `--pink` / `--pink-fill` だけ。ロゴのピンク `--brand-pink` はロゴ以外に使わない。
- 大会の状態はバッジ(`.badge`)で示し、色だけでなく文字も入れる(中止・開催予定・延期・確認中)。
- 文字は Noto Sans JP、年や本数などの数字は Teko(`--num`)。本文 15px・行間 1.7、ページ見出し 28px(スマートフォン 22px)、欄の見出し 19px。
- 動画・大会は 16:9 のサムネイルのタイル(角は `--card-r`)。ボタンは丸い形(`.elink`、主ボタンは `.elink.primary`)。
- ニュースの記事は白地のニュースサイト風(`news.py` の `NEWS_CSS`)。他社のロゴ・名前・配色そのものは使わない(「〇〇風」は並べ方と雰囲気だけ)。
- 日本語版と英語版(`/en/`)の両方、パソコンとスマートフォン(幅 390px)で崩れないこと。ページが横にはみ出さないこと。ヘッダーのメニューと検索欄が、パソコンの幅で1段に収まること。
- 写真を使うときは、撮影者のクレジットを付ける。未成年が写っている写真はトップの特集(`photo_gallery.py` の `HERO_PHOTOS`)に使わない。日本レスリング協会のロゴは許可が確認できるまで使わない。
- 毎日 6:00 の自動更新(`.github/workflows/update.yml`)を壊さない。新しいフォルダにページを作るときは、update.yml の `git add` の一覧にそのフォルダを足す。

## 確かめ方

1. 変更したら `python3 build_pages.py` を実行し、エラーがないこと、`build_report.json` の `photos` の `errors` が空なことを確かめる。
2. 変更前と変更後のスクリーンショットを撮る。変更前は `git worktree add <作業用フォルダ> origin/main` で作った main の写しを、変更後は作業中のリポジトリを、それぞれ `npx http-server` で開いて Playwright(Chromium は `/opt/pw-browsers/chromium`)で撮る。パソコン(1280px)とスマートフォン(390px)、必要なら白テーマも撮る。
3. この環境からは YouTube のサムネイル(i.ytimg.com)が読めないので、Playwright の `route` で `assets/photos` の写真に差し替え、画面に「仮の絵」と書いて撮る。
4. スクリーンショットは見比べられるページ(Artifact)にまとめて、リンクを運営者に渡す。

## PR

- PR を出す前に、画面を見てもらって「PR にしてよいか」を聞く。
- PR には元のファイル(`index.html`・`*.py`・`*.json`・`*.csv`・`articles/`・`.github/` など)だけを入れる。作られるファイル(`data.json`・`build_report.json`・`page_slugs.json`・`sitemap.xml`・`events/`・`en/`・`players/`・`photos/` の中の作られたページ・`news/`・`champions/`・`assets/site.css`・`assets/home.json` など)は入れない。終わったら `git stash push --include-untracked` などで作業ツリーを片付ける。
- PR の説明に、変えたこと・確かめたこと・スクリーンショットのリンクを書く。
- マージ後の手順として伝えること:GitHub で「Merge pull request」→「Confirm merge」、Actions タブで「Update wrestling archive data」が緑になるのを待つ。Cloudflare の「Purge Everything」は、`assets/player.js` や同じ名前のまま差し替えた画像(ロゴ、`assets/feature/` の絵など)を変えたときだけ必要。
