import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// Limites d'analyses de script par jour, par plan (miroir du frontend)
const PLAN_LIMITS: Record<string, number> = { starter: 3, growth: 7, elite: 20 };
function planLimit(plan: string) { return PLAN_LIMITS[plan] != null ? PLAN_LIMITS[plan] : 3; }

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Marque invisible : note + plateforme encodees (notation stable par plateforme).
// IMPORTANT : ce sont des caracteres ZERO-WIDTH (largeur nulle, invisibles a l'ecran).
// On les ecrit en sequences \u pour qu'ils restent EXACTS quoi qu'il arrive.
const ZW: Record<number, string> = {
  0: "​", 1: "‌", 2: "‍", 3: "⁠", 4: "⁡",
  5: "⁢", 6: "⁣", 7: "⁤", 8: "﻿", 9: "͏",
};
const ZW_KEYS = Object.values(ZW);
const SEP = "⁦"; // separateur invisible entre note et plateforme
const MARK_START = "​⁠​"; // signature Skillora

const PLATFORM_CODES: Record<string, number> = { tiktok: 0, tiktok_shop: 1, reels: 2, shorts: 3, youtube_long: 4, instagram_post: 5 };

// encode note (ex 8.5 -> "85") + code plateforme
function encodeStamp(note: number, platform: string) {
  const n = Math.round(Number(note) * 10).toString();
  const pc = (PLATFORM_CODES[platform] != null ? PLATFORM_CODES[platform] : 0).toString();
  let out = MARK_START;
  for (const ch of n) out += ZW[Number(ch)];
  out += SEP;
  for (const ch of pc) out += ZW[Number(ch)];
  out += MARK_START;
  return out;
}
// retourne { note, platformCode } ou null
function decodeStamp(text: string) {
  const i = text.indexOf(MARK_START);
  if (i < 0) return null;
  const rest = text.slice(i + MARK_START.length);
  const j = rest.indexOf(MARK_START);
  if (j < 0) return null;
  const enc = rest.slice(0, j);
  const parts = enc.split(SEP);
  function digitsOf(s: string) { let d = ""; for (const ch of s) { const idx = ZW_KEYS.indexOf(ch); if (idx >= 0) d += idx.toString(); } return d; }
  const noteDigits = digitsOf(parts[0] || "");
  if (!noteDigits) return null;
  const note = Number(noteDigits) / 10;
  const pcDigits = parts.length > 1 ? digitsOf(parts[1]) : "";
  const platformCode = pcDigits !== "" ? Number(pcDigits) : 0;
  return { note, platformCode };
}
function stripMarks(text: string) {
  return text.replace(new RegExp("[" + ZW_KEYS.join("") + SEP + "]", "g"), "");
}

