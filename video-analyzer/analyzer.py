"""
Skillora — Analyse vidéo multimodale 100 % locale & open-source
================================================================
Pipeline (sans Google Gemini) :

    1. RÉCEPTION & DÉCOUPAGE  ........  FFmpeg   -> audio.wav + frames/*.jpg
    2. ANALYSE AUDIO  ................  Whisper  -> transcription + timestamps
    3. ANALYSE VISUELLE  ............  Moondream2 -> description de chaque image
    4. FUSION & RAISONNEMENT  .......  LLM local (Ollama) OU Claude

Chaque étape est une classe indépendante -> tu peux remplacer un modèle
sans toucher au reste.

Usage CLI :
    python analyzer.py ma_video.mp4 -q "De quoi parle cette vidéo et est-elle accrocheuse ?"
    python analyzer.py ma_video.mp4 -q "..." --reasoner claude --fps 0.5

Auteur : Skillora — licence libre d'usage.
"""

from __future__ import annotations

import os
import json
import glob
import shutil
import argparse
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional


# ════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════════════
@dataclass
class Config:
    # Étape 1 — découpage
    fps: float = 1.0                       # nombre d'images extraites par seconde
    max_frames: int = 45                   # garde-fou : on ne décrit jamais plus d'images

    # Étape 2 — Whisper (faster-whisper)
    whisper_model: str = "base"            # tiny | base | small | medium | large-v3
    whisper_device: str = "auto"           # auto | cpu | cuda
    whisper_compute: str = "auto"          # auto | int8 | float16 | float32
    language: Optional[str] = None         # ex: "fr" pour forcer ; None = auto-détection

    # Étape 3 — vision locale
    vision_model_id: str = "vikhyatk/moondream2"
    vision_revision: str = "2024-08-26"    # épingle une version stable du modèle
    vision_device: str = "auto"            # auto | cpu | cuda
    vision_prompt: str = "Décris en une phrase précise ce que montre cette image."

    # Étape 4 — raisonnement
    reasoner: str = "ollama"               # "ollama" (local) ou "claude" (API)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"           # ex: llama3 | mistral | qwen2.5
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_key_env: str = "ANTHROPIC_API_KEY"

    # Divers
    work_dir: Optional[str] = None         # dossier de travail (sinon temporaire)
    keep_files: bool = False               # garder audio/frames après l'analyse


# ── Petits utilitaires ──────────────────────────────────────────────
def _auto_device() -> str:
    """Retourne 'cuda' si un GPU NVIDIA est dispo, sinon 'cpu'."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _fmt_ts(seconds: float) -> str:
    """Secondes -> 'mm:ss' lisible."""
    seconds = int(round(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _log(msg: str) -> None:
    print(f"[skillora] {msg}", flush=True)


# ── Structures de données échangées entre les étapes ────────────────
@dataclass
class Frame:
    index: int
    path: str
    timestamp: float            # en secondes depuis le début


@dataclass
class FrameDesc:
    timestamp: float
    description: str


@dataclass
class Segment:
    start: float
    end: float
    text: str


# ════════════════════════════════════════════════════════════════════
#  ÉTAPE 1 — DÉCOUPAGE (FFmpeg)
# ════════════════════════════════════════════════════════════════════
class VideoSplitter:
    """Sépare la piste audio et extrait les images clés via FFmpeg."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @staticmethod
    def check_ffmpeg() -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "FFmpeg est introuvable. Installe-le (ex: 'sudo apt install ffmpeg' "
                "ou 'brew install ffmpeg') puis réessaie."
            )

    def extract_audio(self, video_path: str, out_wav: str) -> str:
        """Audio mono 16 kHz WAV : le format idéal pour Whisper."""
        _log("Extraction de l'audio…")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn",                      # pas de vidéo
            "-ac", "1",                 # mono
            "-ar", "16000",             # 16 kHz
            "-c:a", "pcm_s16le",        # WAV PCM
            out_wav,
        ]
        self._run(cmd)
        return out_wav

    def extract_frames(self, video_path: str, out_dir: str) -> List[Frame]:
        """Extrait `fps` images par seconde dans out_dir/frame_00001.jpg, …"""
        _log(f"Extraction des images ({self.cfg.fps} img/s)…")
        os.makedirs(out_dir, exist_ok=True)
        pattern = os.path.join(out_dir, "frame_%05d.jpg")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps={self.cfg.fps}",
            "-q:v", "3",                # bonne qualité JPEG
            pattern,
        ]
        self._run(cmd)

        files = sorted(glob.glob(os.path.join(out_dir, "frame_*.jpg")))
        frames: List[Frame] = []
        for i, path in enumerate(files):
            # 1re image = juste après t=0, puis pas régulier de 1/fps
            ts = i / self.cfg.fps if self.cfg.fps else float(i)
            frames.append(Frame(index=i, path=path, timestamp=ts))

        # Garde-fou : si trop d'images, on échantillonne uniformément.
        if len(frames) > self.cfg.max_frames:
            step = len(frames) / self.cfg.max_frames
            frames = [frames[int(k * step)] for k in range(self.cfg.max_frames)]
            _log(f"{len(files)} images réduites à {len(frames)} (échantillonnage uniforme).")

        _log(f"{len(frames)} images prêtes.")
        return frames

    @staticmethod
    def _run(cmd: List[str]) -> None:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError("FFmpeg a échoué :\n" + proc.stderr.decode(errors="ignore")[-800:])


