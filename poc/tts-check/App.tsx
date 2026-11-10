// Throwaway PoC (design D9): list installed Bangla/Arabic TTS voices and speak sample translations.
// Not the base of the Week 3 app.
import * as Speech from 'expo-speech';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Platform, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';

import data from './samples.json';

type Lang = 'ar-SA' | 'bn-BD';
type Sample = { id: string; language: Lang; text: string };

const LANGS: { code: Lang; prefix: string; label: string }[] = [
  { code: 'ar-SA', prefix: 'ar', label: 'Arabic (target ar-SA)' },
  { code: 'bn-BD', prefix: 'bn', label: 'Bangla (target bn-BD)' },
];

const samples = data.samples as Sample[];

function matches(voice: Speech.Voice, prefix: string): boolean {
  const lang = voice.language.toLowerCase().replace('_', '-');
  return lang === prefix || lang.startsWith(`${prefix}-`);
}

export default function App() {
  const [voices, setVoices] = useState<Speech.Voice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Partial<Record<Lang, string>>>({});
  const [speaking, setSpeaking] = useState<string | null>(null);

  useEffect(() => {
    Speech.getAvailableVoicesAsync()
      .then((all) => {
        setVoices(all);
        // Prefer an exact locale match (ar-SA / bn-BD), then any voice of that language.
        const initial: Partial<Record<Lang, string>> = {};
        for (const l of LANGS) {
          const own = all.filter((v) => matches(v, l.prefix));
          const exact = own.find((v) => v.language.replace('_', '-').toLowerCase() === l.code.toLowerCase());
          if (exact ?? own[0]) initial[l.code] = (exact ?? own[0]).identifier;
        }
        setSelected(initial);
      })
      .catch((e: unknown) => {
        setVoices([]);
        setError(String(e));
      });
  }, []);

  const byLang = useMemo(() => {
    const out: Record<Lang, Speech.Voice[]> = { 'ar-SA': [], 'bn-BD': [] };
    for (const l of LANGS) out[l.code] = (voices ?? []).filter((v) => matches(v, l.prefix));
    return out;
  }, [voices]);

  const speak = useCallback(
    (s: Sample) => {
      const voice = selected[s.language];
      if (!voice) return; // no voice: text stays visible, nothing is spoken
      Speech.stop();
      setSpeaking(s.id);
      Speech.speak(s.text, {
        language: s.language,
        voice,
        rate: 0.95,
        onDone: () => setSpeaking(null),
        onStopped: () => setSpeaking(null),
        onError: () => setSpeaking(null),
      });
    },
    [selected],
  );

  const report = useCallback(() => {
    const payload = {
      platform: Platform.OS,
      osVersion: Platform.Version,
      checkedAt: new Date().toISOString(),
      voices: Object.fromEntries(
        LANGS.map((l) => [
          l.code,
          byLang[l.code].map((v) => ({ id: v.identifier, name: v.name, language: v.language, quality: v.quality })),
        ]),
      ),
      selected,
      totalVoicesOnDevice: voices?.length ?? 0,
    };
    Share.share({ message: JSON.stringify(payload, null, 2) }).catch(() => undefined);
  }, [byLang, selected, voices]);

  return (
    <View style={styles.root}>
      <StatusBar style="auto" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Averon TTS check</Text>
        <Text style={styles.meta}>
          {Platform.OS} {String(Platform.Version)} · {voices === null ? 'loading voices…' : `${voices.length} voices on device`}
        </Text>
        {error ? <Text style={styles.warn}>Could not list voices: {error}</Text> : null}

        {LANGS.map((l) => (
          <View key={l.code} style={styles.section}>
            <Text style={styles.h2}>{l.label}</Text>
            {voices !== null && byLang[l.code].length === 0 ? (
              <Text style={styles.warn}>No {l.prefix} voice installed. Translations are shown as text only.</Text>
            ) : null}
            {byLang[l.code].map((v) => {
              const active = selected[l.code] === v.identifier;
              const saudi = v.language.replace('_', '-').toLowerCase() === 'ar-sa';
              return (
                <Pressable
                  key={v.identifier}
                  onPress={() => setSelected((s) => ({ ...s, [l.code]: v.identifier }))}
                  style={[styles.voice, active && styles.voiceActive]}
                >
                  <Text style={styles.voiceName}>
                    {active ? '● ' : '○ '}
                    {v.name} {saudi ? '· Saudi locale' : ''}
                  </Text>
                  <Text style={styles.voiceMeta}>
                    {v.language} · {v.quality} · {v.identifier}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        ))}

        <View style={styles.section}>
          <Text style={styles.h2}>Sample translations</Text>
          {samples.map((s) => {
            const hasVoice = Boolean(selected[s.language]);
            return (
              <View key={s.id} style={styles.sample}>
                <Text style={[styles.sampleText, s.language === 'ar-SA' && styles.rtl]}>{s.text}</Text>
                <View style={styles.row}>
                  <Text style={styles.voiceMeta}>
                    {s.id} · {s.language}
                  </Text>
                  <Pressable
                    disabled={!hasVoice}
                    onPress={() => speak(s)}
                    style={[styles.button, !hasVoice && styles.buttonDisabled]}
                  >
                    <Text style={styles.buttonText}>
                      {!hasVoice ? 'No voice' : speaking === s.id ? 'Speaking…' : 'Speak'}
                    </Text>
                  </Pressable>
                </View>
              </View>
            );
          })}
        </View>

        <Pressable onPress={report} style={[styles.button, styles.share]}>
          <Text style={styles.buttonText}>Share voice report (for poc/reports/tts.md)</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 16, paddingTop: 56, paddingBottom: 48 },
  title: { fontSize: 22, fontWeight: '700' },
  meta: { color: '#555', marginTop: 4 },
  section: { marginTop: 24 },
  h2: { fontSize: 17, fontWeight: '600', marginBottom: 8 },
  warn: { color: '#a15c00', backgroundColor: '#fff4e0', padding: 8, borderRadius: 6, marginBottom: 8 },
  voice: { padding: 10, borderWidth: 1, borderColor: '#ddd', borderRadius: 8, marginBottom: 6 },
  voiceActive: { borderColor: '#2563eb', backgroundColor: '#eff6ff' },
  voiceName: { fontWeight: '500' },
  voiceMeta: { color: '#666', fontSize: 12, marginTop: 2, flexShrink: 1 },
  sample: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#eee' },
  sampleText: { fontSize: 20, lineHeight: 30 },
  rtl: { writingDirection: 'rtl', textAlign: 'right' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 6, gap: 8 },
  button: { backgroundColor: '#2563eb', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  buttonDisabled: { backgroundColor: '#9ca3af' },
  buttonText: { color: '#fff', fontWeight: '600' },
  share: { marginTop: 24, alignItems: 'center' },
});
