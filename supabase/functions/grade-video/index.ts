// SKILLORA — grade-video v8 : notes ANCRÉES sur des faits mesurés.
// Le FORMAT n'est plus une opinion de l'IA : il est CALCULÉ depuis les vraies
// dimensions envoyées par l'app (9:16 = 10 ; horizontal = 2,5 + conseil recadrage).
// Résultat : une vidéo recadrée par Skillora remonte MATHÉMATIQUEMENT sa note —
// l'analyse ne peut plus contredire l'amélioration (confiance client).
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const MODELS = [
  "claude-sonnet-4-6",
  "claude-sonnet-4-5",
  "claude-haiku-4-5-20251001",
  "claude-haiku-4-5",
  "claude-3-5-sonnet-20240620",
  "claude-3-haiku-20240307",
];

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!AI_KEY) return j({ error: "Cle IA manquante." }, 500);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifie." }, 401);

    const body = await req.json().catch(() => ({}));
    const caption = String(body.caption ?? "").slice(0, 1000);
    const platform = String(body.platform ?? "tiktok").toLowerCase();
    const niche = String(body.niche ?? "").slice(0, 80);
    const duration = Number(body.duration_s ?? 0) || 0;
    const transcript = String(body.transcript ?? "").slice(0, 2500);
    const topHashtags = Array.isArray(body.top_hashtags) ? body.top_hashtags.slice(0, 30) : [];
    const frames = Array.isArray(body.frames) ? body.frames.slice(0, 6) : [];
    if (!frames.length) return j({ error: "Ajoute une video." }, 400);

    // ── FAIT MESURÉ n°1 : le FORMAT (dimensions réelles envoyées par l'app) ──
    const W = Number(body.width) || 0, H = Number(body.height) || 0;
    let formatReal: number | null = null;
    let formatFact = "";
    if (W > 0 && H > 0) {
      const r = W / H; // 9:16 = 0.5625
      if (r <= 0.60) { formatReal = 10; formatFact = `${W}x${H} : format vertical 9:16 PARFAIT pour ${platform}`; }
      else if (r <= 0.70) { formatReal = 8; formatFact = `${W}x${H} : vertical, proche du 9:16 idéal`; }
      else if (r < 0.95) { formatReal = 6; formatFact = `${W}x${H} : format vertical non standard`; }
      else if (r < 1.05) { formatReal = 5; formatFact = `${W}x${H} : format CARRÉ — passable mais pas optimal pour ${platform}`; }
      else { formatReal = 2.5; formatFact = `${W}x${H} : format HORIZONTAL (paysage type YouTube) — TRÈS pénalisant sur ${platform}, à recadrer en 9:16`; }
    }

    const imgs = [];
    for (const f of frames) {
      const m = String(f).match(/^data:(image\/[a-zA-Z]+);base64,(.+)$/);
      if (m) imgs.push({ type: "image", source: { type: "base64", media_type: m[1], data: m[2] } });
    }
    if (!imgs.length) return j({ error: "Images illisibles." }, 400);

    const factBlock = formatReal !== null
      ? `\n\nFAITS MESURÉS (NE JAMAIS les contredire) :\n- Dimensions réelles : ${formatFact}. La note 'format' est DÉJÀ FIXÉE à ${formatReal}/10 par la mesure — recopie EXACTEMENT ${formatReal} dans scores.format, n'en débats pas.${formatReal <= 5 ? " Ton 'tip' DOIT recommander en priorité le recadrage vertical 9:16 (Skillora peut le faire automatiquement via « Améliorer ma vidéo »)." : ""}`
      : "";

    const sys = `Tu es le moteur d'analyse video de Skillora. On te donne quelques images extraites d'une video courte (${platform}) dans l'ordre chronologique (les premieres = le tout debut / le hook), sa duree (${duration || "?"}s), la niche, la description, ET la TRANSCRIPTION audio (ce qui est dit dans la video) quand elle est disponible. La transcription represente 100% du contenu parle : appuie-toi dessus en priorite pour comprendre le sujet et juger la retention ; les images servent surtout a juger le visuel (cadrage, hook visuel, energie). Tu evalues le POTENTIEL VIRAL pour cette plateforme. Tutoie le createur, sois concret, exploitable par un debutant.${factBlock}\n\nRÈGLE DE VÉRITÉ : ne cite JAMAIS un élément (sous-titres, texte à l'écran, effets) comme présent s'il n'est pas VISIBLE sur les images fournies. Si tu n'es pas sûr, n'en parle pas.\n\nCALIBRAGE (tres important): sois realiste, pas severe par defaut. Beaucoup de videos qui percent ont un hook tres fort — mets 8, 9 voire 10 quand c'est merite, n'hesite pas. Reperes: 9-10 = excellent (peut cartonner), 7-8 = bon, 5-6 = moyen, moins de 5 = faible. Juge le HOOK a la fois sur la 1re image ET la 1re phrase dite (si transcription dispo).\n\nLANGUE: detecte la langue parlee dans la video (via la transcription; sinon la description; sinon francais). Le champ 'caption' DOIT etre redige DANS CETTE LANGUE (c'est la description publiee avec la video : son audience doit la comprendre). En revanche 'tip' et 'subject' restent toujours en FRANCAIS (ce sont des infos pour le createur).\n\nDonne 4 notes sur 10 (une decimale possible):\n- accroche: force du hook visuel + verbal dans la 1re seconde\n- format: ${formatReal !== null ? `DÉJÀ FIXÉE à ${formatReal} (mesure réelle) — recopie-la` : "adaptation au format vertical court (cadrage, lisibilite, rythme visuel)"}\n- retention: capacite a garder le spectateur jusqu'au bout (utilise la transcription/le rythme)\n- legende: potentiel de la legende a generer du clic/engagement\nLe score global = moyenne ponderee (accroche compte double).\n\nHASHTAGS: choisis 4 a 6 hashtags (sans #), dans la langue de la video, en MELANGEANT (a) des hashtags lies au contenu et au sujet de CETTE video et (b) des hashtags fournis qui marchent deja sur le compte.\nRends UNIQUEMENT du JSON STRICT, rien d'autre:\n{\n "score": <0-10>,\n "subject": "<sujet de la video en max 4 mots, en francais>",\n "scores": { "accroche": <0-10>, "format": <0-10>, "retention": <0-10>, "legende": <0-10> },\n "tip": "<un seul conseil concret et actionnable en francais, max 20 mots>",\n "caption": "<une legende accrocheuse prete a publier dans la langue de la video, max 30 mots, 1-2 emojis si pertinent>",\n "hashtags": ["sansdiese"]\n}`;
    const userText = `Niche: ${niche || "inconnue"}. Duree: ${duration || "?"}s. Description fournie: "${caption || "(aucune)"}". Hashtags qui marchent deja sur le compte: ${topHashtags.join(", ") || "(aucun)"}.\nTranscription audio: ${transcript ? '"' + transcript + '"' : "(non disponible — juge surtout sur les images)"}.`;
    const content = [...imgs, { type: "text", text: userText }];

    let r = null, used = "", lastErr = "";
    for (const model of MODELS) {
      r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": AI_KEY, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({ model, max_tokens: 1200, system: sys, messages: [{ role: "user", content }] }),
      });
      if (r.ok) { used = model; break; }
      const t = await r.text();
      lastErr = "IA " + r.status + " (" + model + "): " + t.slice(0, 150);
      if (r.status !== 404) return j({ error: lastErr }, 500);
      r = null;
    }
    if (!r) return j({ error: "Aucun modele IA disponible. " + lastErr }, 500);

    const d = await r.json();
    let t = "";
    if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
    t = t.replace(/```json/g, "").replace(/```/g, "").trim();
    const s = t.indexOf("{"), e = t.lastIndexOf("}");
    let grade;
    try { grade = JSON.parse(s >= 0 && e > s ? t.slice(s, e + 1) : t); }
    catch { return j({ error: "Reponse IA illisible." }, 500); }

    const clamp = (x: unknown) => Math.max(0, Math.min(10, Math.round((Number(x) || 0) * 10) / 10));
    const sc = grade.scores || {};
    const scores = { accroche: clamp(sc.accroche), format: clamp(sc.format), retention: clamp(sc.retention), legende: clamp(sc.legende) };
    // ── ANCRAGE : la mesure PRIME sur l'avis de l'IA, et le score global est
    //    RECALCULÉ ici (accroche x2) — même pondération à chaque analyse, donc
    //    une vidéo objectivement améliorée remonte toujours. ──
    if (formatReal !== null) scores.format = formatReal;
    const global = clamp((scores.accroche * 2 + scores.format + scores.retention + scores.legende) / 5);
    const out = {
      score: global,
      subject: String(grade.subject ?? "ta video").slice(0, 60),
      scores,
      tip: String(grade.tip ?? "").slice(0, 200),
      caption: String(grade.caption ?? "").slice(0, 400),
      hashtags: Array.isArray(grade.hashtags) ? grade.hashtags.map((h: unknown) => String(h).replace(/^#/, "")).filter(Boolean).slice(0, 6) : [],
      used_audio: !!transcript,
      measured_format: formatReal,
      model: used,
    };
    return j({ success: true, grade: out }, 200);
  } catch (e) {
    return j({ error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});

function j(o: unknown, st = 200) {
  return new Response(JSON.stringify(o), { status: st, headers: { ...cors, "Content-Type": "application/json" } });
}
