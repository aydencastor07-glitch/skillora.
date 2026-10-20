# Génère une image texte→image (Seedream v4 via fal, clé ajoutée par l'environnement). usage : t2i.py out.jpg "prompt" [w h]
import sys, json, urllib.request, io, base64
from PIL import Image
out, prompt = sys.argv[1], sys.argv[2]; w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1440, 2560)
body = {'prompt': prompt, 'image_size': {'width': w, 'height': h}, 'num_images': 1, 'enable_safety_checker': True, 'sync_mode': True}
UA = {'User-Agent': 'Mozilla/5.0'}
for k in range(3):
    try:
        req = urllib.request.Request('https://fal.run/fal-ai/bytedance/seedream/v4/text-to-image', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        d = json.load(urllib.request.urlopen(req, timeout=300)); url = d['images'][0]['url']
        data = base64.b64decode(url.split(',', 1)[1]) if url.startswith('data:') else urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        Image.open(io.BytesIO(data)).convert('RGB').save(out, quality=95); print('ok', out); break
    except Exception as e: print('retry', k, e)
