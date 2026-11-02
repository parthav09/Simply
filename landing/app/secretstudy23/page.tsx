import type { Metadata } from 'next';
import { Suspense } from 'react';
import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { connection } from 'next/server';
import { STUDY_COOKIE, validSession } from '../../study/auth';
import '../../styles/study.css';

export const metadata: Metadata = {
  title: 'Private study · Simply',
  robots: { index: false, follow: false, noarchive: true, nosnippet: true },
};

async function ProtectedStudy() {
  // Retain the local-only boundary as well as requiring authentication.
  if (process.env.NODE_ENV === 'development') {
    // Session expiry is time-sensitive and must never run during prerendering.
    await connection();
    if (!validSession((await cookies()).get(STUDY_COOKIE)?.value)) {
      const { default: StudyLogin } = await import('../../study/StudyLogin');
      return <StudyLogin/>;
    }
    // Never serialize private questions or answers before checking the session.
    const [{ default: StudyRoom }, { studyData }, { logout }] = await Promise.all([
      import('../../study/StudyRoom'),
      import('../../study/content'),
      import('./actions'),
    ]);
    return <><form action={logout} className="study-lock"><button className="study-secondary">Log out</button></form><StudyRoom data={studyData}/></>;
  }
  notFound();
}

export default function Page() {
  if (process.env.NODE_ENV !== 'development') notFound();
  return <Suspense fallback={null}><ProtectedStudy/></Suspense>;
}
