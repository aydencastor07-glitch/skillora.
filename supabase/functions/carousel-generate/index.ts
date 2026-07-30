// SKILLORA — carousel-generate : écrit un NOUVEAU carrousel dans le style appris.
//
// Entrée : un template (la recette apprise par carousel-analyze) + un sujet.
// Sortie : le contenu complet du carrousel — le texte de chaque slide, le prompt
// d'image de chaque slide, la légende et les hashtags — puis un job pour le worker,
// qui fabrique les images et les assemble au format de la recette.
//
// Le style ne vient JAMAIS d'ici : il vient de la recette. Cette fonction ne fait
// qu'appliquer les règles écrites dans la recette à un nouveau sujet.
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
  "claude-3-5-sonnet-20240620",
];

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

type Slide = Record<string, any>;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const AI_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!AI_KEY) return j({ success: false, error: "Clé IA manquante." }, 500);

    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } },
    );
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u?.user?.id ?? null;
    if (!userId) return j({ success: false, error: "Non authentifié." }, 401);

    const body = await req.json().catch(() => ({}));
    const templateId = String(body.template_id || "");
    const sujet = String(body.sujet || "").slice(0, 400);
    const langue = String(body.langue || "").slice(0, 10);
    const nb = Math.max(1, Math.min(12, Number(body.combien) || 1)); // combien de variantes
    const rendre = body.rendre !== false; // false = on veut juste le texte, pas les images
    if (!templateId) return j({ success: false, error: "Choisis un modèle de carrousel." }, 400);
    if (!sujet) return j({ success: false, error: "Donne un sujet." }, 400);

    const { data: tpl } = await admin.from("carousel_templates")
      .select("id,nom,recette,user_id").eq("id", templateId).eq("user_id", userId).maybeSingle();
    if (!tpl) return j({ success: false, error: "Modèle introuvable." }, 404);

    const recette = (tpl.recette || {}) as Record<string, any>;
    const slidesRecette: Slide[] = Array.isArray(recette.slides) ? recette.slides : [];
    if (!slidesRecette.length) return j({ success: false, error: "Ce modèle est vide, réanalyse ton carrousel." }, 400);
    const ecriture = (recette.ecriture || {}) as Record<string, any>;
    const lg = langue || String(ecriture.langue || "fr");

    // On donne au rédacteur le PLAN de la recette, slide par slide, avec l'exemple
    // d'origine ET la règle. L'exemple apprend le ton ; la règle empêche de le recopier.
    const plan = slidesRecette.map((s, i) => {
      const t = (s.texte || {}) as Record<string, any>;
      return `Slide ${s.n ?? i + 1} — rôle « ${s.role ?? "?"} », gabarit « ${s.gabarit ?? "titre_seul"} »
  Règle : ${s.regle ?? "(aucune)"}
  Exemple d'origine (le TON, pas le contenu) : titre = "${t.titre ?? ""}"${t.corps ? `, corps = "${t.corps}"` : ""}${t.note ? `, note = "${t.note}"` : ""}`;
    }).join("\n");

    const sys = `Tu es le rédacteur de carrousels de Skillora.

On te donne le STYLE d'un carrousel qui existe déjà (fabriqué à la main par le créateur) et un
SUJET nouveau. Tu écris un carrousel neuf sur ce sujet, dans exactement ce style.

RÈGLE ABSOLUE : tu ne recopies pas les exemples. Ils sont là pour t'apprendre le ton, le rythme
et la longueur — pas pour être réutilisés. Si une phrase de ta sortie ressemble à un exemple à
plus de la moitié, réécris-la.

Le carrousel fait ${slidesRecette.length} slides, dans cet ordre, avec ces rôles :
${plan}

Contraintes d'écriture (elles viennent du carrousel d'origine, respecte-les au mot près) :
- Langue : ${lg}
- Ton : ${ecriture.ton ?? "direct"}
- Longueur des titres : ${ecriture.longueur_titre ?? "4-8 mots"}
- Longueur des corps : ${ecriture.longueur_corps ?? "12-25 mots"}
- Emojis : ${ecriture.emojis ?? "jamais"}
${Array.isArray(ecriture.interdits) && ecriture.interdits.length ? `- À ne jamais écrire : ${ecriture.interdits.join(", ")}` : ""}

IMAGES — pour chaque slide, écris "image_prompt" : un prompt de génération d'image, EN ANGLAIS,
qui produit une image cohérente avec le style visuel du carrousel d'origine, décrit ici :
« ${recette.style_images ?? "photo réaliste, lumière naturelle"} ».
Le prompt décrit une SCÈNE, jamais du texte : l'image ne doit contenir AUCUN mot, AUCUNE lettre,
AUCUN logo — le texte est incrusté après, par le moteur de rendu. Précise le cadrage vertical.
Si la slide ne porte pas d'image dans ce style, mets image_prompt à null.

La 1re slide est le hook : c'est elle qui décide si le carrousel est lu. Elle doit créer une
tension en une phrase — une promesse, une contradiction ou un chiffre. Jamais une généralité.

Réponds UNIQUEMENT en JSON STRICT, sans texte autour, sans bloc de code :
{
  "titre_interne": "<nom court de ce carrousel, pour le créateur>",
  "slides": [
    { "n": 1, "titre": "<...>", "corps": "<ou null>", "note": "<ou null>", "image_prompt": "<en anglais, ou null>" }
  ],
  "legende": "<légende prête à publier, dans le style de la légende d'origine>",
  "hashtags": ["sansdiese"]
}`;

    async function ecrireUn(variante: number) {
      const invite = `Sujet : ${sujet}${
        variante > 0 ? `\n\nC'est la variante n°${variante + 1} : prends un ANGLE DIFFÉRENT des précédentes sur le même sujet — autre entrée en matière, autres exemples.` : ""
      }`;
      let r: Response | null = null, derniere = "";
      for (const model of MODELS) {
        r = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-api-key": AI_KEY!, "anthropic-version": "2023-06-01" },
          body: JSON.stringify({
            model, max_tokens: 3000, system: sys,
            messages: [{ role: "user", content: invite }],
          }),
        });
        if (r.ok) break;
        derniere = "IA " + r.status + ": " + (await r.text()).slice(0, 160);
        if (r.status !== 404) throw new Error(derniere);
        r = null;
      }
      if (!r) throw new Error("Aucun modèle IA disponible. " + derniere);
      const d = await r.json();
      let t = "";
      if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
      t = t.replace(/```json/g, "").replace(/```/g, "").trim();
      const a = t.indexOf("{"), z = t.lastIndexOf("}");
      const out = JSON.parse(a >= 0 && z > a ? t.slice(a, z + 1) : t);

      // On rattache chaque slide écrite à sa slide de recette : c'est le gabarit de la
      // recette qui commande le rendu, pas ce que l'IA a bien voulu renvoyer.
      const ecrites: Slide[] = Array.isArray(out.slides) ? out.slides : [];
      const slides = slidesRecette.map((modele, i) => {
        const e = ecrites[i] || {};
        return {
          n: i + 1,
          role: modele.role ?? null,
          gabarit: modele.gabarit ?? "titre_seul",
          titre: String(e.titre ?? "").slice(0, 220),
          corps: e.corps ? String(e.corps).slice(0, 400) : null,
          note: e.note ? String(e.note).slice(0, 200) : null,
          image_prompt: e.image_prompt ? String(e.image_prompt).slice(0, 700) : null,
        };
      });
      return {
        titre_interne: String(out.titre_interne ?? sujet).slice(0, 80),
        slides,
        legende: String(out.legende ?? "").slice(0, 2200),
        hashtags: Array.isArray(out.hashtags)
          ? out.hashtags.map((h: unknown) => String(h).replace(/^#/, "")).filter(Boolean).slice(0, 8)
          : [],
      };
    }

    const variantes = [];
    for (let i = 0; i < nb; i++) variantes.push(await ecrireUn(i));

    // Sans rendu demandé, on rend juste le texte : utile pour relire avant de dépenser
    // des images (chaque slide générée coûte).
    if (!rendre) return j({ success: true, template: tpl.nom, carrousels: variantes });

    // Un job par variante : le worker fabrique les images puis assemble les slides.
    const jobs = [];
    for (const v of variantes) {
      const { data: job, error } = await admin.from("video_jobs").insert({
        user_id: userId,
        status: "queued",
        context: { mode: "carrousel", template_id: tpl.id, sujet, langue: lg },
        plan: { carrousel: { recette, contenu: v } },
      }).select("id,status").single();
      if (error) return j({ success: false, error: "File d'attente indisponible : " + error.message }, 500);
      jobs.push({ id: job.id, titre: v.titre_interne, slides: v.slides.length });
    }

    return j({ success: true, template: tpl.nom, jobs, carrousels: variantes });
  } catch (e) {
    return j({ success: false, error: "Erreur serveur: " + ((e as Error)?.message ?? String(e)) }, 500);
  }
});
