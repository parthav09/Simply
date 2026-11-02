import 'server-only';
import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

export const STUDY_COOKIE = 'simply-study-session';
export const SESSION_SECONDS = 60 * 60 * 8;

function equal(left: string, right: string) {
  return timingSafeEqual(createHash('sha256').update(left).digest(), createHash('sha256').update(right).digest());
}

export function passwordMatches(candidate: unknown): boolean {
  const expected = process.env.STUDY_PASSWORD;
  return !!expected && typeof candidate === 'string' && candidate.length <= 256 && equal(candidate, expected);
}

function sign(payload: string): string {
  return createHmac('sha256', process.env.STUDY_SESSION_SECRET!).update(`study-v1:${payload}`).digest('hex');
}

export function createSession(now = Date.now()): string {
  if (!process.env.STUDY_SESSION_SECRET || !process.env.STUDY_PASSWORD) throw new Error('Study authentication is not configured');
  const payload = `${Math.floor(now / 1000) + SESSION_SECONDS}.${randomBytes(24).toString('hex')}`;
  return `${payload}.${sign(payload)}`;
}

export function validSession(token: string | undefined, now = Date.now()): boolean {
  if (!process.env.STUDY_SESSION_SECRET || !process.env.STUDY_PASSWORD || !token || token.length > 200) return false;
  const parts = /^(\d+)\.([a-f0-9]{48})\.([a-f0-9]{64})$/.exec(token);
  if (!parts) return false;
  const expiry = Number(parts[1]);
  const seconds = Math.floor(now / 1000);
  return Number.isSafeInteger(expiry) && expiry > seconds && expiry <= seconds + SESSION_SECONDS
    && equal(parts[3], sign(`${parts[1]}.${parts[2]}`));
}
