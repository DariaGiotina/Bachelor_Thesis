// Accounts and session.
//
// The main backend (FastAPI auth with Argon2id + JWT) is not built yet, so this provider keeps
// accounts on the device: a development stand-in with the same rules the backend will enforce
// (passwords of at least 12 characters that are not common, sign-in paused for 15 minutes after
// 5 failed attempts). Only a salted SHA-256 of the password is stored, never the password. When the
// backend exists, `register`, `logIn` and `logOut` call its endpoints and the screens stay the same.
import * as Crypto from 'expo-crypto';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { readJson, secret, writeJson } from './storage';

export type User = {
  id: string;
  name: string;
  email: string;
  createdAt: string;
  consentVersion: string | null; // privacy policy version accepted for photo + skin data
  ageRange: string | null;
  skinTone: string | null; // Fitzpatrick I-VI or null
};

type StoredAccount = User & { salt: string; passwordHash: string; failed: number; lockedUntil: number | null };

const ACCOUNTS_KEY = 'lumiere.accounts.v1';
const SESSION_KEY = 'lumiere.session';
export const POLICY_VERSION = '1.2';
export const MAX_ATTEMPTS = 5;
export const LOCK_MINUTES = 15;
export const MIN_PASSWORD = 12;

// A few of the most common passwords that pass the length rule; the backend checks a full list.
const COMMON = new Set([
  '123456789012', 'password1234', 'qwertyuiopas', '111111111111', 'iloveyou1234',
  'passwordpassword', 'qwerty123456', '1234567890123', 'abcdefghijkl', 'aaaaaaaaaaaa',
]);

export class AuthError extends Error {}

export function passwordStrength(pw: string): { score: 0 | 1 | 2 | 3 | 4; message: string } {
  if (!pw) return { score: 0, message: `At least ${MIN_PASSWORD} characters and not a common password.` };
  if (pw.length < MIN_PASSWORD) return { score: 1, message: `Too short. At least ${MIN_PASSWORD} characters.` };
  if (COMMON.has(pw.toLowerCase())) return { score: 1, message: 'This password is too common.' };
  const kinds = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (pw.length >= 16 || kinds >= 3) return { score: kinds >= 3 && pw.length >= 14 ? 4 : 3, message: 'Strong. At least 12 characters and not a common password.' };
  return { score: 2, message: 'Fair. A longer password or a mix of characters is stronger.' };
}

export function isEmail(s: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s.trim());
}

async function hash(salt: string, password: string) {
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, `${salt}:${password}`);
}

function publicUser(a: StoredAccount): User {
  const { salt: _s, passwordHash: _p, failed: _f, lockedUntil: _l, ...user } = a;
  return user;
}

type AuthState = {
  ready: boolean;
  user: User | null;
  register: (name: string, email: string, password: string) => Promise<void>;
  logIn: (email: string, password: string, keepSignedIn: boolean) => Promise<void>;
  logOut: () => Promise<void>;
  updateUser: (patch: Partial<Pick<User, 'name' | 'consentVersion' | 'ageRange' | 'skinTone'>>) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const id = await secret.get(SESSION_KEY);
        if (id) {
          const accounts = await readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
          const found = accounts.find((a) => a.id === id);
          if (found) setUser(publicUser(found));
        }
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const mail = email.trim().toLowerCase();
    if (!name.trim()) throw new AuthError('Please enter your name.');
    if (!isEmail(mail)) throw new AuthError('Please enter a valid email address.');
    if (passwordStrength(password).score < 2) throw new AuthError(passwordStrength(password).message);
    const accounts = await readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
    if (accounts.some((a) => a.email === mail)) throw new AuthError('An account with this email already exists.');
    const salt = Crypto.randomUUID();
    const account: StoredAccount = {
      id: Crypto.randomUUID(),
      name: name.trim(),
      email: mail,
      createdAt: new Date().toISOString(),
      consentVersion: null,
      ageRange: null,
      skinTone: null,
      salt,
      passwordHash: await hash(salt, password),
      failed: 0,
      lockedUntil: null,
    };
    await writeJson(ACCOUNTS_KEY, [...accounts, account]);
    await secret.set(SESSION_KEY, account.id);
    setUser(publicUser(account));
  }, []);

  const logIn = useCallback(async (email: string, password: string, keepSignedIn: boolean) => {
    const mail = email.trim().toLowerCase();
    const accounts = await readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
    const i = accounts.findIndex((a) => a.email === mail);
    // Same message for an unknown email and a wrong password, so the form does not reveal accounts.
    const wrong = new AuthError('Email or password is not right.');
    if (i < 0) throw wrong;
    const a = accounts[i];
    const now = Date.now();
    if (a.lockedUntil && a.lockedUntil > now) {
      const min = Math.ceil((a.lockedUntil - now) / 60000);
      throw new AuthError(`Too many attempts. Try again in ${min} minute${min === 1 ? '' : 's'}.`);
    }
    if ((await hash(a.salt, password)) !== a.passwordHash) {
      a.failed = (a.lockedUntil ? 0 : a.failed) + 1;
      a.lockedUntil = null;
      if (a.failed >= MAX_ATTEMPTS) {
        a.lockedUntil = now + LOCK_MINUTES * 60000;
        a.failed = 0;
      }
      await writeJson(ACCOUNTS_KEY, accounts);
      if (a.lockedUntil) throw new AuthError(`Too many attempts. Sign-in is paused for ${LOCK_MINUTES} minutes.`);
      throw wrong;
    }
    a.failed = 0;
    a.lockedUntil = null;
    await writeJson(ACCOUNTS_KEY, accounts);
    if (keepSignedIn) await secret.set(SESSION_KEY, a.id);
    else await secret.remove(SESSION_KEY);
    setUser(publicUser(a));
  }, []);

  const logOut = useCallback(async () => {
    await secret.remove(SESSION_KEY);
    setUser(null);
  }, []);

  const updateUser = useCallback<AuthState['updateUser']>(
    async (patch) => {
      if (!user) return;
      const accounts = await readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
      const a = accounts.find((x) => x.id === user.id);
      if (!a) return;
      Object.assign(a, patch);
      await writeJson(ACCOUNTS_KEY, accounts);
      setUser(publicUser(a));
    },
    [user],
  );

  const value = useMemo(() => ({ ready, user, register, logIn, logOut, updateUser }), [ready, user, register, logIn, logOut, updateUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
