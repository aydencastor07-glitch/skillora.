import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { OverviewPage } from '@/components/overview-page';
import { PlatformIcon } from '@/components/platform-icon';
import { ProfilePage } from '@/components/profile-page';
import { PrimaryButton } from '@/components/ui';
import { PLATFORMS } from '@/constants/platforms';
import { Colors, Radius, Spacing } from '@/constants/theme';
import type { Account } from '@/lib/types';
import { DEMO_MODE } from '@/services/config';
import { useQuax } from '@/store/quax-store';

const TOP_BAR = 56;

type Page = { key: string; account?: Account };

export default function HomeScreen() {
  const { accounts, posts, loading } = useQuax();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [index, setIndex] = useState(0);
  const listRef = useRef<FlatList<Page>>(null);

  const pages: Page[] = [{ key: 'overview' }, ...accounts.map((a) => ({ key: a.id, account: a }))];
  const current = pages[index]?.account;

  const goTo = (i: number) => {
    setIndex(i);
    listRef.current?.scrollToIndex({ index: i, animated: true });
  };

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i !== index && i >= 0 && i < pages.length) setIndex(i);
  };

  if (loading && accounts.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.accent} />
      </View>
    );
  }

  if (accounts.length === 0) {
    return (
      <View style={[styles.center, { padding: Spacing.four }]}>
        <Text style={styles.logo}>quax</Text>
        <Text style={styles.emptyTitle}>Tous tes réseaux, un seul endroit.</Text>
        <Text style={styles.emptyText}>
          Connecte Instagram, TikTok, YouTube, X, Facebook… pour suivre tes stats et publier partout d&apos;un coup.
        </Text>
        <View style={{ alignSelf: 'stretch', marginTop: Spacing.four }}>
          <PrimaryButton label="Connecter un compte" icon="link" onPress={() => router.push('/accounts')} />
        </View>
      </View>
    );
  }

  const topInset = insets.top + TOP_BAR + Spacing.two;

  return (
    <View style={styles.root}>
      <FlatList
        ref={listRef}
        data={pages}
        keyExtractor={(p) => p.key}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
        renderItem={({ item }) =>
          item.account ? (
            <ProfilePage account={item.account} width={width} topInset={topInset} />
          ) : (
            <OverviewPage accounts={accounts} posts={posts} width={width} topInset={topInset} onOpen={goTo} />
          )
        }
      />

      {/* Floating top bar: logo + platform switcher (synced with the swipe) */}
      <View style={[styles.topBar, { paddingTop: insets.top + 6 }]} pointerEvents="box-none">
        <Pressable onPress={() => goTo(0)} style={[styles.pill, index === 0 && styles.pillActive]}>
          <Text style={styles.logoSmall}>quax</Text>
          {DEMO_MODE && <Text style={styles.demo}>DÉMO</Text>}
        </Pressable>
        <ScrollView
          horizontal
          style={{ flex: 1 }}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.switcher}>
          {accounts.map((a, i) => {
            const active = index === i + 1;
            return (
              <Pressable
                key={a.id}
                onPress={() => goTo(i + 1)}
                accessibilityLabel={PLATFORMS[a.platform].name}
                style={[styles.dot, active && { backgroundColor: PLATFORMS[a.platform].color, borderColor: 'transparent' }]}>
                <PlatformIcon platform={a.platform} size={15} color={active ? PLATFORMS[a.platform].onColor : '#fff'} />
              </Pressable>
            );
          })}
        </ScrollView>
        <Pressable onPress={() => router.push('/accounts')} style={styles.dot} accessibilityLabel="Gérer les comptes">
          <Ionicons name="add" size={20} color="#fff" />
        </Pressable>
      </View>

      {/* Page indicator */}
      <View style={[styles.indicator, { top: insets.top + TOP_BAR + 2 }]} pointerEvents="none">
        {pages.map((p, i) => (
          <View
            key={p.key}
            style={[
              styles.indicatorDot,
              i === index && { width: 18, backgroundColor: current ? PLATFORMS[current.platform].color : '#fff' },
            ]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background },
  logo: { color: Colors.text, fontSize: 44, fontWeight: '900', letterSpacing: -1.5 },
  emptyTitle: { color: Colors.text, fontSize: 22, fontWeight: '800', marginTop: Spacing.three, textAlign: 'center' },
  emptyText: { color: Colors.textSecondary, fontSize: 15, textAlign: 'center', marginTop: Spacing.two, lineHeight: 21 },
  topBar: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.three,
    gap: 8,
  },
  pill: {
    height: 38,
    paddingHorizontal: 14,
    borderRadius: Radius.pill,
    backgroundColor: 'rgba(0,0,0,0.35)',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,255,255,0.2)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pillActive: { backgroundColor: 'rgba(255,255,255,0.18)' },
  logoSmall: { color: '#fff', fontSize: 18, fontWeight: '900', letterSpacing: -0.5 },
  demo: {
    color: '#000',
    backgroundColor: Colors.warning,
    fontSize: 9,
    fontWeight: '900',
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 4,
    overflow: 'hidden',
  },
  switcher: { gap: 8, paddingRight: 8 },
  dot: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(0,0,0,0.35)',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  indicator: { position: 'absolute', left: 0, right: 0, flexDirection: 'row', justifyContent: 'center', gap: 5 },
  indicatorDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.35)' },
});