# ════════════════════════════════════════════════════════════════════
#  ÉTAPE 2 — TRANSCRIPTION AUDIO (faster-whisper)
# ════════════════════════════════════════════════════════════════════
class AudioTranscriber:
    """Transcrit l'audio en texte horodaté avec faster-whisper (local)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        device = self.cfg.whisper_device
        if device == "auto":
            device = _auto_device()

        compute = self.cfg.whisper_compute
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"

        _log(f"Chargement de Whisper '{self.cfg.whisper_model}' ({device}/{compute})…")
        self._model = WhisperModel(self.cfg.whisper_model, device=device, compute_type=compute)

    def transcribe(self, wav_path: str) -> List[Segment]:
        self._load()
        _log("Transcription de l'audio…")
        # vad_filter coupe les silences -> transcription plus propre.
        segments, info = self._model.transcribe(
            wav_path,
            language=self.cfg.language,
            vad_filter=True,
            beam_size=5,
        )
        out: List[Segment] = []
        for s in segments:
            txt = (s.text or "").strip()
            if txt:
                out.append(Segment(start=s.start, end=s.end, text=txt))
        _log(f"{len(out)} segments transcrits (langue détectée : {getattr(info, 'language', '?')}).")
        return out


# ════════════════════════════════════════════════════════════════════
#  ÉTAPE 3 — DESCRIPTION VISUELLE (Moondream2)
# ════════════════════════════════════════════════════════════════════
class VisionDescriber:
    """Décrit chaque image clé avec un modèle de vision local et léger.

    Par défaut : Moondream2 (~2 Go, rapide). Pour LLaVA-1.5-7b, voir le commentaire
    dans _load() : il suffit de changer le chargement, la logique reste identique.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._model = None
        self._tok = None
        self._device = None

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._device = self.cfg.vision_device
        if self._device == "auto":
            self._device = _auto_device()
        dtype = torch.float16 if self._device == "cuda" else torch.float32

        _log(f"Chargement du modèle de vision '{self.cfg.vision_model_id}' ({self._device})…")
        self._model = AutoModelForCausalLM.from_pretrained(
            self.cfg.vision_model_id,
            revision=self.cfg.vision_revision,
            trust_remote_code=True,
            torch_dtype=dtype,
        ).to(self._device).eval()
        self._tok = AutoTokenizer.from_pretrained(
            self.cfg.vision_model_id, revision=self.cfg.vision_revision
        )
        # ── Variante LLaVA (décommente et adapte) ──
        # from transformers import LlavaForConditionalGeneration, AutoProcessor
        # self._processor = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
        # self._model = LlavaForConditionalGeneration.from_pretrained(
        #     "llava-hf/llava-1.5-7b-hf", torch_dtype=dtype).to(self._device)

    def _describe_one(self, image) -> str:
        """Compatible avec les différentes versions de l'API Moondream."""
        m = self._model
        prompt = self.cfg.vision_prompt
        if hasattr(m, "answer_question"):          # API classique
            enc = m.encode_image(image)
            return m.answer_question(enc, prompt, self._tok).strip()
        if hasattr(m, "query"):                    # API récente
            return m.query(image, prompt)["answer"].strip()
        if hasattr(m, "caption"):                  # légende simple
            return m.caption(image)["caption"].strip()
        raise RuntimeError("API du modèle de vision non reconnue.")

    def describe_frames(self, frames: List[Frame]) -> List[FrameDesc]:
        self._load()
        from PIL import Image

        _log(f"Description de {len(frames)} images…")
        out: List[FrameDesc] = []
        for f in frames:
            try:
                img = Image.open(f.path).convert("RGB")
                desc = self._describe_one(img)
            except Exception as e:
                desc = f"(image illisible : {e})"
            out.append(FrameDesc(timestamp=f.timestamp, description=desc))
            _log(f"  [{_fmt_ts(f.timestamp)}] {desc[:70]}")
        return out