function platformRules(p: string) {
  switch (p) {
    case "tiktok_shop":
      return `TIKTOK SHOP (objectif : VENDRE un produit). Reste sur UNE niche produit.
SCHEMA QUI VEND : 1) Accroche sur le PROBLEME ou un resultat choc ("J'ai teste ce truc et...", "Si tu galeres avec X, regarde ca"). 2) Montre le produit en action (demonstration, avant/apres). 3) Benefice concret + preuve sociale ("tout le monde l'achete", "ruptures de stock"). 4) URGENCE + CTA panier.
CTA TYPE SHOP (varie la formulation, garde panier orange + urgence) : "Clique sur le panier orange en bas a gauche avant rupture", "Stock quasi epuise, fonce sur le panier orange", "Le lien est dans le panier orange, mais y'en a plus pour longtemps".
Cree un sentiment de manque/FOMO. Le script doit donner envie d'acheter MAINTENANT.`;
    case "youtube_long":
      return `YOUTUBE LONG (objectif : retention sur une longue duree + abonnes).
SCHEMA : 1) Hook + promesse claire de ce que le spectateur va gagner dans les 15 premieres secondes. 2) Annonce le plan ("je vais te montrer 3 choses"). 3) Boucles ouvertes regulieres ("on y revient juste apres") pour retenir. 4) Valeur dense, exemples concrets. 5) Conclusion + CTA abonnement lie au benefice ("abonne-toi pour la partie 2").
FINS POSSIBLES (varie) : question d'avis en commentaire, cliffhanger sur la prochaine video, recap qui donne fierte, abonnement lie a la suite. Jamais un "abonne-toi" plat sans raison.`;
    case "instagram_post":
      return `POST INSTAGRAM (carrousel/reel + legende).
1ere ligne = scroll-stopper absolu. Lignes courtes et aerees. Apporte de la valeur ou de l'emotion vite.
FINS POSSIBLES (varie selon le contenu) : "Enregistre ce post pour plus tard", "Partage a quelqu'un qui en a besoin", "Commente X pour recevoir Y", une question qui divise, une punchline qui donne envie de partager.`;
    case "reels":
      return `INSTAGRAM REELS (court vertical). Hook < 1s, rythme rapide, une boucle ouverte, texte a l'ecran.
FINS POSSIBLES (varie) : boucle qui ramene au debut, question en commentaire, punchline emotionnelle, "enregistre pour pas oublier", "partage en story", "suis pour la partie 2".`;
    case "shorts":
      return `YOUTUBE SHORTS (court vertical). Hook ultra-rapide < 1s, format punchy, boucle qui ramene au debut.
FINS POSSIBLES (varie) : boucle de retention, question qui pousse au commentaire, twist final, "abonne-toi pour la suite", "regarde jusqu'au bout".`;
    default:
      return `TIKTOK (court vertical, objectif vues + abonnes).
Hook < 1s qui stoppe le scroll, zero temps mort, rythme rapide, une boucle ouverte qui tient jusqu'a la fin.
FINS POSSIBLES (varie selon l'histoire) : punchline emotionnelle qui donne envie de liker, question qui divise ("toi tu ferais quoi ?") pour les commentaires, twist/non-dit, boucle qui ramene au hook, verite relatable qui pousse au partage, abonnement integre a l'histoire ("j'en poste tous les jours"). Choisis la fin la plus FORTE pour CE contenu, jamais un "abonne-toi" plat.`;
  }
}

