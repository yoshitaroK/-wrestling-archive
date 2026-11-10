"""
どのページにも共通の枠(ヘッダーの上の帯の文字・フッターのリンクの列)。

build_pages.py(大会ページなど)と en_index.py(英語版のトップ)の両方から使う。
トップページの index.html は手で書いたファイルなので、同じ HTML を index.html にも書いてある。
ここを変えたら index.html のフッターも同じ形に直す(合っていないと en_index.py がビルドを止める)。
"""

IG_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>'
          '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1.3" fill="currentColor"/></svg>')
FOOT_SNS = f'<p class="foot-sns"><a href="https://www.instagram.com/japan_wrestlingchannel/" target="_blank" rel="noopener me">{IG_SVG}Instagram</a></p>'

# (見出し, [(リンク先, 名前), …])。英語版に無いページ(ニュース・書籍・歴代優勝者)は英語の列に入れない
FOOT_JA = [
    ("大会・動画", [("/events/", "大会一覧"), ("/events/calendar/", "大会カレンダー"), ("/champions/", "歴代優勝者"), ("/uww/", "国際大会"), ("/technique/", "技術動画")]),
    ("読む・調べる", [("/news/", "ニュース"), ("/players/", "選手検索"), ("/photos/", "写真"), ("/books/", "書籍")]),
    ("このサイトについて", [("/about/", "運営者情報"), ("/faq/", "よくある質問"), ("/contact.html", "お問い合わせ"), ("/privacy/", "プライバシーポリシー")]),
]
FOOT_EN = [
    ("Tournaments & videos", [("/en/events/", "Tournaments"), ("/en/events/calendar/", "Calendar"), ("/en/uww/", "International videos"), ("/en/technique/", "Technique videos")]),
    ("Explore", [("/en/players/", "Players"), ("/en/photos/", "Photos")]),
    ("About this site", [("/en/about/", "About"), ("/en/faq/", "FAQ"), ("/en/contact.html", "Contact"), ("/en/privacy/", "Privacy Policy")]),
]
ABOUT_JA = "Japan Wrestling Channel 公式の配信アーカイブです。YouTube で公開されているレスリングの動画を、大会ごとに整理しています。"
ABOUT_EN = "The official archive of Japan Wrestling Channel. Japanese wrestling videos published on YouTube, organized by tournament."


def official_text(en=False):
    """ヘッダーの上の帯の文字。スマートフォンでは1行に収まるように .ot-l の部分を隠す"""
    if en:
        return '<span class="official-t"><span>Official site<span class="ot-l"> of Japan Wrestling Channel</span></span></span>'
    return '<span class="official-t"><span><span class="ot-l">Japan Wrestling Channel </span>公式サイト</span></span>'


def foot_grid(en=False):
    """フッターの上の段:ロゴと短い説明、リンクを3つの列に分けたもの"""
    cols = FOOT_EN if en else FOOT_JA
    home, other = ("/en/", '<li><a href="/" hreflang="ja" lang="ja">日本語</a></li>') if en else ("/", '<li><a href="/en/" hreflang="en" lang="en">English</a></li>')
    h = ('<div class="foot-grid">\n'
         f'<div class="foot-brand"><a class="foot-logo" href="{home}"><img src="/assets/logo.png" alt="JAPAN WRESTLING CHANNEL" width="118" height="44" loading="lazy"></a>'
         f'<p>{ABOUT_EN if en else ABOUT_JA}</p>{FOOT_SNS}</div>\n')
    for i, (title, links) in enumerate(cols):
        lis = "".join(f'<li><a href="{p}">{t}</a></li>' for p, t in links) + (other if i == len(cols) - 1 else "")
        h += f'<nav class="foot-col" aria-label="{title}"><p class="foot-h">{title}</p><ul>{lis}</ul></nav>\n'
    return h + "</div>"
