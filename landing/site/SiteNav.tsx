import Link from 'next/link';
import { ThemeControl } from '../ui/ThemeProvider';

const Brand = () => <><span className="brand-mark" aria-hidden="true"><i/><i/><i/></span>simply<span className="brand-dot">.</span></>;

type Page = 'home' | 'lab' | 'replays' | 'evaluation';
const links: { id: Page; href: string; label: string }[] = [
  { id: 'replays', href: '/replays', label: 'Replays' },
  { id: 'lab', href: '/lab', label: 'Live run' },
  { id: 'evaluation', href: '/evaluation', label: 'Results' },
];

export default function SiteNav({ active = 'home' }: { active?: Page }) {
  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <nav className={`product-nav ${active === 'lab' || active === 'replays' ? 'lab-nav' : ''}`} aria-label="Main navigation">
      <Link href="/" className="brand" aria-label="Simply home"><Brand/></Link>
      <div className="nav-links">{links.map(l => <Link key={l.id} href={l.href} aria-current={active === l.id ? 'page' : undefined}>{l.label}</Link>)}</div>
      <div className="nav-end"><ThemeControl/></div>
    </nav>
  </>;
}
