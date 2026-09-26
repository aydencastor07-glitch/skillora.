/**
 * Quax AI — chat with Claude, streamed as plain text.
 *
 * POST { messages: [{ role: 'user' | 'assistant', content }], context: string }
 *   → text/plain stream (the answer, chunk by chunk)
 *
 * `context` is a text snapshot of the user's stats built by the app (src/lib/ai-context.ts).
 * Secret: ANTHROPIC_API_KEY.
 */
import Anthropic from 'npm:@anthropic-ai/sdk';

import { corsHeaders, error, requireEnv } from '../_shared/http.ts';

const MODEL = 'claude-opus-5';
const MAX_HISTORY = 30;

const SYSTEM = `Tu es Quax AI, l'assistant intégré à Quax, une application de social media management.
L'utilisateur connecte ses réseaux (Instagram, TikTok, YouTube, X, Facebook, LinkedIn…) et publie depuis Quax.

Ton rôle :
- analyser ses statistiques (abonnés, vues, likes, engagement) et expliquer ce qui marche ;
- lui dire quand publier en t'appuyant sur les créneaux d'activité de son audience ;
- proposer des idées de contenus, des accroches, des légendes et des hashtags adaptés à chaque réseau.

Style : tu tutoies, tu réponds en français, de façon courte et concrète (c'est une app mobile) : quelques phrases
ou une petite liste. Mets en **gras** l'info clé. Appuie-toi sur les chiffres du contexte ; n'invente jamais de
statistiques qui n'y figurent pas — si une donnée manque, dis-le simplement.`;

type ChatTurn = { role: 'user' | 'assistant'; content: string };

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders });
  if (req.method !== 'POST') return error('Méthode non autorisée', 405);

  let client: Anthropic;
  try {
    client = new Anthropic({ apiKey: requireEnv('ANTHROPIC_API_KEY') });
  } catch (e) {
    return error(e instanceof Error ? e.message : String(e), 500);
  }

  const body = await req.json().catch(() => ({}));
  const history = ((body.messages ?? []) as ChatTurn[])
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string' && m.content.trim())
    .slice(-MAX_HISTORY);
  // The API expects the conversation to start with a user turn.
  while (history.length && history[0].role !== 'user') history.shift();
  if (history.length === 0) return error('Message vide');

  const context = typeof body.context === 'string' && body.context ? body.context : 'Aucune donnée fournie.';

  const stream = client.beta.messages.stream({
    model: MODEL,
    max_tokens: 16000,
    thinking: { type: 'adaptive' },
    output_config: { effort: 'medium' },
    // If Claude declines a request, the API retries it on the recommended fallback model instead.
    betas: ['server-side-fallback-2026-07-01'],
    ...({ fallbacks: 'default' } as Record<string, unknown>),
    system: [
      // Stable part first (cached), per-user stats after the breakpoint.
      { type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } },
      { type: 'text', text: `Données actuelles de l'utilisateur :\n${context}` },
    ],
    messages: history,
  });

  const encoder = new TextEncoder();
  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        for await (const event of stream) {
          if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
            controller.enqueue(encoder.encode(event.delta.text));
          }
        }
        const final = await stream.finalMessage();
        if (final.stop_reason === 'refusal') {
          controller.enqueue(encoder.encode("\n\nJe ne peux pas t'aider sur ce point. Essaie de reformuler ta question."));
        } else if (final.stop_reason === 'max_tokens') {
          controller.enqueue(encoder.encode('…'));
        }
      } catch (e) {
        console.error(e);
        const message =
          e instanceof Anthropic.RateLimitError
            ? "L'IA est très demandée, réessaie dans un instant."
            : e instanceof Anthropic.AuthenticationError
              ? 'Clé API Anthropic invalide.'
              : "L'IA est indisponible pour le moment.";
        controller.enqueue(encoder.encode(`\n\n⚠️ ${message}`));
      } finally {
        controller.close();
      }
    },
    cancel() {
      stream.abort();
    },
  });

  return new Response(readable, {
    headers: { ...corsHeaders, 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' },
  });
});
