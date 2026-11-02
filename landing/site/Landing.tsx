import Link from 'next/link';
import RecordedShowcase from '../ui/RecordedShowcase';
import LandingReplayDemos from '../ui/LandingReplayDemos';
import SiteNav from './SiteNav';
import { Icon } from '../ui/Icons';

export default function Landing() {
  return <main className="marketing-page">
    <SiteNav labDisabled/>
    <section className="marketing-hero" id="main-content">
      <div className="marketing-intro"><p className="marketing-eyebrow"><span/> Retail simulation, with evidence.</p><h1>Understand the<br/><em>shopper’s choices.</em></h1><p className="marketing-description">Explore how AI shoppers navigate a store, choose products, and work through their lists. Replay every decision and inspect the evidence behind the results.</p><div className="marketing-actions"><button className="marketing-primary" disabled>Shopper lab <Icon name="arrow" size={18}/></button><a href="#how-it-works" className="marketing-secondary">How Simply works <span>↘</span></a></div><div className="marketing-footnote"><span className="tiny-shoppers" aria-hidden="true"><i/><i/><i/></span><p>Different people. Different priorities.<br/><strong>Every choice on record.</strong></p></div></div>
      <RecordedShowcase/>
    </section>
    <div className="marketing-principles"><span>BUILT TO EXPLORE</span><p><Icon name="users" size={17}/> Individual shoppers</p><p><Icon name="map" size={17}/> Two store layouts</p><p><Icon name="route" size={17}/> Recorded journeys</p><p><Icon name="chart" size={17}/> Inspectable outcomes</p></div>
    <section className="marketing-replay" id="recorded-simulation" aria-label="Replay completed store simulations">
      <LandingReplayDemos/>
    </section>
    <section className="marketing-story" id="how-it-works"><div className="marketing-story-title"><p className="marketing-eyebrow">01 / THE IDEA</p><h2>One experiment.<br/><em>Every choice in view.</em></h2><p>A list gets forgotten. A budget gets stretched. An aisle gets another look. Simply lets you investigate the small decisions that make a shopping trip.</p><Link href="/evaluation" className="marketing-text-link">Meet the method <Icon name="arrow" size={17}/></Link></div><div className="marketing-steps"><article><span>01</span><div><h3>Set the scene.</h3><p>Two layouts. The same group of 10–15 shoppers, with individual lists, budgets, and supplied preferences.</p></div><Icon name="map" size={21}/></article><article><span>02</span><div><h3>Watch choices unfold.</h3><p>The model proposes each choice. The simulation records what happened, including detours, missed items, and incomplete trips.</p></div><Icon name="route" size={21}/></article><article><span>03</span><div><h3>Follow your curiosity.</h3><p>Open the lab to inspect a shopper, follow a recorded path, or read the decision behind a moment.</p></div><Icon name="spark" size={21}/></article></div></section>
    <section className="marketing-questions"><div className="marketing-questions-heading"><p className="marketing-eyebrow">02 / A BETTER QUESTION</p><h2>Look a little closer.</h2><p>The most useful answer often starts with a better question.</p></div><div className="marketing-question-grid"><article><Icon name="bag" size={25}/><span>THE BASKET</span><h3>What made the cut?</h3><p>Find the list items, the off-list choices, and what was still missing at checkout.</p></article><article><Icon name="route" size={25}/><span>THE JOURNEY</span><h3>Why this way?</h3><p>Follow a shopper through the store and inspect the choices along their path.</p></article><article><Icon name="chart" size={25}/><span>THE EVIDENCE</span><h3>What can we learn?</h3><p>Connect recorded choices to saved outcomes, with the limits of each experiment in view.</p></article></div><p className="marketing-limits"><Icon name="info" size={15}/> Simulated choices help explore hypotheses. They do not establish real customer behavior or retail impact.</p></section>
    <section className="marketing-closing"><span aria-hidden="true">↗</span><div><p className="marketing-eyebrow">THERE’S A STORY IN EVERY AISLE</p><h2>Let’s see where it goes.</h2></div><button className="marketing-primary" disabled>Shopper lab <Icon name="arrow" size={18}/></button></section>
    <footer className="marketing-footer"><Link href="/" className="brand">simply.</Link><p>Small decisions. A different perspective.</p><Link href="/evaluation">Method & evidence <Icon name="arrow" size={14}/></Link></footer>
  </main>;
}
