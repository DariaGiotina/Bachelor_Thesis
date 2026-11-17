// Wording of the result screen. Informational only: "may indicate", never a diagnosis or a treatment.
import type { PastelName } from './theme';
import type { SkinClass } from './ml-api';
import type { Answers } from './skin-check';

const MEANING: Record<SkinClass, string> = {
  redness_rosacea:
    'The photo shows a pattern the model links to redness-type irritation. This kind of pattern often settles with a simpler, fragrance-free routine and daily sun protection.',
  eczema_dermatitis:
    'The photo shows a pattern the model links to dry or eczema-like skin. Gentle cleansing, a fragrance-free moisturiser and lukewarm rather than hot water are often a good start.',
  acne: 'The photo shows a pattern the model links to acne-like breakouts. Non-comedogenic products, a light moisturiser and not picking at spots are often a good start.',
  normal_other:
    'The photo looks most like other common skin concerns that Lumière does not tell apart. It only checks for acne-like breakouts, eczema-like dryness and redness-type irritation.',
};

export function meaningText(category: SkinClass, answers: Answers): string {
  const symptoms = (answers.symptoms ?? []).filter((s) => s !== 'None of these').map((s) => s.toLowerCase());
  const changes = (answers.changes ?? []).filter((s) => s !== 'Not sure').map((s) => s.toLowerCase());
  const said: string[] = [];
  if (symptoms.length) said.push(symptoms.join(', '));
  if (changes.length) said.push(`a recent change (${changes.join(', ')})`);
  const extra = said.length ? ` You mentioned ${said.join(' and ')}, which can be worth noting if you talk to a professional.` : '';
  return MEANING[category] + extra;
}

export const ROUTINE_IDEA: Record<SkinClass, { title: string; steps: [string, string, PastelName][] }> = {
  redness_rosacea: {
    title: 'A calming routine idea',
    steps: [
      ['Gentle cleanser', 'Cleanse', 'sky'],
      ['Soothing serum', 'Treat', 'peach'],
      ['Barrier cream', 'Moisturise', 'rose'],
      ['Mineral SPF (morning)', 'Protect', 'butter'],
    ],
  },
  eczema_dermatitis: {
    title: 'A comforting routine idea',
    steps: [
      ['Cream cleanser', 'Cleanse', 'sky'],
      ['Fragrance-free rich cream', 'Moisturise', 'rose'],
      ['Mineral SPF (morning)', 'Protect', 'butter'],
    ],
  },
  acne: {
    title: 'A clarifying routine idea',
    steps: [
      ['Gentle gel cleanser', 'Cleanse', 'sky'],
      ['Niacinamide serum', 'Treat', 'peach'],
      ['Light gel moisturiser', 'Moisturise', 'rose'],
      ['Oil-free SPF (morning)', 'Protect', 'butter'],
    ],
  },
  normal_other: {
    title: 'A simple routine idea',
    steps: [
      ['Gentle cleanser', 'Cleanse', 'sky'],
      ['Moisturiser', 'Moisturise', 'rose'],
      ['SPF (morning)', 'Protect', 'butter'],
    ],
  },
};
