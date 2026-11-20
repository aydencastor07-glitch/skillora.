# Soupe joumou – sous-titres portugais
- `source.mp4` : vidéo reçue (360×640).
- `sous_titres_pt.srt` : texte portugais (légèrement corrigé pour être naturel au Brésil), `sous_titres_pt.ass` : style incrusté.
- `soupe_joumou_pt.mp4` : vidéo 720×1280 avec les sous-titres incrustés (blanc, contour noir, 2 lignes max).
Refaire : ffmpeg -i source.mp4 -vf "scale=720:1280:flags=lanczos,ass=sous_titres_pt.ass:fontsdir=../../temu/fonts" … soupe_joumou_pt.mp4
