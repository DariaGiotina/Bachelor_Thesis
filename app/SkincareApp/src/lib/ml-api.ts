// Client of the ML inference service (api/ml_service): one photo in, one informational answer out.
//
// The photo is first downscaled on the phone (longest side 1024 px, JPEG): the model works on 448 px,
// so a full-size camera photo would only make the upload slower. It is then sent as the raw request
// body (Content-Type image/jpeg), which is what POST /v1/analyze expects.
//
// Service address: EXPO_PUBLIC_ML_URL if set; otherwise, in development, the computer that runs the
// Expo dev server, port 8001 (start the service with --host 0.0.0.0 so the phone can reach it).
import Constants from 'expo-constants';
import { File } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { Platform } from 'react-native';

export const CLASSES = ['acne', 'eczema_dermatitis', 'redness_rosacea', 'normal_other'] as const;
export type SkinClass = (typeof CLASSES)[number];

export type AnalyzeResponse = {
  status: 'answered' | 'uncertain' | 'unusual_photo';
  category: SkinClass | null;
  confidence: number;
  probabilities: Record<SkinClass, number>;
  knn_score: number;
  notice: string;
  model_sha256: string;
};

export class AnalyzeError extends Error {
  constructor(message: string, readonly kind: 'network' | 'photo' | 'service') {
    super(message);
  }
}

const MAX_SIDE = 1024;
const TIMEOUT_MS = 60_000;

export function mlServiceUrl(): string {
  const env = process.env.EXPO_PUBLIC_ML_URL;
  if (env) return env.replace(/\/$/, '');
  if (Platform.OS === 'web') return 'http://localhost:8001';
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return `http://${host ?? 'localhost'}:8001`;
}

/** Downscale to MAX_SIDE on the longest side and re-encode as JPEG; returns the new uri. */
export async function preparePhoto(uri: string): Promise<string> {
  const first = await ImageManipulator.manipulate(uri).renderAsync();
  const longest = Math.max(first.width, first.height);
  let image = first;
  if (longest > MAX_SIDE) {
    const ctx = ImageManipulator.manipulate(uri);
    // both sides given explicitly: the web implementation does not derive a missing (null) side
    const scale = MAX_SIDE / longest;
    ctx.resize({ width: Math.round(first.width * scale), height: Math.round(first.height * scale) });
    image = await ctx.renderAsync();
  }
  const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.9 });
  return saved.uri;
}

export async function analyzePhoto(uri: string): Promise<AnalyzeResponse> {
  const url = `${mlServiceUrl()}/v1/analyze`;
  const headers: Record<string, string> = { 'Content-Type': 'image/jpeg' };
  const key = process.env.EXPO_PUBLIC_ML_SERVICE_KEY; // development only; in production the backend calls the service
  if (key) headers['X-Service-Key'] = key;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    if (Platform.OS === 'web') {
      const body = await (await fetch(uri)).blob();
      res = await fetch(url, { method: 'POST', headers, body, signal: controller.signal });
    } else {
      res = (await expoFetch(url, { method: 'POST', headers, body: new File(uri), signal: controller.signal })) as unknown as Response;
    }
  } catch {
    throw new AnalyzeError(`Can't reach the analysis service at ${mlServiceUrl()}. Check that it is running and that the phone is on the same Wi-Fi.`, 'network');
  } finally {
    clearTimeout(timer);
  }

  if (res.ok) return (await res.json()) as AnalyzeResponse;
  let detail = '';
  try {
    detail = ((await res.json()) as { detail?: string }).detail ?? '';
  } catch {
    // body was not JSON
  }
  if ([400, 413, 415].includes(res.status)) throw new AnalyzeError(detail || 'The photo could not be read.', 'photo');
  if (res.status === 503) throw new AnalyzeError('The analysis model is not loaded on the service.', 'service');
  if (res.status === 401) throw new AnalyzeError('The analysis service refused the request (service key).', 'service');
  throw new AnalyzeError(`The analysis service answered ${res.status}${detail ? `: ${detail}` : ''}.`, 'service');
}
