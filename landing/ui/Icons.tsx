import type { CSSProperties } from 'react';

export type IconName = 'appearance' | 'arrow' | 'map' | 'chart' | 'play' | 'pause' | 'back' | 'next' | 'reset' | 'route' | 'heat' | 'bag' | 'users' | 'check' | 'download' | 'plus' | 'minus' | 'info' | 'clock' | 'spark';
const paths: Record<IconName, string> = {
  appearance: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-18v18M12 7a5 5 0 0 1 0 10',
  arrow: 'M5 12h14m-6-6 6 6-6 6', map: 'm3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15m6-12v15',
  chart: 'M4 4v16h16M8 15v-4m5 4V7m5 8v-6', play: 'm9 5 11 7-11 7V5Z', pause: 'M8 5v14M16 5v14',
  back: 'M6 5v14m12-14L8 12l10 7V5Z', next: 'M18 5v14M6 5l10 7-10 7V5Z', reset: 'M4 10a8 8 0 1 1 2 8M4 4v6h6',
  route: 'M6 5a2 2 0 1 0 0 .01M18 19a2 2 0 1 0 0 .01M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7',
  heat: 'M12 3c1 5-5 6-5 11a5 5 0 0 0 10 0c0-3-2-5-2-5s0 4-3 4c2-4 2-7 0-10Z',
  bag: 'M5 8h14l1 12H4L5 8Zm3 0V6a4 4 0 0 1 8 0v2', users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 9v-2a6 6 0 0 1 12 0v2m2-16a4 4 0 0 1 0 8m1 3a5 5 0 0 1 5 5',
  check: 'm5 12 4 4L19 6', download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5', plus: 'M12 5v14M5 12h14', minus: 'M5 12h14',
  info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm0-11v6m0-10v.1', clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-14v5l3 2',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
};
export function Icon({ name, size = 18, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" style={style}><path d={paths[name]} /></svg>;
}
