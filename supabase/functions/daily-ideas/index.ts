// SKILLORA — daily-ideas v8 : idées ADAPTÉES au type de contenu (curation / actu / visuel / original).
// Même plomberie que la v7 (auth anon + Authorization, cache/jour, historique, cache_only).
// Règle anti-invention stricte. Versioning GEN_V : les idées en cache d'une version antérieure
// sont régénérées au premier affichage (amélioration immédiate). 1 génération / compte / jour.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MODEL = "claude-haiku-4-5";
const GEN_V = 2; // incrémenter à chaque amélioration du prompt

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const j = (o: unknown, s = 200) =>
  new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });

function normalizeScores(ideas: any) {
  if (!Array.isArray(ideas)) return [];
  return ideas.map((it: any) => ({ ...it, viral_score: Math.max(0, Math.min(10, Number(it?.viral_score) || 0)) }));
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const platform = (body.platform ?? "tiktok").toLowerCase().trim();
    const username = (body.username ?? "").trim().replace(/^@/, "");
    if (!username) return j({ error: "username requis." }, 400);

    // Historique : dernières journées d'idées de ce compte.
    if (body.history === true) {
      const { data } = await supabase.from("daily_ideas")
        .select("idea_date, ideas").eq("user_id", user.id).eq("platform", platform).eq("username", username)
        .order("idea_date", { ascending: false }).limit(10);
      const hist = (data || []).map((row: any) => ({ ...row, ideas: normalizeScores(row.ideas) }));
      return j({ success: true, history: hist }, 200);
    }

    const today = new Date().toISOString().slice(0, 10);

    // Cache du jour (avec garde de version) : aucune dépense IA si déjà à jour.
    const { data: cached } = await supabase.from("daily_ideas")
      .select("*").eq("user_id", user.id).eq("platform", platform).eq("username", username)
      .eq("idea_date", today).maybeSingle();
    const fresh = cached && Array.isArray(cached.ideas) && cached.ideas.length &&
      cached.ideas[0] && cached.ideas[0]._v === GEN_V;
    if (fresh) return j({ success: true, ideas: normalizeScores(cached.ideas), date: today }, 200);

    // cache_only : on ne génère jamais ici (0 crédit).
    if (body.cache_only === true) return j({ success: true, ideas: [], date: today }, 200);

    // Contexte : niche + signaux de type de contenu (profil + dernière analyse).
    const ctx = await resolveContext(supabase, user.id, platform, username);
    if (!ctx.niche && !ctx.best) {
      return j({ success: true, ideas: [], date: today, message: "Tes idées arrivent après une première analyse de ce compte. Actualise-le sur l'Accueil." }, 200);
    }
    if (!AI_KEY) return j({ success: true, ideas: [], date: today, message: "Idées indisponibles pour le moment." }, 200);

    let ideas: any[] | null = null;
    try { ideas = await generateIdeas({ platform, ...ctx }, AI_KEY); }
    catch (_e) { return j({ success: true, ideas: [], date: today, message: "Idées indisponibles pour le moment. Réessaie plus tard." }, 200); }
    if (!ideas || !ideas.length) return j({ success: true, ideas: [], date: today, message: "Idées indisponibles pour le moment." }, 200);

    ideas = ideas.map((it) => ({ ...it, _v: GEN_V }));
    await supabase.from("daily_ideas").upsert(
      { user_id: user.id, platform, username, idea_date: today, ideas },
      { onConflict: "user_id,platform,username,idea_date" },
    );
    return j({ success: true, ideas, date: today }, 200);
  } catch (e) {
    return j({ error: String((e as any)?.message ?? e) }, 200);
  }
});