# ════════════════════════════════════════════════════════════════════
#  ÉTAPE 4 — FUSION & RAISONNEMENT (Ollama local OU Claude)
# ════════════════════════════════════════════════════════════════════
class ReasoningEngine:
    """Fusionne audio + visuel en une chronologie, puis interroge un LLM."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    # --- Fusion chronologique ---
    def build_timeline(self, segments: List[Segment], frame_descs: List[FrameDesc]) -> str:
        events = []
        for s in segments:
            events.append((s.start, "AUDIO ", s.text))
        for d in frame_descs:
            events.append((d.timestamp, "VISUEL", d.description))
        events.sort(key=lambda e: e[0])
        return "\n".join(f"[{_fmt_ts(t)}] ({src}) {txt}" for t, src, txt in events)

    # --- Construction du prompt ---
    def build_messages(self, timeline: str, question: str):
        system = (
            "Tu es un assistant expert qui analyse une vidéo courte. On te fournit une "
            "CHRONOLOGIE qui combine deux sources horodatées :\n"
            "  - (AUDIO)  : ce qui est DIT dans la vidéo (transcription).\n"
            "  - (VISUEL) : ce qui est VU à l'écran (description des images clés).\n\n"
            "Raisonne en croisant le son et l'image. Réponds de façon claire, concrète et "
            "utile à la question de l'utilisateur. Si une information manque, dis-le honnêtement."
        )
        user = (
            f"### CHRONOLOGIE DE LA VIDÉO\n{timeline}\n\n"
            f"### QUESTION\n{question}"
        )
        return system, user

    # --- Aiguillage ---
    def ask(self, timeline: str, question: str) -> str:
        system, user = self.build_messages(timeline, question)
        _log(f"Raisonnement via '{self.cfg.reasoner}'…")
        if self.cfg.reasoner == "claude":
            return self._ask_claude(system, user)
        return self._ask_ollama(system, user)

    # --- Backend 1 : LLM local via Ollama ---
    def _ask_ollama(self, system: str, user: str) -> str:
        import requests
        resp = requests.post(
            f"{self.cfg.ollama_url}/api/chat",
            json={
                "model": self.cfg.ollama_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.4},
            },
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    # --- Backend 2 : Claude (API) ---
    def _ask_claude(self, system: str, user: str) -> str:
        import requests
        key = os.environ.get(self.cfg.anthropic_key_env, "")
        if not key:
            raise RuntimeError(f"Variable d'environnement {self.cfg.anthropic_key_env} absente.")
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.cfg.anthropic_model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", [])).strip()


# ════════════════════════════════════════════════════════════════════
#  ORCHESTRATEUR
# ════════════════════════════════════════════════════════════════════
def analyze_video(video_path: str, question: str, cfg: Optional[Config] = None) -> dict:
    """Exécute tout le pipeline et renvoie un dictionnaire de résultats."""
    cfg = cfg or Config()
    if not os.path.isfile(video_path):
        raise FileNotFoundError(video_path)

    work = cfg.work_dir or tempfile.mkdtemp(prefix="skillora_va_")
    frames_dir = os.path.join(work, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    try:
        # 1) Découpage
        splitter = VideoSplitter(cfg)
        splitter.check_ffmpeg()
        wav = splitter.extract_audio(video_path, os.path.join(work, "audio.wav"))
        frames = splitter.extract_frames(video_path, frames_dir)

        # 2) Audio
        segments = AudioTranscriber(cfg).transcribe(wav)

        # 3) Visuel
        frame_descs = VisionDescriber(cfg).describe_frames(frames)

        # 4) Fusion + raisonnement
        engine = ReasoningEngine(cfg)
        timeline = engine.build_timeline(segments, frame_descs)
        answer = engine.ask(timeline, question)

        return {
            "question": question,
            "answer": answer,
            "timeline": timeline,
            "transcript": [s.__dict__ for s in segments],
            "frames": [d.__dict__ for d in frame_descs],
        }
    finally:
        if not cfg.keep_files:
            shutil.rmtree(work, ignore_errors=True)
        else:
            _log(f"Fichiers conservés dans : {work}")


# ════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════
def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Analyse vidéo multimodale locale (Skillora).")
    p.add_argument("video", help="Chemin de la vidéo à analyser")
    p.add_argument("-q", "--question", required=True, help="Question sur la vidéo")
    p.add_argument("--fps", type=float, default=1.0, help="Images extraites par seconde (def: 1)")
    p.add_argument("--whisper-model", default="base", help="tiny|base|small|medium|large-v3")
    p.add_argument("--language", default=None, help="Forcer la langue (ex: fr)")
    p.add_argument("--reasoner", choices=["ollama", "claude"], default="ollama")
    p.add_argument("--ollama-model", default="llama3")
    p.add_argument("--keep-files", action="store_true", help="Garder audio/images")
    p.add_argument("--json", action="store_true", help="Sortie JSON brute")
    return p


def main() -> None:
    args = _build_cli().parse_args()
    cfg = Config(
        fps=args.fps,
        whisper_model=args.whisper_model,
        language=args.language,
        reasoner=args.reasoner,
        ollama_model=args.ollama_model,
        keep_files=args.keep_files,
    )
    result = analyze_video(args.video, args.question, cfg)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n" + "═" * 60)
        print("RÉPONSE :\n")
        print(result["answer"])
        print("═" * 60)


if __name__ == "__main__":
    main()
