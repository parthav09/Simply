'use server';

import { cookies } from 'next/headers';
import { notFound, redirect } from 'next/navigation';
import { createSession, passwordMatches, SESSION_SECONDS, STUDY_COOKIE } from '../../study/auth';

export async function login(_previous: string, form: FormData): Promise<string> {
  if (process.env.NODE_ENV !== 'development') notFound();
  if (!passwordMatches(form.get('password'))) return 'Incorrect password.';
  if (!process.env.STUDY_SESSION_SECRET) return 'Study login is not configured.';
  (await cookies()).set(STUDY_COOKIE, createSession(), {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV !== 'development',
    path: '/secretstudy23',
    maxAge: SESSION_SECONDS,
  });
  redirect('/secretstudy23');
}

export async function logout(): Promise<void> {
  if (process.env.NODE_ENV !== 'development') notFound();
  (await cookies()).set(STUDY_COOKIE, '', {
    httpOnly: true, sameSite: 'strict', secure: false,
    path: '/secretstudy23', maxAge: 0,
  });
  redirect('/secretstudy23');
}
