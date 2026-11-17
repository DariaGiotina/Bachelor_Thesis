// State of one skin check (area, photos, five answers), the rule that turns the per-photo answers of
// the ML service into one result, and the list of past checks kept on the device.
//
// The shipped model looks at the photo only (the questionnaire did not add measurable accuracy in the
// study), so the answers personalise the text of the result and are stored with it; they are not sent
// to the model. Photos stay in memory for the result screen and are never saved.
import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react';

import type { PastelName } from './theme';
import { AnalyzeResponse, CLASSES, SkinClass } from './ml-api';
import { readJson, writeJson } from './storage';

export type Zone = 'face' | 'forehead' | 'nose' | 'left_cheek' | 'right_cheek' | 'chin';

export const ZONE_LABEL: Record<Zone, string> = {
  face: 'Whole face',
  forehead: 'Forehead',
  nose: 'Nose',
  left_cheek: 'Left cheek',
  right_cheek: 'Right cheek',
  chin: 'Chin',
};

export const CLASS_INFO: Record<SkinClass, { label: string; tone: PastelName; short: string }> = {
  redness_rosacea: { label: 'Redness-type irritation', tone: 'rose', short: 'redness' },
  eczema_dermatitis: { label: 'Dryness or eczema-like', tone: 'sky', short: 'dryness' },
  acne: { label: 'Acne-like breakouts', tone: 'peach', short: 'breakouts' },
  normal_other: { label: 'Another common skin concern', tone: 'mint', short: 'another concern' },
};

export type Answers = {
  skinType?: string;
  duration?: string;
  symptoms?: string[];
  intensity?: string;
  changes?: string[];
  ageRange?: string;
  skinTone?: string;
};

export function answeredCount(a: Answers): number {
  return [
    a.skinType,
    a.duration,
    a.symptoms?.length ? a.symptoms : undefined,
    a.changes?.length ? a.changes : undefined,
    a.ageRange || a.skinTone,
  ].filter(Boolean).length;
}

export type Photo = { zone: Zone; uri: string };

export type PhotoOutcome = { zone: Zone; status: AnalyzeResponse['status']; category: SkinClass | null; confidence: number };

export type CheckResult = {
  id: string;
  date: string;
  zones: Zone[];
  answers: Answers;
  status: AnalyzeResponse['status'];
  category: SkinClass | null; // set only when status is answered
  closest: SkinClass; // most likely class, shown as context when the check is uncertain
  confidence: number; // probability of `category` (answered) or of `closest` (otherwise)
  probabilities: Record<SkinClass, number>;
  perPhoto: PhotoOutcome[];
  model: string;
};

function mean(responses: AnalyzeResponse[]): Record<SkinClass, number> {
  const out = Object.fromEntries(CLASSES.map((c) => [c, 0])) as Record<SkinClass, number>;
  for (const r of responses) for (const c of CLASSES) out[c] += (r.probabilities[c] ?? 0) / responses.length;
  return out;
}

const argmax = (p: Record<SkinClass, number>) => CLASSES.reduce((a, b) => (p[b] > p[a] ? b : a));

/**
 * One result from one or more photos. The service applies its validated decision rule to every
 * photo; this rule only combines them: the check is answered when at least one photo is answered
 * (probabilities averaged over the answered photos), uncertain when no photo is answered but at least
 * one is uncertain, and an unusual photo when every photo is unusual.
 */
export function combine(photos: Photo[], responses: AnalyzeResponse[], answers: Answers, id: string): CheckResult {
  const answered = responses.filter((r) => r.status === 'answered');
  const readable = responses.filter((r) => r.status !== 'unusual_photo');
  const basis = answered.length ? answered : readable.length ? readable : responses;
  const probabilities = mean(basis);
  const top = argmax(probabilities);
  const status: CheckResult['status'] = answered.length ? 'answered' : readable.length ? 'uncertain' : 'unusual_photo';
  return {
    id,
    date: new Date().toISOString(),
    zones: photos.map((p) => p.zone),
    answers,
    status,
    category: status === 'answered' ? top : null,
    closest: top,
    confidence: probabilities[top],
    probabilities,
    perPhoto: responses.map((r, i) => ({ zone: photos[i].zone, status: r.status, category: r.category, confidence: r.confidence })),
    model: responses[0]?.model_sha256 ?? '',
  };
}

