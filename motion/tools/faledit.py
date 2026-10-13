# Édition d'image avec référence via fal.ai (Nano Banana / Seedream) : garde le personnage, change la pose.
# usage : faledit.py <ref.jpg>[,<ref2.jpg>] <sortie.jpg> <prompt> [modèle=fal-ai/nano-banana/edit]
# La clé est ajoutée par l'environnement (secret réseau sur fal.run, en-tête Authorization « Key … »).
import sys, json, base64, urllib.request, time, io
from PIL import Image
refs, out, prompt = sys.argv[1].split(','), sys.argv[2], sys.argv[3]
model = sys.argv[4] if len(sys.argv) > 4 else 'fal-ai/nano-banana/edit'
def data_uri(p):
    buf = io.BytesIO(); im = Image.open(p).convert('RGB'); im.thumbnail((1536, 1536)); im.save(buf, 'JPEG', quality=92)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
body = {'prompt': prompt, 'image_urls': [data_uri(r) for r in refs], 'num_images': 1, 'output_format': 'png'}
UA = {'User-Agent': 'Mozilla/5.0'}
for attempt in range(4):
    try:
        req = urllib.request.Request(f'https://fal.run/{model}', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', **UA})
        d = json.load(urllib.request.urlopen(req, timeout=300))
        url = d['images'][0]['url']
        data = base64.b64decode(url.split(',', 1)[1]) if url.startswith('data:') else urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        Image.open(io.BytesIO(data)).convert('RGB').save(out, quality=95); print('ok', out); break
    except Exception as e:
        body_err = e.read()[:300] if hasattr(e, 'read') else ''
        print('retry', attempt, e, body_err); time.sleep(4 + attempt * 6)
