# 🎬 Skillora — Analyse vidéo multimodale 100 % locale (open-source)

Analyse une vidéo (**image + son**) sans Google Gemini, avec des modèles libres.

```
Vidéo ─▶ FFmpeg ─▶ ┌ audio.wav ─▶ Whisper ─────▶ transcription horodatée ┐
                   └ frames/*.jpg ─▶ Moondream2 ─▶ descriptions visuelles ┘
                                                            │
                                                  fusion chronologique
                                                            │
                                          LLM (Ollama local OU Claude) ─▶ réponse
```

## 1. Prérequis

### FFmpeg (obligatoire)
- **Ubuntu/Debian** : `sudo apt update && sudo apt install -y ffmpeg`
- **macOS** : `brew install ffmpeg`
- **Windows** : `choco install ffmpeg` (ou télécharger sur ffmpeg.org)

### Python 3.10+
```bash
cd video-analyzer
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```
> 💡 **GPU NVIDIA** : installe la version CUDA de PyTorch (voir https://pytorch.org).
> Sans GPU, ça marche mais c'est plus lent (utilise `--whisper-model tiny`).

### Ollama (pour le raisonnement local — optionnel si tu utilises Claude)
```bash
# Installe Ollama : https://ollama.com
ollama pull llama3        # ou: ollama pull mistral
```

## 2. Utilisation (ligne de commande)

```bash
# Raisonnement avec un LLM 100 % local (Ollama) :
python analyzer.py ma_video.mp4 -q "De quoi parle la vidéo et est-elle accrocheuse ?"

# Plus rapide (moins d'images, petit modèle audio) :
python analyzer.py ma_video.mp4 -q "Résume la vidéo" --fps 0.5 --whisper-model tiny

# Raisonnement avec Claude au lieu d'Ollama :
export ANTHROPIC_API_KEY=sk-ant-...
python analyzer.py ma_video.mp4 -q "Note le potentiel viral /10" --reasoner claude

# Sortie JSON (pour l'intégration) :
python analyzer.py ma_video.mp4 -q "..." --json
```

## 3. Utilisation en API web (pour le site)

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
Puis depuis ton site :
```js
const fd = new FormData();
fd.append("video", fichier);
fd.append("question", "Évalue le potentiel viral de cette vidéo /10");
const r = await fetch("https://TON-SERVEUR:8000/analyze", { method: "POST", body: fd });
const data = await r.json();   // { answer, timeline, transcript, frames }
```

## 4. Choisir / remplacer les modèles

| Étape    | Défaut         | Alternatives                                  |
|----------|----------------|-----------------------------------------------|
| Audio    | `whisper base` | `tiny` (rapide) … `large-v3` (précis)         |
| Vision   | `moondream2`   | `llava-hf/llava-1.5-7b-hf` (voir `vision.py`) |
| Raisonn. | `llama3` (Ollama) | `mistral`, `qwen2.5`, ou `--reasoner claude` |

## ⚠️ Important
Ce pipeline **ne tourne pas sur Vercel/Supabase** (serverless, sans GPU ni FFmpeg).
Héberge-le sur une machine dédiée (ton PC, un VPS, ou un GPU loué type RunPod/Vast),
expose `api.py`, et fais appeler cette API par Skillora.
