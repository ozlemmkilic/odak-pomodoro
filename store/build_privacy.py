"""Create the offline/privacy-hosting page from the in-app text."""
import html
from pathlib import Path

root=Path(__file__).resolve().parents[1]
body=html.escape((root/'GIZLILIK.txt').read_text(encoding='utf-8'))
page='''<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Odak — Gizlilik</title><style>
body{margin:0;background:#f5f6f8;color:#202734;font:17px/1.7 system-ui,sans-serif}
main{max-width:760px;margin:48px auto;padding:40px;background:white;border-radius:20px;border-top:6px solid #ffa500;white-space:pre-wrap}
@media(max-width:600px){main{margin:0;padding:24px;border-radius:0}}
</style></head><body><main>'''+body+'</main></body></html>'
(root/'store'/'privacy.html').write_text(page,encoding='utf-8')
