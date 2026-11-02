import Link from 'next/link';
import { Icon } from '../ui/Icons';
import { ThemeControl } from '../ui/ThemeProvider';

const Brand = () => <><span className="brand-mark" aria-hidden="true"><i/><i/><i/></span>simply<span className="brand-dot">.</span></>;

export default function SiteNav({ active = 'home', labDisabled = false }: { active?: 'home' | 'lab' | 'evaluation'; labDisabled?: boolean }) {
  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <nav className={`product-nav ${active === 'lab' ? 'lab-nav' : ''}`} aria-label="Main navigation">
      <Link href="/" className="brand" aria-label="Simply home"><Brand/></Link>
      <div className="nav-links"><Link href="/" aria-current={active === 'home' ? 'page' : undefined}>Overview</Link>{labDisabled?<button disabled>Shopper lab</button>:<Link href="/lab" aria-current={active === 'lab' ? 'page' : undefined}>Shopper lab</Link>}<Link href="/evaluation" aria-current={active === 'evaluation' ? 'page' : undefined}>Evidence</Link></div>
      <div className="nav-end"><ThemeControl/>{active !== 'lab' && (labDisabled?<button className="nav-action" disabled>Open lab<Icon name="arrow" size={15}/></button>:<Link className="nav-action" href="/lab">Open lab<Icon name="arrow" size={15}/></Link>)}</div>
    </nav>
  </>;
}