function clamp(n: number, lo: number, hi: number) { n = Number(n); if (isNaN(n)) n = 0; return Math.max(lo, Math.min(hi, n)); }
function round1(n: number) { return Math.round(n * 10) / 10; }
function computeNote(c: any[]) { if (!Array.isArray(c) || !c.length) return 0; let s = 0; for (const x of c) s += clamp(x.score, 0, 10); return round1(s / c.length); }

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const body = await req.json();
    const { script, platform, goal, niche, account } = body;
    const duration = Number(body.duration) || 30;
    // image produit optionnelle (base64) pour TikTok Shop
    const image = body.image || null;
    const imageType = body.imageType || "image/jpeg";
    // Image acceptée pour TikTok Shop ET pour les posts (X / Threads / Facebook / Instagram).
    const POST_PLATS = ["instagram_post", "post"];
    const isShop = platform === "tiktok_shop";
    const isPost = POST_PLATS.indexOf(platform) >= 0;
    const hasImage = !!(image && (isShop || isPost));
    const scriptText = (script || "").trim();
    // Pour TikTok Shop avec image, le script peut etre vide (on genere depuis l'image)
    if (!hasImage && scriptText.length < 5) {
      return new Response(JSON.stringify({ success: false, error: "Script trop court." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    const KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!KEY) {
      return new Response(JSON.stringify({ success: false, error: "Cle ANTHROPIC_API_KEY manquante." }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    // === Identification de l'utilisateur (quota cote SERVEUR, par compte) ===
    const SUPA_URL = Deno.env.get("SUPABASE_URL");
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    let admin: any = null, userId: string | null = null;
    try {
      const authHeader = req.headers.get("Authorization") || "";
      const jwt = authHeader.replace(/^Bearer\s+/i, "").trim();
      if (SUPA_URL && SERVICE_KEY) {
        admin = createClient(SUPA_URL, SERVICE_KEY, { auth: { persistSession: false } });
        if (jwt) { const { data: u } = await admin.auth.getUser(jwt); userId = u?.user?.id || null; }
      }
    } catch (_e) { userId = null; }

    // === Notation stable : script deja genere par Skillora ===
    const stamp = scriptText ? decodeStamp(script) : null;
    const reqPlatformCode = (PLATFORM_CODES[platform] != null ? PLATFORM_CODES[platform] : 0);
    if (stamp !== null && stamp.platformCode === reqPlatformCode) {
      const encoded = stamp.note;
      const crit = [
        { nom: "Hook", score: clamp(encoded + 0.5, 0, 10) }, { nom: "Structure", score: clamp(encoded, 0, 10) },
        { nom: "Retention", score: clamp(encoded, 0, 10) }, { nom: "Call to action", score: clamp(encoded - 0.5, 0, 10) },
      ];
      return new Response(JSON.stringify({
        success: true, analysis: {
          note: encoded, deja_optimise: true,
          verdict: "Ce script a ete optimise par Skillora pour cette plateforme. Il est pret a filmer.",
          criteres: crit,
          ce_qui_marche: ["Hook qui stoppe le scroll", "Boucle ouverte qui retient jusqu'au bout", "Fin qui declenche l'engagement"],
          a_eviter: ["Ne change rien : ce script est deja a son potentiel maximal pour cette plateforme."],
          montage: [{ t: "0-1s", a: "Plan serre + texte du hook a l'ecran" }, { t: "1-3s", a: "Coupe rapide, zoom dynamique" }, { t: "Fin", a: "Punchline/CTA visuel + sous-titres actifs" }],
          meilleur_moment: "12h-13h ou 18h-21h", hashtags: ["fyp", "pourtoi", "viral"], versions: [],
        },
      }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    // === Verification de la limite quotidienne (cote serveur, par compte) ===
    let userPlan = "starter", usedToday = 0;
    if (admin && userId) {
      try {
        const { data: sub } = await admin.from("subscriptions")
          .select("plan,status").eq("user_id", userId).maybeSingle();
        userPlan = (sub && sub.status === "active" && PLAN_LIMITS[sub.plan] != null) ? sub.plan : "starter";
        const { data: used } = await admin.rpc("get_script_usage", { p_user: userId });
        usedToday = Number(used) || 0;
      } catch (_e) { /* en cas d'erreur de lecture, on n'empeche pas l'analyse */ }
      const lim = planLimit(userPlan);
      if (usedToday >= lim) {
        return new Response(JSON.stringify({
          success: false, limit_reached: true, plan: userPlan, limit: lim, used: usedToday,
          error: "Limite quotidienne atteinte.",
        }), { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
      }
    }

    // Si le script vient de Skillora mais pour une AUTRE plateforme, on nettoie la marque.
    const scriptClean = stamp !== null ? stripMarks(script) : script;

    const rules = platformRules(platform);
    const nicheLine = niche ? `Niche : "${niche}". Adapte ton, references et hashtags.` : "";
    const accountLine = account ? `Compte : "${account}".` : "";
    const targetWords = Math.max(12, Math.round(duration * 2.5));
    const maxTokens = Math.max(1100, Math.min(3000, Math.round(targetWords * 4) + 600));

    // PARTIE FIXE (identique a chaque appel) -> mise en cache
    const SYSTEM_FIXED = `Tu es un SCENARISTE VIRAL d'elite (centaines de millions de vues). Tu ecris comme les meilleurs createurs humains, jamais comme une IA. Tu detestes le plat et le generique.

EXIGENCE DE QUALITE : la version que tu produis est EXCELLENTE, notee entre 8.5 et 9.8 (jamais moins). Script de niveau professionnel, pret a devenir viral. Choisis l'angle et la formule de hook les plus puissants pour ce script (un seul, le meilleur).

DONNE DU SENS : meme si l'utilisateur ne donne qu'une phrase ou une idee vague, construis une VRAIE petite histoire avec un debut, une tension, et un sens. La video doit raconter quelque chose, transmettre une emotion ou une idee forte, pas juste enchainer des phrases.

7 FORMULES DE HOOK (choisis la PLUS forte pour ce script) :
1. Curiosity gap 2. Promesse-resultat+temps 3. Declaration polarisante 4. In medias res 5. Question qui pique 6. Chiffre choc+preuve 7. Contre-intuitif.

STRUCTURE VIRALE : Hook (0-3s) -> boucle ouverte (annoncer un retournement) -> developpement avec tension et phrases courtes -> PAYOFF (la revelation qui donne du SENS a toute la video) -> FIN qui declenche l'engagement.

LA FIN EST CRUCIALE (c'est elle qui genere les likes, les commentaires et les abonnes). Ne termine JAMAIS sur un "abonne-toi" plat, mecanique et hors-sol. Choisis la fin la PLUS forte pour CETTE histoire, et VARIE selon le contenu, parmi :
- Punchline emotionnelle : une derniere phrase qui frappe (fierte, frisson, nostalgie, satisfaction) -> donne envie de liker.
- Question qui implique ou divise : un avis, un choix, "toi tu aurais fait quoi ?" -> genere des commentaires.
- Twist final / non-dit : une revelation partielle, une ouverture -> donne envie de commenter et de revoir.
- Boucle qui ramene au debut : la derniere phrase fait re-regarder le hook -> boucle de retention.
- Verite relatable : une phrase ou la personne se reconnait totalement -> donne envie de partager.
- Abonnement INTEGRE a l'histoire (jamais hors-sol) : lie a la promesse ("la suite demain", "je raconte le reste bientot").
La fin doit etre MERITEE par l'histoire, refermer le sens, et donner clairement envie d'AGIR (liker, commenter, partager ou s'abonner). Le champ "cta" contient CETTE phrase de fin.

INTERDIT a l'ouverture : "Bonjour", "Salut", "Je m'appelle X", "Aujourd'hui je vais parler de", "Bienvenue". Garde le prenom mais integre-le naturellement (au milieu, en aparte), jamais en ouverture mecanique.

STYLE : langage parle, vivant, du rythme, phrases qui claquent. On doit entendre un humain charismatique.

EXEMPLE :
Mauvais : "Je m'appelle Alex et je vais vous raconter comment j'ai sauve la ville." (fin : "Abonnez-vous a ma chaine.")
Bon : "Il restait 3 minutes avant que le robot rase la ville. Et le seul a pouvoir l'arreter, c'etait moi. Ce qui s'est passe ensuite, personne s'y attendait..." (fin : "Et toi, a ma place, t'aurais appuye sur le bouton ? Dis-le moi.")

NOTATION du script ORIGINAL de l'utilisateur (severe, juste). Chaque critere /10. Hook plat ("bonjour/je m'appelle" sans tension) = 1-2 max. Donne les 4 scores du script original.
REGLE DU ZERO (IMPORTANT) : si un critere est TOTALEMENT ABSENT du script, mets 0 (zero), jamais 1 "par defaut". Exemples : aucune phrase d'appel a l'action / aucune invitation (a s'abonner, commenter, acheter, partager...) => Call to action = 0 ; aucune accroche, le script commence a plat sans rien pour capter => Hook = 0 ; aucun ordre logique, idees jetees en vrac sans debut/milieu/fin => Structure = 0 ; rien qui donne envie de rester (pas de tension, pas de boucle, pas de promesse) => Retention = 0. Ne mets 1 que s'il existe une tentative reelle mais tres faible. Si l'element n'existe pas du tout, c'est 0.
IMPORTANT - ADAPTATION PLATEFORME : note le script PAR RAPPORT a la plateforme demandee. Si le script n'est PAS adapte a cette plateforme (ex: un script narratif classique soumis en TIKTOK SHOP qui ne vend aucun produit et n'a pas de CTA d'achat), la note doit etre BASSE (surtout Call to action et Structure), meme si le texte est bon en soi. Explique dans "a_eviter" pourquoi. La version, elle, est TOUJOURS parfaitement adaptee a la plateforme demandee.
Pour la version generee, donne aussi ses 4 scores (entre 8.5 et 9.8).

Reponds UNIQUEMENT en JSON valide strict :
{
"produit": null,
"verdict":"<phrase franche sur le script original>",
"criteres":[{"nom":"Hook","score":<n>},{"nom":"Structure","score":<n>},{"nom":"Retention","score":<n>},{"nom":"Call to action","score":<n>}],
"ce_qui_marche":["<court concret>","<court>"],
"a_eviter":["<court concret>","<court>"],
"montage":[{"t":"0-3s","a":"<concret>"},{"t":"3-15s","a":"<concret>"},{"t":"Fin","a":"<concret>"}],
"meilleur_moment":"<heure de publication ideale pour cette plateforme, ex: 18h-21h ; UNIQUEMENT un creneau horaire, jamais une phrase>",
"hashtags":["<niche>","<niche>","<niche>","<niche>","<niche>"],
"versions":[
{"titre":"<angle + formule>","hook":"<hook viral>","cta":"<la phrase de fin : emotion + declenche UNE action (like/commentaire/partage/abonnement), naturelle et meritee, JAMAIS un abonne-toi plat>","script":"<script complet et vivant, a la LONGUEUR exacte de la duree demandee, avec une vraie fin forte>","criteres":[{"nom":"Hook","score":<8.5-9.8>},{"nom":"Structure","score":<8.5-9.8>},{"nom":"Retention","score":<8.5-9.8>},{"nom":"Call to action","score":<8.5-9.8>}]}
]
}
Produis EXACTEMENT 1 version complete ; le SCRIPT fait la LONGUEUR demandee (duree cible), riche et detaille, et se TERMINE par une fin forte (la meme que le champ "cta"). MAIS garde les champs d'ANALYSE TRES COURTS pour rester dans un JSON VALIDE et complet : verdict max 25 mots ; chaque point de ce_qui_marche et a_eviter max 12 mots (2 points chacun) ; montage = 3 etapes ultra-courtes. Termine TOUJOURS le JSON. Script VIVANT, formules appliquees. Francais parle.`;

    // PARTIE VARIABLE (change a chaque appel, petite, non cachee)
    const shopInstr = `\nPRODUIT EN IMAGE : une image de produit TikTok Shop est fournie. 1) Identifie le produit (nom court et concret, max 5 mots). 2) Ecris un script de VENTE : accroche sur le probleme resolu, demo en action, preuve sociale, urgence/FOMO, CTA panier orange.
REMPLIS le champ "produit" du JSON avec EXACTEMENT cette structure :
"produit":{"nom":"<nom court du produit>","potentiel_vente":"<Fort|Moyen|Faible>","concurrence":"<Peu exploite|Equilibre|Sature>","angle":"<1 phrase: l'angle de vente le plus malin pour se demarquer>"}
REGLES DE STYLE pour "produit" : ultra concis, percutant, comme un expert e-commerce qui parle a un ami. PAS de blabla, PAS de phrases d'IA generiques. Direct, concret, premium. "potentiel_vente" et "concurrence" = UN SEUL mot de la liste. "angle" = une seule phrase courte et actionnable.`;
    const postInstr = `\nPOST AVEC IMAGE (X / Threads / Facebook / Instagram). Une image accompagne ce post. 1) Regarde l'IMAGE et le texte ensemble. 2) NOTE le post de depart (accroche dans la 1ere ligne, clarte, emotion, appel a reagir) — sois juste et severe. 3) Reecris une version OPTIMISEE : le champ "script" = une LEGENDE de post (PAS un long script video), courte et percutante (2 a 5 phrases), qui COLLE a l'image et donne envie de liker/commenter/partager ; "cta" = la derniere phrase qui declenche la reaction ; "hashtags" = pertinents pour le sujet de l'image. Reste humain, naturel, jamais robotique. Laisse "produit" a null.`;
    const imageInstr = hasImage ? (isShop ? shopInstr : postInstr) : "";
    const SYSTEM_VARIABLE = `CONTEXTE DE CETTE ANALYSE :
${rules}
${accountLine}
${nicheLine}
Objectif : ${goal || "gagner abonnes et vues"}.
DUREE CIBLE : ${duration}s (~${targetWords} mots pour le script). Ecris un script a CETTE longueur (+/-15%) : assez long pour remplir la duree, ni trop court.${imageInstr}`;

    // Construit le message utilisateur (texte + image optionnelle)
    let userContent: any;
    if (hasImage) {
      const parts: any[] = [];
      parts.push({ type: "image", source: { type: "base64", media_type: imageType, data: image } });
      if (scriptText) {
        parts.push({ type: "text", text: (isShop ? "Voici aussi des notes/script de depart :\n" : "Texte du post de depart a noter :\n") + scriptClean });
      } else {
        parts.push({ type: "text", text: isShop
          ? "Genere le script de vente a partir de ce produit (pas de script de depart fourni). Note le 'script original' comme inexistant : mets des scores bas et explique qu'il n'y avait pas encore de script."
          : "Pas de texte fourni : propose une legende a partir de l'image, et note le post de depart comme tres faible (texte absent)." });
      }
      userContent = parts;
    } else {
      userContent = "SCRIPT A ANALYSER :\n" + scriptClean;
    }

    const SCRIPT_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"];
    let aiRes: Response | null = null, aiData: any = null;
    for (const m of SCRIPT_MODELS) {
      aiRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: m,
          max_tokens: maxTokens,
          system: [
            { type: "text", text: SYSTEM_FIXED, cache_control: { type: "ephemeral" } },
            { type: "text", text: SYSTEM_VARIABLE },
          ],
          messages: [{ role: "user", content: userContent }],
        }),
      });
      if (aiRes.ok) break;
      aiData = await aiRes.json().catch(() => ({}));
      if (aiRes.status !== 404) {
        return new Response(JSON.stringify({ success: false, error: aiData?.error?.message || "Erreur Claude" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
      }
      aiRes = null;
    }
    if (!aiRes) {
      return new Response(JSON.stringify({ success: false, error: "Aucun modele IA disponible." }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    aiData = await aiRes.json();

    let text = "";
    if (Array.isArray(aiData.content)) {
      for (const block of aiData.content) { if (block.type === "text") text += block.text; }
    }
    text = text.replace(/```json/g, "").replace(/```/g, "").trim();
    // extraire l'objet JSON meme s'il est entoure de texte
    function extractJSON(t: string) {
      const start = t.indexOf("{");
      const end = t.lastIndexOf("}");
      if (start >= 0 && end > start) return t.slice(start, end + 1);
      return t;
    }
    let analysis: any;
    try { analysis = JSON.parse(text); }
    catch (_e1) {
      try { analysis = JSON.parse(extractJSON(text)); }
      catch (_e2) {
        return new Response(JSON.stringify({ success: true, raw: text }),
          { headers: { ...corsHeaders, "Content-Type": "application/json" } });
      }
    }

    analysis.note = computeNote(analysis.criteres);
    if (Array.isArray(analysis.versions)) {
      analysis.versions = analysis.versions.map((v: any) => {
        const vnote = computeNote(v.criteres);
        return { ...v, note: vnote, script: (v.script || "") + encodeStamp(vnote, platform) };
      });
    }
    analysis.deja_optimise = false;

    // Analyse reelle reussie -> on incremente le compteur du jour (cote serveur)
    let remaining: number | null = null;
    if (admin && userId) {
      try {
        const { data: nv } = await admin.rpc("bump_script_usage", { p_user: userId });
        const newCount = Number(nv) || (usedToday + 1);
        remaining = Math.max(0, planLimit(userPlan) - newCount);
      } catch (_e) { /* si l'increment echoue, on ne bloque pas la reponse */ }
    }

    return new Response(JSON.stringify({ success: true, analysis, plan: userPlan, remaining, limit: planLimit(userPlan) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (err) {
    return new Response(JSON.stringify({ success: false, error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
});
