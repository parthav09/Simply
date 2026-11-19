import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import TechDeck from '../../../present/TechDeck';
import '../../../styles/present.css';

export const metadata: Metadata = {
  title: 'Technical presentation · Simply',
  robots: { index: false, follow: false, noarchive: true, nosnippet: true },
};

/** Local-only technical draft of the presentation, like the overview at /present. */
export default function Page() {
  if (process.env.NODE_ENV !== 'development') notFound();
  return <TechDeck/>;
}
