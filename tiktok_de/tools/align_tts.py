# Alignement mot par mot d'une voix off sur son texte, sans service en ligne :
# 1) une voix de synthèse locale (Piper, allemand) lit le même texte et donne la durée de chaque son ;
# 2) on aligne les deux enregistrements (DTW sur MFCC, comme l'outil « aeneas ») ;
# 3) chaque début/fin de mot de la synthèse est reporté sur la vraie voix.
# usage : align_tts.py voix.mp3 texte.txt sortie_words.json   (texte : une phrase par ligne ou texte libre)
import sys, re, json, io, wave, subprocess
import numpy as np, librosa, imageio_ffmpeg
from piper import PiperVoice
MODEL = '/tmp/claude-0/-home-user-skillora-/fec401e9-70df-57ee-af23-f64816928711/scratchpad/piper/de-thorsten-low.onnx'
FF = imageio_ffmpeg.get_ffmpeg_exe(); SR = 16000; HOP = 160
voice_path, text_path, out_path = sys.argv[1:4]
UNITS = ['', 'ein', 'zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben', 'acht', 'neun', 'zehn', 'elf', 'zwölf', 'dreizehn', 'vierzehn', 'fünfzehn', 'sechzehn', 'siebzehn', 'achtzehn', 'neunzehn']
TENS = ['', '', 'zwanzig', 'dreißig', 'vierzig', 'fünfzig', 'sechzig', 'siebzig', 'achtzig', 'neunzig']
def num_de(n):
    if n == 0: return 'null'
    s = ''
    if n >= 1000: s += ('ein' if n // 1000 == 1 else num_de(n // 1000)) + 'tausend'; n %= 1000
    if n >= 100: s += ('ein' if n // 100 == 1 else UNITS[n // 100]) + 'hundert'; n %= 100
    if n >= 20: s += (UNITS[n % 10] + 'und' if n % 10 else '') + TENS[n // 10]
    elif n > 0: s += 'eins' if (n == 1 and not s) else UNITS[n]
    return s
def norm(w):
    # chiffres en toutes lettres pour la synthèse (400er -> vierhunderter) ; le son « ich » (ç) manque
    # dans ce modèle et casse l'alignement : on le remplace par « sch », de durée équivalente
    w = re.sub(r'\d+', lambda m: num_de(int(m.group())), w)
    w = re.sub(r'(?i)(?<=[eiäöüylrn])ch', 'sch', w); w = re.sub(r'(?i)ig(?=\W*$)', 'ik', w)
    return w
raw = open(text_path).read().replace('\n', ' ')
WORDS = [w for w in raw.split() if re.search(r'[\wäöüß]', w)]        # mots affichables (sans « – »)
SENT = [s for s in re.split(r'(?<=[.?!:])\s+', raw.strip()) if s.strip()]
v = PiperVoice.load(MODEL, include_alignments=True); rate = v.config.sample_rate
tts_audio = []; spans = []; t_samp = 0; wi = 0
for s in SENT:
    ws = [w for w in s.split() if re.search(r'[\wäöüß]', w)]
    buf = io.BytesIO(); wf = wave.open(buf, 'wb')
    al = v.synthesize_wav(' '.join(norm(w) for w in ws), wf, include_alignments=True); wf.close()
    buf.seek(0); r = wave.open(buf); a = np.frombuffer(r.readframes(r.getnframes()), np.int16).astype(float) / 32768
    # groupes de sons séparés par ' ' = mots ; ponctuation et marques de début/fin ignorées
    groups = []; cur = []; pos = 0
    for p in al:
        n = int(p.num_samples)
        if p.phoneme == ' ':
            if cur: groups.append(cur); cur = []
        elif re.match(r'[\^\$_.,!?:;…"„“()-]', p.phoneme): pass
        else: cur.append((pos, pos + n))
        pos += n
    if cur: groups.append(cur)
    if len(groups) == len(ws):
        for g in groups: spans.append((t_samp + g[0][0], t_samp + g[-1][1]))
    else:   # repli : répartition selon le nombre de sons de chaque mot
        lens = [max(1, len(''.join(sum(v.phonemize(norm(w)), [])))) for w in ws]; tot = sum(lens)
        voiced = [i for i, x in enumerate(np.abs(a) > 0.02) if x]; a0 = voiced[0] if voiced else 0; a1 = voiced[-1] if voiced else len(a)
        acc = 0
        for L in lens: spans.append((t_samp + a0 + (a1 - a0) * acc / tot, t_samp + a0 + (a1 - a0) * (acc + L) / tot)); acc += L
        print('repli proportionnel :', s[:50], len(groups), '≠', len(ws))
    tts_audio.append(a); t_samp += len(a)
    gap = np.zeros(int(0.12 * rate)); tts_audio.append(gap); t_samp += len(gap)
tts = np.concatenate(tts_audio)
if rate != SR: tts = librosa.resample(tts, orig_sr=rate, target_sr=SR); spans = [(a * SR / rate, b * SR / rate) for a, b in spans]
real = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', voice_path, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(float) / 32768
def feats(x):
    m = librosa.feature.mfcc(y=x, sr=SR, n_mfcc=20, hop_length=HOP, n_fft=512)[1:]
    m = (m - m.mean(1, keepdims=True)) / (m.std(1, keepdims=True) + 1e-6)
    e = librosa.feature.rms(y=x, hop_length=HOP, frame_length=512); e = np.log(e + 1e-4); e = (e - e.mean()) / (e.std() + 1e-6)
    return np.vstack([m, 2.0 * e])      # l'énergie aide à caler silences et pauses
A, B = feats(tts), feats(real)
D, wp = librosa.sequence.dtw(X=A, Y=B, metric='euclidean', global_constraints=True, band_rad=0.12)
wp = wp[::-1]; ta = wp[:, 0]; tb = wp[:, 1]
def map_t(sample):   # temps synthèse -> temps vraie voix (moyenne des cases associées)
    f = sample / HOP; idx = np.where(ta == int(round(f)))[0]
    if len(idx) == 0: idx = [np.argmin(np.abs(ta - f))]
    return float(np.mean(tb[idx])) * HOP / SR
out = []
for w, (a, b) in zip(WORDS, spans): out.append([w, round(map_t(a), 3), round(map_t(b), 3)])
for i in range(1, len(out)): out[i][1] = max(out[i][1], out[i - 1][1] + 0.02)
json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=0)
print('ok', len(out), 'mots ;', ' '.join(f'{w}[{a}]' for w, a, b in out[:12]), '…')
