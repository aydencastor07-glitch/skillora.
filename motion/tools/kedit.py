# Édition d'image avec référence (Cloudflare FLUX.2 [klein]) : garde le personnage, change la pose.
# usage : kedit.py <ref.jpg> <sortie.jpg> <prompt> [w] [h] [modèle]
import sys, json, base64, urllib.request, uuid, os, time, io
from PIL import Image
ref, out, prompt = sys.argv[1:4]
w = int(sys.argv[4]) if len(sys.argv) > 4 else 768; h = int(sys.argv[5]) if len(sys.argv) > 5 else 768
model = sys.argv[6] if len(sys.argv) > 6 else 'flux-2-klein-9b'
ACC = os.environ.get('CF_ACCOUNT_ID') or '8d0aa08785afc373cdec8e7d28508576'
buf = io.BytesIO(); Image.open(ref).convert('RGB').resize((w, h)).save(buf, 'PNG')
refs = [r for r in ref.split(',')]
for attempt in range(5):
    b = uuid.uuid4().hex; parts = []
    def field(n, v): parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode())
    field('prompt', prompt); field('width', w); field('height', h)
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="input_image_0"; filename="ref.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + buf.getvalue() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/{model}', data=b''.join(parts),
                                 headers={'Content-Type': f'multipart/form-data; boundary={b}'})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=150))
        open(out, 'wb').write(base64.b64decode(d['result']['image'])); print('ok', out); break
    except Exception as e:
        body = e.read()[:180] if hasattr(e, 'read') else ''
        print('retry', attempt, e, body); time.sleep(3 + attempt * 4)
