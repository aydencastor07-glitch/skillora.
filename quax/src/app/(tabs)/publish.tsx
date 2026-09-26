import Ionicons from '@expo/vector-icons/Ionicons';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform as RNPlatform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PlatformIcon } from '@/components/platform-icon';
import { Card, Chip, PrimaryButton, ScreenHeader, SectionTitle, type IconName } from '@/components/ui';
import { PLATFORMS, type PlatformId } from '@/constants/platforms';
import { Colors, QuaxGradient, Radius, Spacing, TabBarSpace } from '@/constants/theme';
import { nextBestTime } from '@/lib/best-time';
import { formatDateTime, formatDayLabel, formatPercent } from '@/lib/format';
import type { PublishMode, ScheduledPost } from '@/lib/types';
import { generateCaption } from '@/services/api';
import { useQuax } from '@/store/quax-store';

const MODES: { id: PublishMode; label: string; icon: IconName; hint: string }[] = [
  { id: 'now', label: 'Maintenant', icon: 'flash', hint: 'Publié instantanément sur tous les réseaux choisis.' },
  { id: 'scheduled', label: 'Programmer', icon: 'calendar', hint: 'Choisis le jour et l’heure exacts.' },
  { id: 'best', label: 'Meilleur moment', icon: 'sparkles', hint: 'Quax analyse ton audience et publie au moment idéal.' },
];

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const MINUTES = [0, 15, 30, 45];

function platformFromParams(value?: string): PlatformId[] | null {
  return value && value in PLATFORMS ? [value as PlatformId] : null;
}

function modeFromParams(value?: string): PublishMode | null {
  return value === 'now' || value === 'scheduled' || value === 'best' ? value : null;
}

