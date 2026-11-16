import Link from 'next/link';
import ImpulseReceipt from '../ui/ImpulseReceipt';
import ImpulseReplayDemo from '../ui/ImpulseReplayDemo';
import SiteNav from './SiteNav';
import { Icon } from '../ui/Icons';

const steps = [
  { n: '01', title: 'Give them a list.', body: 'Ten shoppers, each with a shopping list, a budget and a personality — from careful planners to snack grabbers.', icon: 'bag' as const },
  { n: '02', title: 'Let them shop.', body: 'A language model makes every move, one decision at a time. Python validates and records each one.', icon: 'route' as const },
  { n: '03', title: 'Flag the extras.', body: 'Anything that wasn’t on the list is flagged as an impulse buy — with the shelf, the price and the reason given.', icon: 'spark' as const },
];

export default function Landing() {
  return <main className="marketing-page">
    <SiteNav/>
    <section className="hero" id="main-content">
      <div className="hero-copy">
        <p className="hero-pill"><span/>Impulse-buy detection</p>
        <h1>Spot the impulse buy.</h1>
        <p className="hero-lede">Simply walks AI shoppers through a store with a list and a budget, then shows you exactly which items they <em>didn’t</em> plan to buy — where they grabbed it, what it cost, and the reason they gave.</p>
        <div className="hero-actions">
          <Link href="/lab" className="marketing-primary">Open the lab <Icon name="arrow" size={17}/></Link>
          <Link href="/evaluation" className="marketing-secondary">See the evidence</Link>
        </div>
        <ul className="hero-legend" aria-label="How purchases are tagged">
          <li><i className="dot-planned"/>On the list</li>
          <li><i className="dot-impulse"/>Impulse buy</li>
        </ul>
      </div>
      <ImpulseReceipt/>
    </section>

    <section className="steps" aria-labelledby="how-heading">
      <h2 id="how-heading" className="sr-only">How Simply works</h2>
      {steps.map(step => <article key={step.n}>
        <span className="step-icon"><Icon name={step.icon} size={18}/></span>
        <span className="step-n">{step.n}</span>
        <h3>{step.title}</h3>
        <p>{step.body}</p>
      </article>)}
    </section>

    <section className="watch" aria-labelledby="watch-heading">
      <header>
        <p className="marketing-eyebrow">A recorded trip</p>
        <h2 id="watch-heading">Watch the extras pile up.</h2>
        <p>Every amber shelf is where a shopper picked up something that wasn’t on their list. This is a saved run, replayed — nothing here is generated in your browser.</p>
      </header>
      <ImpulseReplayDemo/>
    </section>

    <section className="cta-band">
      <div>
        <h2>Which stores trigger more impulse buys?</h2>
        <p>Compare models and shelf layouts on the same ten shoppers.</p>
      </div>
      <Link href="/evaluation" className="marketing-primary">See the evidence <Icon name="arrow" size={17}/></Link>
    </section>

    <footer className="marketing-footer">
      <Link href="/" className="brand">simply<span className="brand-dot">.</span></Link>
      <p><Icon name="info" size={13}/> Simulated shoppers help explore hypotheses. They don’t predict real customer behavior.</p>
      <Link href="/lab">Shopper lab <Icon name="arrow" size={14}/></Link>
    </footer>
  </main>;
}
