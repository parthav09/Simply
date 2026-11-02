'use client';

import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from 'react';
import { Icon } from './Icons';

type Preference = 'system' | 'light' | 'dark';
const storageKey = 'simply-appearance';
const changeEvent = 'simply-appearance-change';
let fallbackPreference: Preference = 'system';
const ThemeContext = createContext<Preference>('system');

function preference(): Preference {
  try { const value = localStorage.getItem(storageKey); return value === 'light' || value === 'dark' ? value : 'system'; }
  catch { return fallbackPreference; }
}
function subscribe(callback: () => void) {
  window.addEventListener('storage', callback);
  window.addEventListener(changeEvent, callback);
  return () => { window.removeEventListener('storage', callback); window.removeEventListener(changeEvent, callback); };
}
function applyTheme(value: Preference) {
  document.documentElement.dataset.theme = value === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : value;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const value = useSyncExternalStore(subscribe, preference, () => 'system' as Preference);
  useEffect(() => {
    // Read the actual client preference during hydration; preserve the bootstrap colors.
    applyTheme(preference());
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const update = () => applyTheme(preference());
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, [value]);
  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function ThemeControl() {
  const value = useContext(ThemeContext);
  return <label className="theme-control"><Icon name="appearance" size={17}/><span className="sr-only">Appearance</span><select aria-label="Appearance" value={value} onChange={event => {
    const next = event.target.value as Preference;
    fallbackPreference = next;
    try { localStorage.setItem(storageKey, next); } catch { /* The current page can still adopt the selection. */ }
    applyTheme(next);
    window.dispatchEvent(new Event(changeEvent));
  }}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
