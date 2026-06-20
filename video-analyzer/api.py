"""
API web (FastAPI) autour du pipeline d'analyse vidéo.
Permet à ton site Skillora d'envoyer une vidéo + une question et de recevoir l'analyse.

Lancer :
    uvicorn api:app --host 0.0.0.0 --port 8000

Tester :
    curl -F "video=@ma_video.mp4" -F "question=De quoi parle la vidéo ?" \
         http://localhost:8000/analyze
"""

import os
import tempfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analyzer import Config, analyze_video

app = FastAPI(title="Skillora Video Analyzer", version="1.0")

# CORS : autorise ton site à appeler l'API (restreins l'origine en prod !).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ex: ["https://skillora.me"] en production
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# On charge la config une seule fois (les modèles se chargent au 1er appel).
DEFAULT_CFG = Config(
    fps=float(os.environ.get("VA_FPS", "1")),
    whisper_model=os.environ.get("VA_WHISPER", "base"),
    reasoner=os.environ.get("VA_REASONER", "ollama"),
    ollama_model=os.environ.get("VA_OLLAMA_MODEL", "llama3"),
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(
    video: UploadFile = File(...),
    question: str = Form("Décris cette vidéo et évalue son potentiel viral."),
):
    suffix = os.path.splitext(video.filename or "")[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await video.read())
        tmp.flush()
        tmp.close()
        result = analyze_video(tmp.name, question, DEFAULT_CFG)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
