// SKILLORA — daily-ideas : générateur d'idées de vidéos ADAPTÉ au type de contenu.
// Contrat d'API (inchangé, appelé par app.html) :
//   POST {platform, username}              -> {ideas:[...], date}          (génère si pas en cache)
//   POST {platform, username, cache_only}  -> {ideas:[...], date}          (jamais de génération)
//   POST {platform, username, history}     -> {history:[{idea_date,ideas}]}
// Cache : table public.daily_ideas (user_id, platform, username, idea_date, ideas) unique(user_id,platform,username,idea_date).
// Coût : 1 génération / compte / jour (Haiku). Le "plan" est déjà dans l'idée -> copier/voir le plan = 0 crédit.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MODEL = "claude-haiku-4-5";
// Version du moteur d'idées. On l'incrémente à chaque amélioration du prompt :
// les idées en cache d'une version antérieure sont régénérées automatiquement.
const GEN_V = 2;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const J = (o: unknown, s = 200) =>
  new Response(JSON.stringify(o), { status: s, headers: { ...corsHeaders, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return J({ error: "method", ideas: [] }, 405);
  try {
    const body = await req.json().catch(() => ({}));
    const platform = String(body.platform || "").trim();
    const username = String(body.username || "").replace(/^@/, "").trim();
    const wantHistory = !!body.history;
    const cacheOnly = !!body.cache_only;
    if (!platform || !username) return J({ error: "missing", ideas: [] });

    const SUPA_URL = Deno.env.get("SUPABASE_URL");
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!SUPA_URL || !SERVICE_KEY) return J({ error: "config", ideas: [] });
    const admin = createClient(SUPA_URL, SERVICE_KEY, { auth: { persistSession: false } });

    // Auth : on identifie l'utilisateur via son JWT (même schéma que analyze-script).
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    let userId: string | null = null;
    if (jwt) { try { const { data: u } = await admin.auth.getUser(jwt); userId = u?.user?.id || null; } catch (_e) { /* noop */ } }
    if (!userId) return J({ error: "auth", ideas: [] });

    const today = new Date().toISOString().slice(0, 10);

    // ===== Historique =====
    if (wantHistory) {
      const { data: rows } = await admin.from("daily_ideas")
        .select("idea_date, ideas")
        .eq("user_id", userId).eq("platform", platform).eq("username", username)
        .order("idea_date", { ascending: false }).limit(30);
      return J({ history: (rows || []).filter((r: any) => Array.isArray(r.ideas) && r.ideas.length) });
    }

    // ===== Cache du jour (avec garde de version) =====
    const { data: cached } = await admin.from("daily_ideas")
      .select("ideas").eq("user_id", userId).eq("platform", platform).eq("username", username)
      .eq("idea_date", today).maybeSingle();
    const fresh = cached && Array.isArray(cached.ideas) && cached.ideas.length &&
      cached.ideas[0] && cached.ideas[0]._v === GEN_V;
    if (fresh) return J({ ideas: cached!.ideas, date: today, cached: true });

    // cache_only : on ne dépense jamais de crédit ici.
    if (cacheOnly) return J({ ideas: [], date: today });

    // ===== Contexte (niche + signaux de type de contenu) =====
    const ctx = await resolveContext(admin, userId, platform, username);
    if (!ctx.niche && !ctx.best) {
      return J({ ideas: [], date: today, message: "Tes idées arrivent après une première analyse de ce compte. Actualise-le sur l'Accueil." });
    }
    if (!AI_KEY) return J({ ideas: [], date: today, message: "Idées indisponibles pour le moment." });

    // ===== Génération adaptée au type =====
    let ideas: any[] | null = null;
    try { ideas = await generateIdeas({ platform, ...ctx }, AI_KEY); }
    catch (_e) { return J({ ideas: [], date: today, message: "Idées indisponibles pour le moment. Réessaie plus tard." }); }
    if (!ideas || !ideas.length) return J({ ideas: [], date: today, message: "Idées indisponibles pour le moment." });

    ideas = ideas.map((it) => ({ ...it, _v: GEN_V }));
    await admin.from("daily_ideas").upsert(
      { user_id: userId, platform, username, idea_date: today, ideas },
      { onConflict: "user_id,platform,username,idea_date" },
    );
    return J({ ideas, date: today });
  } catch (e) {
    return J({ error: String((e as any)?.message ?? e), ideas: [] }, 200);
  }
});

