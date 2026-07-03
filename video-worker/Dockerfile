FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY worker.py .

# Tout est en bibliothèque standard Python : aucune dépendance pip.
CMD ["python", "-u", "worker.py"]
