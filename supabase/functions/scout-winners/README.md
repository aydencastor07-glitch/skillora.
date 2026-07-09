# Agent Éclaireur — `scout-winners`

Recherche **autonome** des vidéos qui cartonnent, pour remplacer la recherche humaine.
Pour chaque compte connecté (TikTok, Instagram, YouTube) :

1. **À la connexion** (`pfm-sync`) → on pose une *ligne de base* dans `scout_accounts`
   (`baseline_at = maintenant`). Coût **0 crédit**. Tout ce qui existait avant est ignoré.
2. **Balayage régulier** (cette fonction) → on repère les vidéos publiées **après** la connexion qui explosent :
   - **gagnante du créateur** (`user-styles/{user_id}`) : vues ≥ `max(1000, 3× sa médiane)` ;
   - **gagnante générale** (`style-library`, l'école de Gemini) : vues ≥ `50 000`.
   Elles vont dans la file `winning_videos`.
3. **Le video-worker**, au repos, réclame chaque gagnante (`claim_winning_video`), la fait **étudier par Gemini**
   et enrichit la mémoire de style. 100 % automatique.

## Déploiement

```
supabase functions deploy scout-winners
```

Secret requis (déjà présent pour les autres fonctions) : `SOCIAVAULT_API_KEY`.

## Planification quotidienne (une seule fois)

Économe en crédits : un compte n'est rescané qu'au plus une fois / 20 h.
Programmez un appel quotidien via `pg_cron` + `pg_net` (SQL editor Supabase) :

```sql
select cron.schedule(
  'scout-winners-daily', '17 3 * * *',   -- tous les jours à 03:17 UTC
  $$ select net.http_post(
       url     := 'https://<PROJECT_REF>.supabase.co/functions/v1/scout-winners',
       headers := jsonb_build_object('Content-Type','application/json',
                                     'Authorization','Bearer <SERVICE_ROLE_KEY>'),
       body    := '{}'::jsonb
     ); $$
);
```

Remplacez `<PROJECT_REF>` et `<SERVICE_ROLE_KEY>`. Extensions à activer : `pg_cron`, `pg_net`.

## Appel manuel / juste après une connexion

```
POST /functions/v1/scout-winners
{ "user_id": "uuid-optionnel", "force": true }
```

- `user_id` : ne scanner qu'un créateur (utile juste après sa connexion).
- `force` : ignorer l'intervalle anti-crédits de 20 h.
