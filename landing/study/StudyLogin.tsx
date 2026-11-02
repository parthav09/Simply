'use client';

import { useActionState } from 'react';
import { login } from '../app/secretstudy23/actions';

export default function StudyLogin() {
  const [error, action, pending] = useActionState(login, '');
  return <main className="study-login"><section className="study-card">
    <p className="eyebrow">Private access</p>
    <h1>Study room.</h1>
    <p>Enter your password to continue.</p>
    <form action={action}>
      <label htmlFor="study-password">Password</label>
      <input id="study-password" name="password" type="password" autoComplete="current-password" required maxLength={256}/>
      {error && <p role="alert">{error}</p>}
      <button className="study-primary" disabled={pending}>{pending ? 'Checking…' : 'Log in'}</button>
    </form>
  </section></main>;
}