export default function PublishScreen() {
  const params = useLocalSearchParams<{ platform?: string; mode?: string }>();
  const { accounts, createPost } = useQuax();
  const insets = useSafeAreaInsets();

  const [caption, setCaption] = useState('');
  const [media, setMedia] = useState<{ uri: string; kind: ScheduledPost['mediaKind'] } | null>(null);
  // null = every connected account (the default).
  const [picked, setPicked] = useState<PlatformId[] | null>(() => platformFromParams(params.platform));
  const [mode, setMode] = useState<PublishMode>(() => modeFromParams(params.mode) ?? 'now');
  const [dayOffset, setDayOffset] = useState(0);
  const [hour, setHour] = useState(() => (new Date().getHours() + 2) % 24);
  const [minute, setMinute] = useState(0);
  const [writing, setWriting] = useState(false);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  // The tab stays mounted: re-apply deep-link params (e.g. "Programmer sur TikTok") when they change.
  const paramKey = `${params.platform ?? ''}|${params.mode ?? ''}`;
  const [seenParams, setSeenParams] = useState(paramKey);
  if (seenParams !== paramKey) {
    setSeenParams(paramKey);
    setPicked(platformFromParams(params.platform));
    const m = modeFromParams(params.mode);
    if (m) setMode(m);
  }

  const selected = picked ?? accounts.map((a) => a.platform);

  const targetAccounts = accounts.filter((a) => selected.includes(a.platform));
  const best = targetAccounts.length ? nextBestTime(targetAccounts) : null;

  const scheduledDate = (() => {
    const d = new Date(now);
    d.setDate(d.getDate() + dayOffset);
    d.setHours(hour, minute, 0, 0);
    return d;
  })();
  const scheduleInPast = mode === 'scheduled' && scheduledDate.getTime() <= now;

  const toggle = (p: PlatformId) =>
    setPicked(selected.includes(p) ? selected.filter((x) => x !== p) : [...selected, p]);

  const pickMedia = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images', 'videos'], quality: 0.9 });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      setMedia({ uri: asset.uri, kind: asset.type === 'video' ? 'video' : 'image' });
    }
  };

  const writeWithAi = async () => {
    setWriting(true);
    try {
      setCaption(await generateCaption(caption, selected));
    } finally {
      setWriting(false);
    }
  };

  const submit = async () => {
    setSending(true);
    try {
      const at = mode === 'best' && best ? best.date : scheduledDate;
      await createPost({ caption, platforms: selected, mode, scheduledAt: at, mediaKind: media?.kind ?? 'text' });
      setDone(
        mode === 'now'
          ? `Publié sur ${selected.length} réseau${selected.length > 1 ? 'x' : ''} 🎉`
          : `Programmé pour ${formatDateTime(at)} ✅`,
      );
      setCaption('');
      setMedia(null);
    } finally {
      setSending(false);
    }
  };

  const canSubmit = selected.length > 0 && (caption.trim().length > 0 || media !== null) && !scheduleInPast;
  const cta = mode === 'now' ? 'Publier maintenant' : mode === 'best' ? 'Publier au meilleur moment' : 'Programmer';

  return (
    <KeyboardAvoidingView style={styles.root} behavior={RNPlatform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: TabBarSpace + insets.bottom }}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}>
        <ScreenHeader title="Publier" subtitle="Un post, tous tes réseaux" />

        <View style={styles.content}>
          {done && (
            <Pressable onPress={() => router.push('/calendar')} style={styles.success}>
              <Ionicons name="checkmark-circle" size={22} color={Colors.success} />
              <Text style={styles.successText}>{done}</Text>
              <Text style={styles.successLink}>Voir</Text>
            </Pressable>
          )}

          {/* Media + caption */}
          <Card>
            <Pressable onPress={pickMedia} style={styles.media}>
              {media ? (
                <>
                  {media.kind === 'image' ? (
                    <Image source={media.uri} style={StyleSheet.absoluteFill} contentFit="cover" />
                  ) : (
                    <View style={styles.videoBadge}>
                      <Ionicons name="videocam" size={28} color="#fff" />
                      <Text style={styles.mediaText}>Vidéo sélectionnée</Text>
                    </View>
                  )}
                  <Pressable onPress={() => setMedia(null)} style={styles.removeMedia} hitSlop={8}>
                    <Ionicons name="close" size={16} color="#fff" />
                  </Pressable>
                </>
              ) : (
                <>
                  <Ionicons name="cloud-upload-outline" size={30} color={Colors.textSecondary} />
                  <Text style={styles.mediaText}>Ajouter une vidéo ou une photo</Text>
                </>
              )}
            </Pressable>

            <TextInput
              value={caption}
              onChangeText={setCaption}
              placeholder="Écris ta légende…"
              placeholderTextColor={Colors.textMuted}
              multiline
              style={styles.input}
            />
            <View style={styles.captionFooter}>
              <Pressable onPress={writeWithAi} disabled={writing} style={styles.aiButton}>
                {writing ? (
                  <ActivityIndicator size="small" color={QuaxGradient[1]} />
                ) : (
                  <Ionicons name="sparkles" size={15} color={QuaxGradient[1]} />
                )}
                <Text style={styles.aiText}>{caption ? 'Améliorer avec l’IA' : 'Écrire avec l’IA'}</Text>
              </Pressable>
              <Text style={styles.counter}>{caption.length}</Text>
            </View>
          </Card>

          {/* Networks */}
          <Card>
            <SectionTitle>Publier sur</SectionTitle>
            <View style={styles.platforms}>
              {accounts.map((a) => {
                const on = selected.includes(a.platform);
                const p = PLATFORMS[a.platform];
                return (
                  <Pressable
                    key={a.id}
                    onPress={() => toggle(a.platform)}
                    style={[styles.platform, on && { borderColor: p.color, backgroundColor: `${p.color}22` }]}>
                    <PlatformIcon platform={a.platform} size={20} color={on ? p.color : Colors.textMuted} />
                    <Text style={[styles.platformName, !on && { color: Colors.textMuted }]} numberOfLines={1}>
                      {p.name}
                    </Text>
                    {on && (
                      <View style={[styles.check, { backgroundColor: p.color }]}>
                        <Ionicons name="checkmark" size={11} color={p.onColor} />
                      </View>
                    )}
                  </Pressable>
                );
              })}
              {accounts.length === 0 && <Text style={styles.muted}>Connecte d’abord un compte depuis l’accueil.</Text>}
            </View>
          </Card>

          {/* When */}
          <Card>
            <SectionTitle>Quand ?</SectionTitle>
            <View style={styles.modes}>
              {MODES.map((m) => (
                <Pressable
                  key={m.id}
                  onPress={() => setMode(m.id)}
                  style={[styles.mode, mode === m.id && styles.modeActive]}>
                  <Ionicons name={m.icon} size={18} color={mode === m.id ? '#fff' : Colors.textSecondary} />
                  <Text style={[styles.modeText, mode === m.id && { color: '#fff' }]}>{m.label}</Text>
                </Pressable>
              ))}
            </View>
            <Text style={styles.muted}>{MODES.find((m) => m.id === mode)?.hint}</Text>

            {mode === 'scheduled' && (
              <View style={{ gap: Spacing.two, marginTop: Spacing.three }}>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
                  {Array.from({ length: 14 }, (_, i) => {
                    const d = new Date(now);
                    d.setDate(d.getDate() + i);
                    return <Chip key={i} label={formatDayLabel(d, new Date(now))} active={dayOffset === i} onPress={() => setDayOffset(i)} />;
                  })}
                </ScrollView>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
                  {HOURS.map((h) => (
                    <Chip key={h} label={`${h}h`} active={hour === h} onPress={() => setHour(h)} />
                  ))}
                </ScrollView>
                <View style={styles.row}>
                  {MINUTES.map((m) => (
                    <Chip key={m} label={`:${String(m).padStart(2, '0')}`} active={minute === m} onPress={() => setMinute(m)} />
                  ))}
                </View>
                <Text style={[styles.when, scheduleInPast && { color: Colors.danger }]}>
                  {scheduleInPast ? 'Cette heure est déjà passée' : formatDateTime(scheduledDate)}
                </Text>
              </View>
            )}

            {mode === 'best' && best && (
              <View style={styles.bestBox}>
                <Ionicons name="sparkles" size={20} color={QuaxGradient[1]} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.when}>{formatDateTime(best.date)}</Text>
                  <Text style={styles.muted}>
                    Pic d’activité de ton audience ({formatPercent(best.score * 100)} du maximum) sur{' '}
                    {targetAccounts.map((a) => PLATFORMS[a.platform].name).join(', ')}.
                  </Text>
                </View>
              </View>
            )}
          </Card>

          <PrimaryButton
            label={cta}
            icon={mode === 'now' ? 'send' : 'time'}
            onPress={submit}
            loading={sending}
            disabled={!canSubmit}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  success: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: Spacing.three,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(46,229,157,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(46,229,157,0.35)',
  },
  successText: { color: Colors.text, fontWeight: '700', flex: 1 },
  successLink: { color: Colors.success, fontWeight: '800' },
  media: {
    height: 150,
    borderRadius: Radius.md,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    overflow: 'hidden',
    backgroundColor: Colors.background,
  },
  mediaText: { color: Colors.textSecondary, fontWeight: '600' },
  videoBadge: { alignItems: 'center', gap: 6 },
  removeMedia: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  input: {
    color: Colors.text,
    fontSize: 16,
    minHeight: 100,
    textAlignVertical: 'top',
    marginTop: Spacing.three,
    lineHeight: 22,
  },
  captionFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: Spacing.two },
  aiButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(192,77,255,0.14)',
  },
  aiText: { color: '#E3B8FF', fontWeight: '700', fontSize: 13 },
  counter: { color: Colors.textMuted, fontSize: 12 },
  platforms: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  platform: {
    width: '31%',
    flexGrow: 1,
    alignItems: 'center',
    gap: 6,
    paddingVertical: 12,
    borderRadius: Radius.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
  },
  platformName: { color: Colors.text, fontSize: 12, fontWeight: '700' },
  check: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modes: { flexDirection: 'row', gap: 8, marginBottom: Spacing.two },
  mode: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
    paddingVertical: 12,
    borderRadius: Radius.md,
    backgroundColor: Colors.surfaceRaised,
  },
  modeActive: { backgroundColor: Colors.accent },
  modeText: { color: Colors.textSecondary, fontSize: 12, fontWeight: '700' },
  muted: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18 },
  row: { flexDirection: 'row', gap: 8 },
  when: { color: Colors.text, fontSize: 16, fontWeight: '800' },
  bestBox: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    marginTop: Spacing.three,
    padding: Spacing.three,
    borderRadius: Radius.md,
    backgroundColor: 'rgba(124,92,255,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(124,92,255,0.35)',
  },
});
