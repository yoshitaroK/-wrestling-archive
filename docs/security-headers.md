# セキュリティヘッダーの設定内容(Cloudflare)

Issue #18 の作業用メモです。GitHub Pages ではレスポンスヘッダーを設定できないため、Cloudflare の「Transform Rules」で付けます。
ここに書いた値は、2026年10月時点でサイトが実際に読み込んでいるもの(HTML・JavaScript・CSS を調べた結果)に合わせています。

## 1. Cloudflare の画面で設定する場所

1. Cloudflare にログインし、`japanwrestlingchannel.com` を選びます。
2. 左のメニューの「ルール」(Rules)→「Transform Rules」(または「設定」→「Transform Rules」)を開きます。
3. 「レスポンスヘッダーの変更」(Modify Response Header)の「ルールを作成」を押します。
4. ルール名は `security-headers` にします。「すべての受信リクエスト」(All incoming requests)を選びます。
5. 下の表のヘッダーを1つずつ「追加」→「静的」(Set static)で入れ、「デプロイ」を押します。

## 2. まず入れるヘッダー(サイトの表示には影響しないもの)

| ヘッダー名 | 値 |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=()` |
| `X-Frame-Options` | `SAMEORIGIN` |

## 3. CSP(Content-Security-Policy)

CSP は「このサイトが読み込んでよい場所」の一覧です。間違えるとページの一部が動かなくなるので、
**最初は `Content-Security-Policy-Report-Only`(見張るだけで止めない)という名前で入れます。**
1〜2週間ブラウザの開発者ツールでエラーが出ないことを確かめてから、名前を `Content-Security-Policy` に変えて本番にします。

ヘッダー名: `Content-Security-Policy-Report-Only`

値(1行で入れます):

```
default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://i.ytimg.com https://*.google-analytics.com https://*.googletagmanager.com; connect-src 'self' https://formspree.io https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self' https://formspree.io mailto:; frame-ancestors 'self'; upgrade-insecure-requests
```

### それぞれの意味

| 項目 | 許可しているもの | 理由 |
|---|---|---|
| `script-src` | 自分のサイト、Google アナリティクス | アクセス解析(gtag.js)のため。`'unsafe-inline'` は下の「今後」を参照 |
| `style-src` | 自分のサイト、Google Fonts | 文字のフォント(Noto Sans JP・Teko)の CSS のため |
| `font-src` | Google Fonts のフォントファイル | 同上 |
| `img-src` | 自分のサイト、YouTube のサムネイル(i.ytimg.com) | 動画一覧のサムネイル、写真(assets/photos/)は自分のサイト |
| `connect-src` | 自分のサイト、Formspree、Google アナリティクス | data.json などの読み込み、お問い合わせの送信、アクセス解析 |
| `frame-src 'none'` | なし | サイト内に YouTube などの埋め込み(iframe)は無い |
| `frame-ancestors 'self'` | 自分のサイトだけ | 他人のサイトに埋め込まれてなりすまされるのを防ぐ |
| `object-src 'none'` / `base-uri 'self'` | なし / 自分のサイト | 古いプラグインや、リンク先を書き換える攻撃を防ぐ |
| `form-action` | 自分のサイト、Formspree、メール | お問い合わせフォームの送信先 |

外へのリンク(YouTube の動画ページ、日本協会、Google フォトのアルバムなど)は、押して移動するだけなので CSP の対象外です。許可に書く必要はありません。

### 今後(Issue #18 の次の 🤖 項目)

今のサイトは、ページの中に直接書いた JavaScript(テーマ切り替え・言語切り替え・写真の拡大表示・サムネイルの読み込み失敗時の処理など)を使っています。
そのため `script-src` に `'unsafe-inline'` を入れています。これらを外部の .js ファイルに移せば `'unsafe-inline'` を外せて、CSP の効果が大きくなります。

## 4. HTTPS 関連(Cloudflare の「SSL/TLS」→「エッジ証明書」)

- 「常に HTTPS を使用」(Always Use HTTPS):オン
- 「HTTPS の自動書き換え」(Automatic HTTPS Rewrites):オン
- 「最小 TLS バージョン」:TLS 1.2
- 「HSTS」:有効。最初は `max-age` を 1か月(2592000)にして、問題が無ければ 6か月以上にする。「サブドメインを含める」はサブドメインを使っていなければオン、「プリロード」は後で決める

## 5. 確認のしかた

- https://securityheaders.com/?q=japanwrestlingchannel.com で評価を見る(目標は A 以上)
- パソコンの Chrome でサイトを開き、F12 →「Console」に赤い `Content-Security-Policy` のエラーが出ていないか見る。出ていたら、その文をこのファイルの Issue(#18)に貼る
