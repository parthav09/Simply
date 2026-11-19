import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Deck from '../../present/Deck';
import '../../styles/present.css';

export const metadata: Metadata = {
  title: 'Presentation · Simply',
  robots: { index: false, follow: false, noarchive: true, nosnippet: true },
};

/** Local-only presentation: available in development, like the study room. */
export default function Page() {
  if (process.env.NODE_ENV !== 'development') notFound();
  return <Deck/>;
}
