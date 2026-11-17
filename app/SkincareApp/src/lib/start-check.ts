import { router } from 'expo-router';

import { POLICY_VERSION, User } from './auth';

/** First check (or a new policy version): consent screen first; otherwise straight to the area. */
export function startCheck(user: User | null, reset: () => void) {
  reset();
  router.push(user?.consentVersion === POLICY_VERSION ? '/check/area' : '/check/consent');
}
