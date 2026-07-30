// SKILLORA — carousel-analyze : apprend la RECETTE d'un carrousel fait à la main.
//
// Le créateur fabrique UN carrousel à la main (6 images par exemple), l'envoie ici,
// et cette fonction le décortique en une recette JSON : format, couleurs, polices,
// marges, place de l'image, rôle de chaque slide, règles d'écriture, style de légende.
//
// Cette recette est le SEUL endroit où vit le design. La génération (carousel-generate)
// et le rendu (worker) ne connaissent aucun style en dur : ils lisent la recette.
// Résultat : on change de style en renvoyant un nouveau carrousel, pas en codant.
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

const MAX_SLIDES = 12;
const MAX_OCTETS = 4_500_000; // limite Anthropic par image

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}

// Accepte une data-URL ou une URL publique ; renvoie le bloc image Anthropic.
async function versImage(src: string) {
  const dataUrl = src.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
  if (dataUrl) return { type: "image", source: { type: "base64", media_type: dataUrl[1], data: dataUrl[2] } };
  if (!/^https:\/\//i.test(src)) return null;
  const r = await fetch(src);
  if (!r.ok) return null;
  const type = (r.headers.get("content-type") || "image/jpeg").split(";")[0].trim();
  if (!/^image\//.test(type)) return null;
  const buf = new Uint8Array(await r.arrayBuffer());
  if (!buf.length || buf.length > MAX_OCTETS) return null;
  let bin = "";
  for (let i = 0; i < buf.length; i += 8192) bin += String.fromCharCode(...buf.subarray(i, i + 8192));
  return { type: "image", source: { type: "base64", media_type: type, data: btoa(bin) } };
}

// ── LE CONTRAT DE RENDU ───────────────────────────────────────────────────────
// Ce schéma n'est pas décoratif : chaque champ est LU par le moteur de rendu.
// Si tu ajoutes un champ ici, ajoute-le aussi dans le gabarit HTML du worker.
const SCHEMA = `{
  "nom": "<nom court du style, 2-4 mots>",
  "format": { "largeur": <px>, "hauteur": <px> },
  "nb_slides": <entier>,
  "couleurs": {
    "fond": "#rrggbb",
    "texte": "#rrggbb",
    "accent": "#rrggbb",
    "secondaire": "#rrggbb",
    "voile_opacite": <0 a 1, assombrissement pose sur l'image de fond>
  },
  "polices": {
    "titre":  { "famille": "<Sora|Inter|Fraunces|Anton|Archivo|DM Sans|Playfair Display>", "graisse": <300-900>, "taille": <px>, "interligne": <1.0-1.6>, "interlettre": <-0.05 a 0.1 em>, "casse": "aucune|majuscules", "align": "gauche|centre|droite" },
    "corps":  { "famille": "<...>", "graisse": <300-900>, "taille": <px>, "interligne": <1.0-1.8>, "interlettre": <...>, "casse": "aucune|majuscules", "align": "gauche|centre|droite" },
    "note":   { "famille": "<...>", "graisse": <300-900>, "taille": <px>, "interligne": <1.0-1.8>, "interlettre": <...>, "casse": "aucune|majuscules", "align": "gauche|centre|droite" }
  },
  "image": {
    "presence": "fond|vignette|aucune",
    "ajustement": "cover|contain",
    "coins": <rayon px>,
    "filtre": "aucun|noir_et_blanc|desature|chaud|froid",
    "part_hauteur": <0 a 1, part de la slide occupee par l'image quand presence=vignette>
  },
  "cadre": {
    "marge_x": <px>, "marge_y": <px>,
    "position_texte": "haut|centre|bas",
    "fond_bloc": "aucun|carte|bandeau",
    "espace_titre_corps": <px>
  },
  "decor": {
    "numero_slide": <true|false>, "position_numero": "haut-gauche|haut-droite|bas-gauche|bas-droite",
    "pseudo": "<@pseudo affiche, ou null>", "position_pseudo": "haut-gauche|haut-droite|bas-gauche|bas-droite",
    "fleche_suivant": <true|false>
  },
  "style_images": "<description PRECISE du type d'images utilisees : photo reelle / capture d'ecran / illustration, sujet, lumiere, palette, cadrage. Assez precise pour servir de prompt de generation.>",
  "slides": [
    { "n": 1, "role": "hook|probleme|preuve|etape|exemple|conseil|cta",
      "gabarit": "titre_seul|titre_corps|image_pleine_titre|citation|liste|cta",
      "texte": { "titre": "<texte exact lu sur la slide>", "corps": "<ou null>", "note": "<ou null>" },
      "regle": "<la regle a respecter pour reecrire CETTE slide : longueur, angle, ce qu'elle doit provoquer>" }
  ],
  "ecriture": {
    "langue": "<fr|en|...>",
    "ton": "<description du ton en une phrase>",
    "longueur_titre": "<ex: 4-8 mots>",
    "longueur_corps": "<ex: 12-25 mots>",
    "emojis": "jamais|rare|souvent",
    "interdits": ["<tournures a ne jamais reprendre>"]
  },
  "legende": {
    "exemple": "<une legende prete a publier dans ce style>",
    "structure": "<comment elle est batie>",
    "hashtags": ["sansdiese"]
  }
}`;

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
    const sources: string[] = Array.isArray(body.slides) ? body.slides.map(String).slice(0, MAX_SLIDES) : [];
    const nom = String(body.nom || "").slice(0, 60);
    const notes = String(body.notes || "").slice(0, 800); // ce que le créateur veut préciser
    if (sources.length < 2) {
      return j({ success: false, error: "Envoie au moins 2 slides du carrousel (dans l'ordre)." }, 400);
    }

    const imgs = [];
    for (const s of sources) {
      const bloc = await versImage(s).catch(() => null);
      if (bloc) imgs.push(bloc);
    }
    if (imgs.length < 2) {
      return j({ success: false, error: "Images illisibles ou trop lourdes (4,5 Mo max par slide)." }, 400);
    }

    const sys = `Tu es le moteur d'apprentissage de style de Skillora.

On te donne les slides d'UN carrousel fabriqué à la main, DANS L'ORDRE (la 1re image = slide 1).
Ta mission : en extraire une RECETTE REPRODUCTIBLE, assez précise pour qu'un moteur de rendu
puisse fabriquer DIX AUTRES carrousels dans exactement le même style, avec d'autres images et
d'autres textes.

Tu ne décris pas, tu MESURES. Deux exigences absolues :

1. LES VALEURS SONT DES NOMBRES. Estime les tailles en pixels en supposant que la slide fait la
   taille que tu déclares dans "format". Si un titre occupe environ un dixième de la hauteur,
   sa taille est environ un dixième de la hauteur. Ne réponds jamais "grand" ou "moyen".

2. LES COULEURS SONT DES CODES HEX exacts, prélevés sur l'image. Regarde le fond, regarde le
   texte, regarde ce qui ressort (accent). Si le fond est une photo assombrie, mets la couleur
   dominante de la photo dans "fond" et l'assombrissement dans "voile_opacite".

Pour "slides", donne UNE entrée par slide reçue, dans l'ordre, avec le texte EXACT que tu lis
dessus (recopié au caractère près, c'est ce qui apprend le ton) et surtout "regle" : la consigne
de réécriture de cette slide précise. La règle est ce qui compte le plus — c'est elle qui sera
donnée au rédacteur pour produire la variante. Elle doit dire à quoi sert la slide et ce qu'elle
doit provoquer chez le lecteur, pas seulement combien de mots elle fait.

"style_images" doit être assez précis pour servir tel quel de prompt à un générateur d'images.

Réponds UNIQUEMENT en JSON STRICT, sans texte autour, sans bloc de code, exactement cette forme :
${SCHEMA}`;

    const texteUser = `Carrousel de ${imgs.length} slides, dans l'ordre.${
      nom ? ` Nom donné par le créateur : "${nom}".` : ""
    }${notes ? `\nPrécisions du créateur (elles priment sur ce que tu devines) : "${notes}"` : ""}`;

    let r: Response | null = null, used = "", derniere = "";
    for (const model of MODELS) {
      r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": AI_KEY, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({
          model, max_tokens: 4000, system: sys,
          messages: [{ role: "user", content: [...imgs, { type: "text", text: texteUser }] }],
        }),
      });
      if (r.ok) { used = model; break; }
      derniere = "IA " + r.status + " (" + model + "): " + (await r.text()).slice(0, 160);
      if (r.status !== 404) return j({ success: false, error: derniere }, 500);
      r = null;
    }
    if (!r) return j({ success: false, error: "Aucun modèle IA disponible. " + derniere }, 500);

    const d = await r.json();
    let t = "";
    if (Array.isArray(d.content)) for (const b of d.content) if (b.type === "text") t += b.text;
    t = t.replace(/```json/g, "").replace(/```/g, "").trim();
    const a = t.indexOf("{"), z = t.lastIndexOf("}");
    let recette: Record<string, unknown>;
    try { recette = JSON.parse(a >= 0 && z > a ? t.slice(a, z + 1) : t); }
    catch { return j({ success: false, error: "Réponse IA illisible." }, 500); }

    // ── Garde-fous : une recette incomplète casserait le rendu en silence. ──
    const fmt = (recette.format || {}) as Record<string, number>;
    const L = Math.round(Number(fmt.largeur) || 1080);
    const H = Math.round(Number(fmt.hauteur) || 1350);
    recette.format = { largeur: Math.min(2000, Math.max(600, L)), hauteur: Math.min(2600, Math.max(600, H)) };
    const slides = Array.isArray(recette.slides) ? recette.slides : [];
    recette.nb_slides = slides.length || imgs.length;
    if (!slides.length) return j({ success: false, error: "L'IA n'a pas su lire les slides." }, 500);
    if (nom) recette.nom = nom;

    const { data: ligne, error: err } = await admin.from("carousel_templates").insert({
      user_id: userId,
      nom: String(recette.nom || nom || "Mon carrousel").slice(0, 60),
      recette,
      slides_source: sources.filter((s) => /^https:\/\//i.test(s)).slice(0, MAX_SLIDES),
    }).select("id,nom,recette,created_at").single();
    if (err) return j({ success: false, error: "Enregistrement impossible : " + err.message }, 500);

    return j({ success: true, template: ligne, model: used });
  } catch (e) {
    return j({ success: false, error: "Erreur serveur: " + ((e as Error)?.message ?? String(e)) }, 500);
  }
});
