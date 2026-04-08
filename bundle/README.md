# SoundToScore V14 — Complete Bundle (Fixed)

## Fixes in this version
- renderOneChunk is not defined → FIXED (single clean JS, no duplicates)
- Download buttons not working → FIXED (fetch+blob cross-origin downloads)
- Merged output download missing → FIXED (renders after all chunks complete)
- Sheet music warning spam → FIXED (silently skips, no MuseScore on Render)
- All buttons broken → FIXED (JS duplicate functions removed)

## Deploy Backend → Render
1. Push backend/ to GitHub
2. Render → New Web Service → Docker
3. Root dir: backend/  |  Dockerfile: ./Dockerfile
4. Deploy → copy your URL

## Deploy Frontend → Vercel
1. Open frontend/index.html
2. Find: const API = 'https://soundtoscore-v14.onrender.com'
3. Replace with your actual Render URL
4. Drag-drop frontend/ to vercel.com → Deploy

## What works
✓ Upload MP3/WAV → processing starts in <1s
✓ Sections appear one by one as they complete (live streaming)
✓ Each section: Play ▶ | Download WAV | Download MIDI | Transcript
✓ After all sections: Full Merged Score appears (purple card)
✓ Full Merged: Play ▶ | Download WAV | Download MIDI | Transcript
✓ Downloads work cross-origin (Vercel → Render) via fetch+blob
✓ Page refresh resumes via localStorage
✓ All 70+ instruments selectable
✓ Mobile responsive with bottom nav + slide-in drawers
