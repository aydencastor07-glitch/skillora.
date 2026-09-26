import Ionicons from '@expo/vector-icons/Ionicons';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { IconButton, RichText, ScreenHeader } from '@/components/ui';
import { Colors, QuaxGradient, Radius, Spacing } from '@/constants/theme';
import type { ChatMessage } from '@/lib/types';
import { DEMO_MODE } from '@/services/config';
import { useQuax } from '@/store/quax-store';

const SUGGESTIONS = [
  'Quand est-ce que je dois publier ?',
  'Est-ce que mes abonnés ont augmenté ?',
  "Qu'est-ce qui a le mieux marché ?",
  'Écris-moi une légende pour ma prochaine vidéo',
];

export default function AiScreen() {
  const { chat, ask, aiBusy, resetChat } = useQuax();
  const insets = useSafeAreaInsets();
  const [input, setInput] = useState('');
  const listRef = useRef<FlatList<ChatMessage>>(null);

  useEffect(() => {
    const t = setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(t);
  }, [chat]);

  const send = (text: string) => {
    if (!text.trim() || aiBusy) return;
    setInput('');
    ask(text);
  };

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScreenHeader
        title="Quax AI"
        subtitle={DEMO_MODE ? 'Assistant · mode démo' : 'Ton assistant social media'}
        right={<IconButton icon="refresh" onPress={resetChat} />}
      />

      <FlatList
        ref={listRef}
        data={chat}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => <Bubble message={item} />}
        ListFooterComponent={
          chat.length <= 1 ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestions}>
              {SUGGESTIONS.map((s) => (
                <Pressable key={s} onPress={() => send(s)} style={styles.suggestion}>
                  <Text style={styles.suggestionText}>{s}</Text>
                </Pressable>
              ))}
            </ScrollView>
          ) : null
        }
      />

      <View style={[styles.composer, { marginBottom: 68 + Math.max(insets.bottom, 12) + 10 }]}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Pose ta question…"
          placeholderTextColor={Colors.textMuted}
          style={styles.input}
          multiline
          onSubmitEditing={() => send(input)}
          submitBehavior="submit"
        />
        <Pressable onPress={() => send(input)} disabled={!input.trim() || aiBusy}>
          <LinearGradient
            colors={QuaxGradient}
            style={[styles.send, (!input.trim() || aiBusy) && { opacity: 0.4 }]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}>
            <Ionicons name="arrow-up" size={20} color="#fff" />
          </LinearGradient>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user';
  if (mine) {
    return (
      <View style={[styles.bubble, styles.mine]}>
        <Text style={styles.mineText}>{message.content}</Text>
      </View>
    );
  }
  return (
    <View style={styles.aiRow}>
      <LinearGradient colors={QuaxGradient} style={styles.aiAvatar}>
        <Ionicons name="sparkles" size={14} color="#fff" />
      </LinearGradient>
      <View style={[styles.bubble, styles.theirs]}>
        {message.pending && !message.content ? (
          <ActivityIndicator size="small" color={Colors.textSecondary} />
        ) : (
          <RichText text={message.content} style={styles.theirsText} />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  list: { paddingHorizontal: Spacing.three, gap: Spacing.three, paddingBottom: Spacing.three },
  bubble: { maxWidth: '85%', borderRadius: Radius.lg, paddingHorizontal: 14, paddingVertical: 10 },
  mine: { alignSelf: 'flex-end', backgroundColor: Colors.accent, borderBottomRightRadius: 6 },
  mineText: { color: '#fff', fontSize: 15, lineHeight: 21 },
  aiRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-end' },
  aiAvatar: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  theirs: { backgroundColor: Colors.surface, borderBottomLeftRadius: 6, flexShrink: 1 },
  theirsText: { color: Colors.text, fontSize: 15, lineHeight: 22 },
  suggestions: { gap: 8, paddingTop: Spacing.two },
  suggestion: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  suggestionText: { color: Colors.text, fontSize: 13, fontWeight: '600' },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginHorizontal: Spacing.three,
    padding: 6,
    paddingLeft: 16,
    borderRadius: Radius.lg,
    backgroundColor: Colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  input: { flex: 1, color: Colors.text, fontSize: 15, maxHeight: 120, paddingVertical: 10 },
  send: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
});
