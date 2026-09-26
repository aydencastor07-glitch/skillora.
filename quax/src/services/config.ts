/**
 * Runtime configuration. Everything is read from `EXPO_PUBLIC_*` variables (see `.env.example`).
 *
 * Without `EXPO_PUBLIC_QUAX_API_URL`, the app runs in **demo mode**: accounts, stats, publishing and the
 * AI all work on local mock data, so the whole product can be designed and tested without paying for
 * any API. Set the variable once the backend (Supabase Edge Functions in `supabase/functions`) is deployed.
 *
 * API keys (Anthropic, Post for Me, SociaVault) NEVER go here: they live on the backend only.
 */
export const API_URL = (process.env.EXPO_PUBLIC_QUAX_API_URL ?? '').replace(/\/$/, '');
export const API_ANON_KEY = process.env.EXPO_PUBLIC_QUAX_ANON_KEY ?? '';

export const DEMO_MODE = API_URL === '';
