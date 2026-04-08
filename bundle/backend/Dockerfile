FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fluidsynth \
    libsndfile1 \
    libfluidsynth-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download SoundFont at build time (baked in)
RUN mkdir -p assets/soundfonts && \
    curl -L --retry 5 --retry-delay 3 \
    "https://github.com/JayaramanSathyanarayanan/SoundToScore/releases/download/v1.0/GeneralUser_GS.sf2" \
    -o assets/soundfonts/GeneralUser_GS.sf2 \
    && echo "SoundFont downloaded OK" \
    || echo "SoundFont will download at runtime"

RUN mkdir -p uploads outputs temp

EXPOSE 10000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
