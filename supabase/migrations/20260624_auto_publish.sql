-- SKILLORA — Publication automatique : table des publications + bucket de stockage vidéo.

create table if not exists public.scheduled_posts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  caption text,
  media_url text,
  platforms text[],
  pfm_post_id text,
  status text not null default 'scheduled',   -- scheduled | publishing | published | failed
  scheduled_at timestamptz,
  error text,
  created_at timestamptz default now()
);
alter table public.scheduled_posts enable row level security;

do $$ begin
  if not exists (select 1 from pg_policies where schemaname='public' and tablename='scheduled_posts' and policyname='sp_select_own') then
    create policy sp_select_own on public.scheduled_posts for select using (auth.uid() = user_id);
  end if;
end $$;

-- Bucket public pour héberger les vidéos à publier (Post for Me a besoin d'une URL).
insert into storage.buckets (id, name, public)
values ('post-media', 'post-media', true)
on conflict (id) do nothing;

do $$ begin
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='post_media_insert') then
    create policy post_media_insert on storage.objects for insert to authenticated
      with check (bucket_id = 'post-media');
  end if;
  if not exists (select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='post_media_read') then
    create policy post_media_read on storage.objects for select using (bucket_id = 'post-media');
  end if;
end $$;
