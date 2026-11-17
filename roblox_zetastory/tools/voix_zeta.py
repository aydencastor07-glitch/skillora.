# Voix « ZetaStory » à partir d'une voix ElevenLabs normale : même recette que les vidéos de référence
# (voix d'homme montée de 3-4 demi-tons, rapide, sans pauses, bien compressée).
#   1) pauses raccourcies (comme pour les histoires allemandes : tiktok_de/tools/voice_prep.py) ;
#   2) hauteur : on mesure la hauteur moyenne de la voix et on la monte jusqu'à la cible (190 Hz par défaut) ;
#   3) rythme : accélération (TEMPO) ; 4) égalisation + compression + volume.
# usage : voix_zeta.py entree.mp3 sortie.mp3      [CIBLE=190] [TEMPO=1.12] [MAXP=0.22] [DEMITONS=… pour forcer]
import sys, os, subprocess, math
import numpy as np, librosa, imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
src, out = sys.argv[1], sys.argv[2]
CIBLE = float(os.environ.get('CIBLE', 190)); TEMPO = float(os.environ.get('TEMPO', 1.12)); MAXP = os.environ.get('MAXP', '0.22')
ICI = os.path.dirname(os.path.abspath(__file__)); PREP = os.path.join(ICI, '..', '..', 'tiktok_de', 'tools', 'voice_prep.py')
tmp = out + '.serre.mp3'
subprocess.run([sys.executable, PREP, tmp, src], check=True, env={**os.environ, 'MAXP': MAXP}, stdout=subprocess.DEVNULL)
def mesure(f):
    y = np.frombuffer(subprocess.run([FF, '-v', 'error', '-i', f, '-ac', '1', '-ar', '22050', '-f', 's16le', '-'], capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    seg = y[:22050 * 40]; f0, _, _ = librosa.pyin(seg, fmin=60, fmax=500, sr=22050, frame_length=2048); f0 = f0[~np.isnan(f0)]
    on = librosa.onset.onset_detect(onset_envelope=librosa.onset.onset_strength(y=seg, sr=22050), sr=22050)
    return float(np.median(f0)), len(on) / (len(seg) / 22050), len(y) / 22050
f0, debit, dur = mesure(tmp)
dt = float(os.environ['DEMITONS']) if os.environ.get('DEMITONS') else max(0.0, min(6.0, 12 * math.log2(CIBLE / f0)))
ratio = 2 ** (dt / 12)
af = (f'rubberband=pitch={ratio:.4f}:tempo={TEMPO}:pitchq=quality,highpass=f=90,equalizer=f=3200:t=q:w=1.2:g=3,'
      'acompressor=threshold=-22dB:ratio=3.5:attack=5:release=90:makeup=2,loudnorm=I=-14:TP=-1.5')
subprocess.run([FF, '-y', '-v', 'error', '-i', tmp, '-af', af, '-ar', '44100', '-b:a', '192k', out], check=True); os.remove(tmp)
f1, debit1, dur1 = mesure(out)
print(f'avant : {f0:.0f} Hz, {debit:.1f} syll/s, {dur:.1f} s  →  après : {f1:.0f} Hz (+{dt:.1f} demi-tons), {debit1:.1f} syll/s, {dur1:.1f} s')