export function zonesText(zones: Zone[]): string {
  if (zones.length === 1) return ZONE_LABEL[zones[0]];
  if (zones.length === 2 && zones.includes('left_cheek') && zones.includes('right_cheek')) return 'Both cheeks';
  const names = zones.map((z) => ZONE_LABEL[z].toLowerCase());
  const s = names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function shortDate(iso: string, withYear = false): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(withYear ? { year: 'numeric' } : {}) });
}

export function resultTitle(r: CheckResult): string {
  if (r.status === 'answered' && r.category) return `May indicate ${CLASS_INFO[r.category].short}`;
  return r.status === 'uncertain' ? 'Uncertain, see a professional' : 'Photo not usable';
}

export function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

// ------------------------------------------------------------------ history (on the device)

const historyKey = (userId: string) => `lumiere.history.${userId}`;

export async function loadHistory(userId: string): Promise<CheckResult[]> {
  return readJson<CheckResult[]>(historyKey(userId), []);
}

export async function saveToHistory(userId: string, result: CheckResult): Promise<void> {
  const list = await loadHistory(userId);
  if (list.some((r) => r.id === result.id)) return;
  await writeJson(historyKey(userId), [result, ...list].slice(0, 100));
}

export async function removeFromHistory(userId: string, id: string): Promise<void> {
  const list = await loadHistory(userId);
  await writeJson(historyKey(userId), list.filter((r) => r.id !== id));
}

// ------------------------------------------------------------------ the check in progress

type CheckState = {
  wholeFace: boolean;
  zones: Zone[];
  photos: Photo[];
  answers: Answers;
  result: CheckResult | null;
  setArea: (wholeFace: boolean, zones: Zone[]) => void;
  addPhoto: (p: Photo) => void;
  setAnswers: (patch: Partial<Answers>) => void;
  setResult: (r: CheckResult | null) => void;
  reset: () => void;
  /** zones that still need a photo, in order */
  pendingZones: () => Zone[];
};

const CheckContext = createContext<CheckState | null>(null);

export function SkinCheckProvider({ children }: { children: ReactNode }) {
  const [wholeFace, setWholeFace] = useState(true);
  const [zones, setZones] = useState<Zone[]>(['face']);
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [answers, setAnswersState] = useState<Answers>({});
  const [result, setResult] = useState<CheckResult | null>(null);

  const setArea = useCallback((whole: boolean, z: Zone[]) => {
    setWholeFace(whole);
    setZones(whole ? ['face'] : z);
    setPhotos([]);
  }, []);
  const addPhoto = useCallback((p: Photo) => setPhotos((list) => [...list.filter((x) => x.zone !== p.zone), p]), []);
  const setAnswers = useCallback((patch: Partial<Answers>) => setAnswersState((a) => ({ ...a, ...patch })), []);
  const reset = useCallback(() => {
    setWholeFace(true);
    setZones(['face']);
    setPhotos([]);
    setAnswersState({});
    setResult(null);
  }, []);
  const pendingZones = useCallback(() => zones.filter((z) => !photos.some((p) => p.zone === z)), [zones, photos]);

  const value = useMemo(
    () => ({ wholeFace, zones, photos, answers, result, setArea, addPhoto, setAnswers, setResult, reset, pendingZones }),
    [wholeFace, zones, photos, answers, result, setArea, addPhoto, setAnswers, reset, pendingZones],
  );
  return <CheckContext.Provider value={value}>{children}</CheckContext.Provider>;
}

export function useSkinCheck() {
  const ctx = useContext(CheckContext);
  if (!ctx) throw new Error('useSkinCheck must be used inside SkinCheckProvider');
  return ctx;
}