// Résout la niche ET les signaux de type de contenu (profil + dernière analyse).
async function resolveContext(admin: any, userId: string, platform: string, username: string) {
  const uLow = username.toLowerCase();
  const { data: profs } = await admin.from("niche_profiles").select("*").eq("user_id", userId).eq("platform", platform);
  let prof: any = null;
  if (profs && profs.length) {
    const m = profs.filter((p: any) => String(p.account || "").toLowerCase().replace(/^@/, "") === uLow);
    prof = m.find((p: any) => p.is_active) || m.find((p: any) => p.is_connected) || m[0] || null;
  }
  const { data: an } = await admin.from("analyses").select("summary")
    .eq("user_id", userId).eq("platform", platform).eq("username", username)
    .order("created_at", { ascending: false }).limit(1).maybeSingle();
  const s: any = an?.summary ?? {};
  const ins: any = s.insights ?? {};
  const best = (s.best_videos || []).slice(0, 3)
    .map((v: any) => `"${(v.description || "").slice(0, 90)}" — ${v.views || 0} vues`).join("\n");
  return {
    niche: (prof && prof.niche) || ins.niche || "",
    contentType: ins.content_type || (prof && prof.format) || "",
    productionKind: ins.production_kind || "",
    needsScript: (typeof ins.needs_script === "boolean") ? ins.needs_script : null,
    face: (prof && prof.face) || "",
    profTags: (prof && Array.isArray(prof.tags)) ? prof.tags.join(" ") : "",
    best,
    formula: ins.formula ? JSON.stringify(ins.formula) : "",
    patterns: (ins.patterns || []).join(" | "),
  };
}

// Détecte le "mode" d'idéation à partir des signaux du compte.
function detectMode(ctx: any): "curation" | "news" | "visual" | "original" {
  const hay = `${ctx.niche} ${ctx.contentType} ${ctx.productionKind} ${ctx.profTags}`.toLowerCase();
  if (ctx.needsScript === false || /clip|clipp|compil|repost|extrait|highlight|best ?of|r[eé]act|reaction|gameplay|montage de|zapping|zap\b|moments?/.test(hay)) return "curation";
  if (/actu|news|info|journal|politiqu|[eé]conomi|sport|foot|basket|tennis|buzz|breaking|tendance|trend/.test(hay)) return "news";
  if (/nature|paysage|voyage|travel|tourism|aesthetic|satisfying|asmr|relax|ambiance|cin[eé]matic|drone|paysages|calm|lofi|slow/.test(hay)) return "visual";
  return "original";
}

function modeBlock(mode: string): string {
  if (mode === "curation") {
    return `Ce compte fait de la CURATION / CLIPPING : il ne tourne pas lui-même, il RE-MONTE des séquences qui existent déjà.
- "title" = l'angle du clip (ce qui accroche).
- "hook" = le texte à l'écran des 2 premières secondes.
- "source" = OÙ trouver la VRAIE séquence : nomme des chaînes / émissions / podcasts / streamers RÉELS et connus dans cette niche, PLUS 2-3 requêtes de recherche précises (YouTube/TikTok) qui ramènent vraiment des résultats. INTERDIT d'inventer un événement précis ("X a refusé 1M$"), un chiffre ou une citation.
- "structure" = les étapes de MONTAGE (repérer le moment fort, découper, sous-titres, zoom/punch, texte, rythme, fin).
Donne des ANGLES de clip qui marchent dans la niche, sans prétendre qu'un fait précis a eu lieu.`;
  }
  if (mode === "news") {
    return `Ce compte fait de l'ACTUALITÉ / tendance. Tu n'as PAS accès au web en direct : n'invente AUCUNE actu, aucun chiffre, aucune citation.
- Donne des ANGLES / formats réutilisables sur les sujets chauds récurrents de la niche.
- "hook" = un gabarit d'accroche à remplir avec le vrai sujet du jour.
- "source" = où prendre le VRAI sujet aujourd'hui (ex: la une de sources réelles de la niche, Google Trends, l'onglet Tendances de la plateforme) et comment l'adapter.
- "structure" = comment monter la vidéo une fois le vrai sujet choisi.
Fournis le SQUELETTE + où brancher le réel, jamais un faux fait.`;
  }
  if (mode === "visual") {
    return `Ce compte fait du VISUEL (nature / voyage / aesthetic / ASMR), souvent sans parole.
- "title" = le concept visuel.
- "hook" = le tout premier plan / texte qui arrête le scroll.
- "source" = où trouver les images : types de LIEUX réels à filmer, banques de stock libres, OU un prompt concret pour GÉNÉRER la séquence en IA (si pertinent pour la niche).
- "structure" = plan de tournage/montage (enchaînement de plans, transitions, musique/ambiance, format, durée idéale).`;
  }
  return `Ce compte CRÉE lui-même son contenu (storytime / narration / IA générative / éducation / motivation). Ici tu PEUX proposer des concepts originaux à produire, car le créateur les fabrique.
- "hook" = l'accroche des 3 premières secondes.
- "structure" = le déroulé du script / de la vidéo, étape par étape.
- "source" = l'angle ou la source d'inspiration (n'a pas besoin d'exister tel quel).`;
}

