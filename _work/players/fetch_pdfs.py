"""jwf_index.json に書いた「入賞者一覧」の PDF を、日本レスリング協会のサイトから jwf/ に取ってくる(1秒に1件ずつ)"""
import hashlib, json, os, time, urllib.parse, urllib.request

UA = {"User-Agent": "JapanWrestlingChannelArchive/1.0 (+https://japanwrestlingchannel.com/)"}
os.makedirs("jwf", exist_ok=True)
for x in json.load(open("jwf_index.json", encoding="utf-8")):
    for u in x["winners"]:
        fn = "jwf/" + hashlib.md5(u.encode()).hexdigest()[:10] + ".pdf"
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            continue
        for i in range(4):
            try:
                req = urllib.request.Request(urllib.parse.quote(u, safe=":/%?=&"), headers=UA)
                with open(fn, "wb") as f:
                    f.write(urllib.request.urlopen(req, timeout=40).read())
                print("ok", fn)
                break
            except Exception as ex:
                print("retry", u, ex)
                time.sleep(5)
        time.sleep(1)
