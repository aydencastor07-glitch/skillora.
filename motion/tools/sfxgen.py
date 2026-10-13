# Génère la bibliothèque d'effets sonores avec ElevenLabs (clé ajoutée par l'environnement, en-tête xi-api-key).
# usage : sfxgen.py <dossier> [nom ...]   → <nom>.mp3 et <nom>.wav (44,1 kHz mono)
import sys, json, urllib.request, subprocess, os, time
import imageio_ffmpeg
SFX = {
 'whoosh':  ('fast clean cinematic whoosh transition, short, no music', 0.8),
 'swish':   ('quick light air swish of a fast arm movement, short and soft', 0.5),
 'click':   ('crisp camera shutter click, single, clean', 0.5),
 'tap':     ('single soft modern UI tap click for text appearing, very short', 0.5),
 'hit':     ('deep cinematic bass drum hit impact, punchy, short tail', 1.2),
 'glitch':  ('short digital glitch stutter sound effect, clean, modern', 0.6),
 'snap':    ('single crisp finger snap', 0.5),
 'ding':    ('positive correct answer chime, bright and short', 0.8),
 'buzz':    ('short wrong answer error buzzer, soft not harsh', 0.6),
 'pop':     ('soft bubbly pop for an icon appearing, short', 0.5),
 'clank':   ('metal dumbbell plates clank gently, single short hit', 0.6),
 'shine':   ('magical sparkle shimmer highlight, short and subtle', 0.9),
 'thud':    ('heavy dull body thud, dropping something too heavy, short', 0.8),
}
out = sys.argv[1]; names = sys.argv[2:] or list(SFX); FF = imageio_ffmpeg.get_ffmpeg_exe()
for n in names:
    text, dur = SFX[n]; mp3 = f'{out}/{n}.mp3'
    for a in range(4):
        try:
            req = urllib.request.Request('https://api.elevenlabs.io/v1/sound-generation', method='POST',
                data=json.dumps({'text': text, 'duration_seconds': dur, 'prompt_influence': 0.6}).encode(),
                headers={'Content-Type': 'application/json'})
            open(mp3, 'wb').write(urllib.request.urlopen(req, timeout=120).read()); break
        except Exception as e:
            print('retry', n, e, e.read()[:200] if hasattr(e, 'read') else ''); time.sleep(3 + 3 * a)
    subprocess.run([FF, '-y', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', '44100', f'{out}/{n}.wav'], check=True)
    print('ok', n)
