// 19 · Analysing: prepares every photo, sends it to the ML service and opens the matching result.
import * as Crypto from 'expo-crypto';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Bar, Button, Callout, Heading, Screen } from '@/components/ui';
import { AnalyzeError, analyzePhoto, AnalyzeResponse, preparePhoto } from '@/lib/ml-api';
import { answeredCount, combine, useSkinCheck, ZONE_LABEL } from '@/lib/skin-check';
import { colors, radius, type } from '@/lib/theme';

const STEPS = ['Preparing the photos', 'Sending them to the analysis', 'Comparing with known patterns', 'Writing your result'];

export default function Analysing() {
  const check = useSkinCheck();
  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0.05);
  const [error, setError] = useState<AnalyzeError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1);

  useEffect(() => {
    if (started.current === attempt) return; // run once per attempt (React may mount effects twice in development)
    started.current = attempt;
    let cancelled = false;
    (async () => {
      setError(null);
      setStep(0);
      try {
        const photos = check.photos;
        if (!photos.length) throw new AnalyzeError('No photo was taken.', 'photo');
        const prepared: string[] = [];
        for (const p of photos) prepared.push(await preparePhoto(p.uri));
        setStep(1);
        setProgress(0.3);
        const responses: AnalyzeResponse[] = [];
        for (let i = 0; i < prepared.length; i++) {
          responses.push(await analyzePhoto(prepared[i]));
          setStep(2);
          setProgress(0.3 + (0.6 * (i + 1)) / prepared.length);
        }
        setStep(3);
        const result = combine(photos, responses, check.answers, Crypto.randomUUID());
        if (cancelled) return;
        check.setResult(result);
        setProgress(1);
        router.replace(result.status === 'answered' ? '/check/result' : result.status === 'uncertain' ? '/check/uncertain' : '/check/unusual');
      } catch (e) {
        if (!(e instanceof AnalyzeError)) console.warn('skin check failed', e);
        if (!cancelled) setError(e instanceof AnalyzeError ? e : new AnalyzeError('The photo could not be prepared.', 'photo'));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  const answers = answeredCount(check.answers);

  return (
    <Screen
      contentStyle={{ paddingHorizontal: 24, paddingTop: 56, gap: 32 }}
      footer={
        error ? (
          <>
            <Button label="Try again" onPress={() => setAttempt((a) => a + 1)} />
            <Button label="Retake photo" variant="secondary" onPress={() => router.replace('/check/capture')} />
          </>
        ) : (
          <Text style={[type.caption, { textAlign: 'center' }]}>Informational only. Not a diagnosis.</Text>
        )
      }>
      <Heading title={error ? 'We couldn’t check your photos' : 'Checking your photos'} subtitle={error ? undefined : 'This usually takes a few seconds.'} />
      <View style={{ flexDirection: 'row', gap: 10 }}>
        {check.photos.slice(0, 2).map((p) => (
          <View key={p.zone} style={styles.photo}>
            <Image source={{ uri: p.uri }} style={StyleSheet.absoluteFill} contentFit="cover" />
            {!error ? <View style={[styles.scanLine, { top: `${Math.round(progress * 90)}%` }]} /> : null}
            <View style={styles.label}>
              <Text style={[type.caption, { color: colors.ink }]}>{ZONE_LABEL[p.zone]}</Text>
            </View>
          </View>
        ))}
      </View>
      {error ? (
        <Callout icon="alert" tone="flag">
          {error.message}
        </Callout>
      ) : (
        <>
          <View style={{ gap: 8 }}>
            <Bar value={progress} />
            <Text style={type.label}>
              {check.photos.length} photo{check.photos.length === 1 ? '' : 's'} · {answers} answer{answers === 1 ? '' : 's'}
            </Text>
          </View>
          <View style={{ gap: 18 }}>
            {STEPS.map((s, i) => (
              <View key={s} style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}>
                <View
                  style={[
                    styles.dot,
                    i < step && { backgroundColor: colors.accent, borderWidth: 0 },
                    i === step && { borderColor: colors.accent },
                  ]}>
                  {i < step ? <Icon name="check" size={16} color={colors.white} /> : null}
                </View>
                <Text style={i === step ? type.bodyStrong : [type.body, i > step && { color: colors.ink3 }]}>{s}</Text>
              </View>
            ))}
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  photo: { flex: 1, height: 190, borderRadius: radius.lg, overflow: 'hidden', backgroundColor: colors.tint },
  scanLine: { position: 'absolute', left: 0, right: 0, height: 3, backgroundColor: colors.accent },
  label: { position: 'absolute', left: 10, bottom: 10, backgroundColor: colors.white, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4 },
  dot: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: colors.tintStrong, alignItems: 'center', justifyContent: 'center' },
});
