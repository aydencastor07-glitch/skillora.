# Agents autonomes — `scout-winners` + `scout-explore`

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

---

# `scout-explore` — le chercheur d'internet

Remplace la recherche humaine de liens : pour chaque **style** (talk_facecam, horror, dance…),
il interroge la **recherche TikTok** de SociaVault (`/tiktok/search/keyword`, tri *most-liked*,
période *this-week*), garde les vidéos ≥ 50 000 vues et les met en file `winning_videos`
(scope `global`, niche imposée). Le worker les fait étudier par Gemini → `style-library`.

```
supabase functions deploy scout-explore
```

Planification **hebdomadaire** (1 recherche par style et par semaine — crédits maîtrisés) :

```sql
select cron.schedule(
  'scout-explore-weekly', '43 4 * * 1',   -- lundi 04:43 UTC
  $$ select net.http_post(
       url     := 'https://<PROJECT_REF>.supabase.co/functions/v1/scout-explore',
       headers := jsonb_build_object('Content-Type','application/json',
                                     'Authorization','Bearer <SERVICE_ROLE_KEY>'),
       body    := '{}'::jsonb
     ); $$
);
```

Appel manuel avec styles personnalisés :

```
POST /functions/v1/scout-explore
{ "niches": { "horror": "pov horror storytime" }, "max_per_niche": 3 }
```

## Clé côté worker (optionnelle mais recommandée)

Ajoutez `Environment=SOCIAVAULT_API_KEY=...` dans `/etc/systemd/system/skillora-worker.service`
(puis `systemctl daemon-reload && systemctl restart skillora-worker`) : les liens mp4 TikTok
expirent en quelques heures, cette clé permet au worker d'en redemander un frais au moment de l'étude.
