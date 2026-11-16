import type {Metadata} from 'next';
import Link from 'next/link';
import SiteNav from '../../site/SiteNav';
import {Icon} from '../../ui/Icons';
import ExperimentReport from '../../ui/ExperimentReport';
import RunHistory from '../../ui/RunHistory';
import MatrixResults from '../../ui/MatrixResults';
import EvidenceDashboard from '../../ui/EvidenceDashboard';

export const metadata:Metadata={title:'Evidence · Simply',description:'Which models and store layouts lead simulated shoppers to impulse buys, alongside completion, list fulfillment and cost.'};

export default function Page(){
  return <main className="evaluation-page"><SiteNav active="evaluation"/><div className="evaluation-content" id="main-content">
    <header className="evaluation-header"><div><p className="eyebrow">Evidence</p><h1>Who buys on impulse, and where?</h1></div><p>The same ten shoppers, lists and budgets in two store layouts, shopped by different models. Compare impulse buys alongside checkout completion, list fulfillment and cost.</p></header>
    <EvidenceDashboard/>
    <details className="evidence-studies"><summary>Study archive · paired comparisons, individual runs and original reports</summary>
      <MatrixResults/>
      <RunHistory/>
      <ExperimentReport/>
    </details>
    <footer className="evidence-method"><p>A fair layout comparison keeps the shoppers, products, prices, model and navigation policy fixed and changes only shelf placement. Repeated runs are needed to measure variation; most cells here are a single run.</p><p>Inspired by <a href="https://github.com/ved-2004/Gary-2">Gary-2</a>. Python owns the simulation and its metrics; this page displays the saved results.</p><Link className="text-link" href="/lab">Open shopper lab <Icon name="arrow" size={14}/></Link></footer>
  </div></main>;
}
