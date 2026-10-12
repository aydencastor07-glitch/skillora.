# Génère des images : Cloudflare Workers AI (Flux Schnell, quota gratuit) ou Pollinations (gratuit).
# usage : genimg.py <cf|poll> <sortie.jpg> <prompt> [seed] [w] [h]
import sys, json, base64, urllib.request, urllib.parse, time, os
eng, out, prompt = sys.argv[1:4]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
w = int(sys.argv[5]) if len(sys.argv) > 5 else 1024
h = int(sys.argv[6]) if len(sys.argv) > 6 else 1024
ACC = os.environ.get('CF_ACCOUNT_ID') or '8d0aa08785afc373cdec8e7d28508576'
for attempt in range(4):
    try:
        if eng == 'cf':
            req = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/flux-1-schnell',
                data=json.dumps({'prompt': prompt + (f', variation {seed}' if seed > 1 else ''), 'steps': 6}).encode(), headers={'Content-Type': 'application/json'})
            d = json.load(urllib.request.urlopen(req, timeout=120))
            open(out, 'wb').write(base64.b64decode(d['result']['image']))
        else:
            u = 'https://image.pollinations.ai/prompt/' + urllib.parse.quote(prompt) + '?' + urllib.parse.urlencode({'width': w, 'height': h, 'seed': seed, 'nologo': 'true', 'model': 'flux'})
            open(out, 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=180).read())
        print('ok', out); break
    except Exception as e:
        print('retry', attempt, e); time.sleep(4 + attempt * 4)
