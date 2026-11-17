import Link from 'next/link';
import ImpulseReceipt from '../ui/ImpulseReceipt';
import SiteNav from './SiteNav';
import { Icon } from '../ui/Icons';

const steps = [
  { title: 'Give shoppers a list', body: 'Ten simulated shoppers, each with a list, a budget and a personality.' },
  { title: 'Let a model shop', body: 'The model picks one move at a time. Python validates and records every move.' },
  { title: 'Flag the impulse buys', body: 'Anything picked up that wasn’t on the list is flagged, with the shelf, price and reason.' },
];

export default function Landing() {
  return <main className="marketing-page">
    <SiteNav/>
    <section className="hero" id="main-content">
      <div className="hero-copy">
        <h1>Spot the impulse buy.</h1>
        <p className="hero-lede">Simply sends AI shoppers through a store with a list and a budget, then shows which items they <em>didn’t</em> plan to buy: where, what it cost, and why.</p>
        <div className="hero-actions">
          <Link href="/replays" className="marketing-primary">Watch a replay <Icon name="arrow" size={17}/></Link>
          <Link href="/evaluation" className="marketing-secondary">See the results</Link>
        </div>
      </div>
      <ImpulseReceipt/>
    </section>

    <section className="steps" aria-label="How Simply works">
      {steps.map((step, i) => <article key={step.title}>
        <span className="step-n">{i + 1}</span>
        <h3>{step.title}</h3>
        <p>{step.body}</p>
      </article>)}
    </section>

    <footer className="marketing-footer">
      <Link href="/" className="brand">simply<span className="brand-dot">.</span></Link>
      <p>Simulated shoppers help explore hypotheses. They don’t predict real customer behavior.</p>
    </footer>
  </main>;
}
