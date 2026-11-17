// Entry route: signed-in users open Today, everyone else the Welcome screen.
import { Redirect } from 'expo-router';

import { useAuth } from '@/lib/auth';

export default function Index() {
  const { user } = useAuth();
  return <Redirect href={user ? '/today' : '/welcome'} />;
}
