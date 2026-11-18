import Link from 'next/link';
import ImpulseReceipt from '../ui/ImpulseReceipt';
import SiteNav from './SiteNav';
import HoverFx from './HoverFx';
import { Wordmark } from './Brand';
import { Icon, type IconName } from '../ui/Icons';

const steps = [
  { title: 'Give shoppers a list', body: 'Ten simulated shoppers, each with a list, a budget and a personality.' },
  { title: 'Let a model shop', body: 'The model picks one move at a time. Python validates and records every move.' },
  { title: 'Flag the impulse buys', body: 'Anything picked up that wasn’t on the list is flagged, with the shelf, price and reason.' },
];

const surfaces: { href: string; icon: IconName; title: string; body: string; cta: string }[] = [
  { href: '/replays', icon: 'play', title: 'Replays', body: 'Scrub through recorded trips on the store map. Playback never changes what happened.', cta: 'Open replays' },
  { href: '/lab', icon: 'map', title: 'Live run', body: 'Watch a Python-owned session stream into the lab, move by move, as it is committed.', cta: 'Open the lab' },
  { href: '/evaluation', icon: 'chart', title: 'Results', body: 'Compare layouts and models on impulse buys, list fulfilment and failed actions.', cta: 'See the results' },
];

export default function Landing() {
  return <main className="marketing-page">
    <HoverFx/>
    <SiteNav/>
    <section className="hero" id="main-content">
      <div className="hero-copy">
        <p className="hero-pill"><span className="status-dot"/>Impulse-buy simulator.</p>
        <h1>Spot the <span className="hl">impulse buy.</span></h1>
        <p className="hero-lede">Simply sends AI shoppers through a store with a list and a budget, then shows which items they <em>didn’t</em> plan to buy: where, what it cost, and why.</p>
        <div className="hero-actions">
          <Link href="/replays" className="marketing-primary">Watch a replay <Icon name="arrow" size={17}/></Link>
          <Link href="/evaluation" className="marketing-secondary">See the results</Link>
        </div>
        <ul className="hero-legend" aria-label="Receipt legend">
          <li><span className="tag tag-planned">On list</span>planned</li>
          <li><span className="tag tag-impulse">Impulse</span>not on the list</li>
        </ul>
      </div>
      <div className="hero-stage"><ImpulseReceipt/></div>
    </section>

    <section className="band" aria-label="How Simply works">
      <div className="band-inner">
        <header className="band-head">
          <p className="band-eyebrow">How it works</p>
          <h2>From shopping list to receipt, one move at a time.</h2>
        </header>
        <div className="steps">
          {steps.map((step, i) => <article key={step.title}>
            <span className="step-n">0{i + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>)}
        </div>
      </div>
    </section>

    <section className="surfaces" aria-label="Explore Simply">
      <header>
        <p className="eyebrow">Explore</p>
        <h2>Three ways into the same recorded run.</h2>
      </header>
      <div className="surface-grid">
        {surfaces.map(s => <Link key={s.href} href={s.href} className="surface-card">
          <span className="surface-icon"><Icon name={s.icon} size={20}/></span>
          <h3>{s.title}</h3>
          <p>{s.body}</p>
          <span className="surface-cta">{s.cta} <Icon name="arrow" size={15}/></span>
        </Link>)}
      </div>
    </section>

    <section className="cta" aria-label="Get started">
      <div>
        <h2>See where the list ends.</h2>
        <p>Every receipt is rebuilt from a saved Python recording, never a script.</p>
      </div>
      <Link href="/replays" className="cta-button">Watch a replay <Icon name="arrow" size={17}/></Link>
    </section>

    <footer className="marketing-footer">
      <Link href="/" className="brand" aria-label="Simply home"><Wordmark/></Link>
      <p>Simulated shoppers help explore hypotheses. They don’t predict real customer behavior.</p>
    </footer>
  </main>;
}
