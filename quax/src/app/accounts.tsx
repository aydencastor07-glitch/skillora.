import { router } from 'expo-router';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PlatformIcon } from '@/components/platform-icon';
import { Card, IconButton, ScreenHeader } from '@/components/ui';
import { PLATFORM_ORDER, PLATFORMS } from '@/constants/platforms';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { formatCompact } from '@/lib/format';
import { DEMO_MODE } from '@/services/config';
import { useQuax } from '@/store/quax-store';

export default function AccountsScreen() {
  const { accounts, connect, disconnect, connecting } = useQuax();
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: insets.bottom + Spacing.five }}>
        <ScreenHeader
          title="Mes comptes"
          subtitle="Connecte tous tes réseaux"
          right={<IconButton icon="close" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />}
        />
        <View style={styles.content}>
          {DEMO_MODE && (
            <Text style={styles.note}>
              Mode démo : les comptes sont simulés. Une fois l’API de publication branchée, « Connecter » ouvrira la
              connexion officielle du réseau.
            </Text>
          )}
          <Card style={{ paddingVertical: Spacing.two }}>
            {PLATFORM_ORDER.map((id, i) => {
              const p = PLATFORMS[id];
              const account = accounts.find((a) => a.platform === id);
              const busy = connecting === id;
              return (
                <View key={id} style={[styles.row, i > 0 && styles.separator]}>
                  <PlatformIcon platform={id} badge size={16} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.name}>{p.name}</Text>
                    <Text style={styles.sub}>
                      {account ? `@${account.handle} · ${formatCompact(account.followers)} abonnés` : 'Non connecté'}
                    </Text>
                  </View>
                  {busy ? (
                    <ActivityIndicator color={p.color === '#FFFFFF' ? Colors.text : p.color} />
                  ) : account ? (
                    <Pressable onPress={() => disconnect(id)} style={[styles.button, styles.ghost]}>
                      <Text style={[styles.buttonText, { color: Colors.textSecondary }]}>Retirer</Text>
                    </Pressable>
                  ) : (
                    <Pressable
                      onPress={() => connect(id)}
                      disabled={connecting !== null}
                      style={[styles.button, { backgroundColor: p.color }]}>
                      <Text style={[styles.buttonText, { color: p.onColor }]}>Connecter</Text>
                    </Pressable>
                  )}
                </View>
              );
            })}
          </Card>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  content: { paddingHorizontal: Spacing.three, gap: Spacing.three },
  note: { color: Colors.textSecondary, fontSize: 13, lineHeight: 18 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  separator: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.border },
  name: { color: Colors.text, fontSize: 16, fontWeight: '700' },
  sub: { color: Colors.textMuted, fontSize: 12, marginTop: 1 },
  button: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: Radius.pill },
  ghost: { backgroundColor: Colors.surfaceRaised },
  buttonText: { fontWeight: '800', fontSize: 13 },
});