// Niche + type de contenu (les requêtes tournent sous l'identité de l'utilisateur -> RLS).
async function resolveContext(supabase: any, userId: string, platform: string, username: string) {
  const uLow = username.toLowerCase();
  const { data: profs } = await supabase.from("niche_profiles").select("*").eq("user_id", userId).eq("platform", platform);
  let prof: any = null;
  if (profs && profs.length) {
    const m = profs.filter((p: any) => String(p.account || "").toLowerCase().replace(/^@/, "") === uLow);
    prof = m.find((p: any) => p.is_active) || m.find((p: any) => p.is_connected) || m[0] || null;
  }
  const { data: an } = await supabase.from("analyses").select("summary")
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
- "title" = l'angle du clip.
- "hook" = le texte à l'écran des 2 premières secondes.
- "source" = OÙ trouver la VRAIE séquence : chaînes / émissions / podcasts / streamers RÉELS connus dans cette niche, + 2-3 requêtes de recherche précises qui ramènent vraiment des résultats. INTERDIT d'inventer un événement précis, un chiffre ou une citation.
- "structure" = les étapes de MONTAGE (repérer le moment fort, découper, sous-titres, zoom/punch, texte, rythme).`;
  }
  if (mode === "news") {
    return `Ce compte fait de l'ACTUALITÉ / tendance. Tu n'as PAS accès au web en direct : n'invente AUCUNE actu ni chiffre.
- ANGLES / formats réutilisables sur les sujets chauds de la niche.
- "hook" = gabarit d'accroche à remplir avec le vrai sujet du jour.
- "source" = où prendre le VRAI sujet aujourd'hui (une de sources réelles, Google Trends, onglet Tendances) et comment l'adapter.
- "structure" = comment monter une fois le vrai sujet choisi.`;
  }
  if (mode === "visual") {
    return `Ce compte fait du VISUEL (nature / voyage / aesthetic / ASMR), souvent sans parole.
- "title" = le concept visuel.
- "hook" = le premier plan / texte qui arrête le scroll.
- "source" = où trouver les images : types de LIEUX réels à filmer, banques de stock libres, OU un prompt pour GÉNÉRER en IA.
- "structure" = plan de tournage/montage (plans, transitions, musique/ambiance, format, durée).`;
  }
  return `Ce compte CRÉE lui-même son contenu (storytime / narration / IA / éducation / motivation). Tu PEUX proposer des concepts originaux.
- "hook" = accroche des 3 premières secondes.
- "structure" = déroulé du script / de la vidéo.
- "source" = angle ou source d'inspiration.`;
}

async function generateIdeas(ctx: any, key: string) {
  const mode = detectMode(ctx);
  const system = `Tu es le moteur d'idéation Skillora pour créateurs de vidéos courtes. Tu tutoies. Zéro emoji. Réponds en FRANÇAIS.
Chaque idée doit être RÉELLEMENT réalisable AUJOURD'HUI par CE créateur.

RÈGLES DE VÉRITÉ (ne jamais enfreindre) :
1. N'invente JAMAIS un fait, événement, citation ou chiffre présenté comme réel (ex: "il a refusé 1M$").
2. Si l'idée dépend d'une séquence qui doit DÉJÀ EXISTER (clipping, réaction, actu) : ne référence que des SOURCES RÉELLES + une stratégie de recherche concrète. Jamais un événement fabriqué.
3. Si le créateur FABRIQUE lui-même (storytime, narration, IA, éducation) : concepts originaux permis.
4. Reste STRICTEMENT dans la niche.

MODE : ${mode}
${modeBlock(mode)}

Produis 4 idées NOUVELLES. "viral_score" 1-10 (la plupart 6-9).
JSON STRICT :
{"ideas":[{"title":"..","viral_score":<1-10>,"hook":"..","angle":"..","structure":["..","..",".."],"source":"..","hashtags":["..",".."],"format":"TikTok|Reels|Shorts"}]}`;
  const userMsg = `Plateforme: ${ctx.platform}
Niche: ${ctx.niche || "(déduire)"}
Type de contenu: ${ctx.contentType || "(inconnu)"}
Style de production: ${ctx.productionKind || "(inconnu)"}
A besoin d'un script: ${ctx.needsScript === null ? "(inconnu)" : (ctx.needsScript ? "oui" : "non")}
Visage: ${ctx.face || "(non précisé)"}
Mots-clés: ${ctx.profTags || "(aucun)"}
Vidéos qui ont marché:
${ctx.best || "(aucune)"}
Formule: ${ctx.formula || "(aucune)"}
Leviers: ${ctx.patterns || "(aucun)"}

Donne 4 idées prêtes à exécuter aujourd'hui, dans la niche, en respectant le MODE et les RÈGLES.`;
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