async function generateIdeas(ctx: any, key: string) {
  const mode = detectMode(ctx);
  const system = `Tu es le moteur d'idéation Skillora pour créateurs de vidéos courtes (TikTok/Reels/Shorts). Tu tutoies. Zéro emoji, zéro blabla. Réponds en FRANÇAIS.
Objectif : chaque idée doit être RÉELLEMENT réalisable AUJOURD'HUI par CE créateur, selon SA façon de faire des vidéos.

RÈGLES DE VÉRITÉ (les plus importantes, ne jamais les enfreindre) :
1. N'invente JAMAIS un fait, un événement, une citation ou un chiffre présenté comme réel (ex: "il a refusé 1M$"). Ces vidéos n'existent pas et font perdre son temps au créateur.
2. Si l'idée dépend d'une séquence qui doit DÉJÀ EXISTER (curation/clipping, réaction, actu) : ne référence que des SOURCES RÉELLES et vérifiables + une stratégie de recherche concrète (mots-clés qui ramènent vraiment des résultats). Jamais un événement fabriqué.
3. Si le créateur FABRIQUE lui-même sa vidéo (storytime, narration, IA, éducation) : tu peux proposer des concepts/angles originaux à créer.
4. Reste STRICTEMENT dans la niche du créateur. Idées variées entre elles.

MODE POUR CE COMPTE : ${mode}
${modeBlock(mode)}

Produis 4 idées NOUVELLES. "viral_score" = potentiel réaliste 1-10 (la plupart 6-9).
Réponds en JSON STRICT, rien d'autre :
{"ideas":[{"title":"..","viral_score":<1-10>,"hook":"..","angle":"..","structure":["..","..",".."],"source":"..","hashtags":["..",".."],"format":"TikTok|Reels|Shorts"}]}
Le SENS de "structure" et "source" suit le MODE ci-dessus (tournage vs montage, lieux vs vraies sources).`;

  const userMsg = `Plateforme: ${ctx.platform}
Niche (obligatoire): ${ctx.niche || "(déduire des vidéos ci-dessous)"}
Type de contenu: ${ctx.contentType || "(inconnu)"}
Style de production: ${ctx.productionKind || "(inconnu)"}
A besoin d'un script: ${ctx.needsScript === null ? "(inconnu)" : (ctx.needsScript ? "oui" : "non")}
Visage montré: ${ctx.face || "(non précisé)"}
Mots-clés: ${ctx.profTags || "(aucun)"}
Vidéos de ce compte qui ont marché:
${ctx.best || "(aucune)"}
Formule gagnante: ${ctx.formula || "(aucune)"}
Leviers récurrents: ${ctx.patterns || "(aucun)"}

Donne 4 idées prêtes à exécuter aujourd'hui, STRICTEMENT dans la niche, en respectant le MODE et les RÈGLES DE VÉRITÉ.`;

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({ model: MODEL, max_tokens: 2600, system, messages: [{ role: "user", content: userMsg }] }),
  });
  if (!r.ok) throw new Error(`Anthropic ${r.status}`);
  const d = await r.json();
  let t = "";
  if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
  t = t.replace(/```json/g, "").replace(/```/g, "").trim();
  const a = t.indexOf("{"), b = t.lastIndexOf("}");
  const parsed = JSON.parse(a >= 0 && b > a ? t.slice(a, b + 1) : t);
  const ideas = Array.isArray(parsed) ? parsed : (parsed.ideas || []);
  // Normalisation défensive des champs attendus par le frontend.
  return ideas.slice(0, 6).map((it: any) => ({
    title: String(it.title || "Idée"),
    viral_score: Number(it.viral_score) || 0,
    hook: String(it.hook || ""),
    angle: String(it.angle || ""),
    structure: Array.isArray(it.structure) ? it.structure.map((x: any) => String(x)) : [],
    source: String(it.source || ""),
    hashtags: Array.isArray(it.hashtags) ? it.hashtags.map((x: any) => String(x)) : [],
    format: String(it.format || "TikTok"),
  }));
}
