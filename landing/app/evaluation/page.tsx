import type {Metadata} from 'next';
import Link from 'next/link';
import SiteNav from '../../site/SiteNav';
import {Icon} from '../../ui/Icons';
import ExperimentReport from '../../ui/ExperimentReport';
import RunHistory from '../../ui/RunHistory';
import MatrixResults from '../../ui/MatrixResults';
import EvidenceDashboard from '../../ui/EvidenceDashboard';

export const metadata:Metadata={title:'Results · Simply',description:'Compare recorded shopper completion, shopping outcomes, movement and API costs.'};

export default function Page(){
  return <main className="evaluation-page"><SiteNav active="evaluation"/><div className="evaluation-content" id="main-content">
    <header className="evaluation-header"><div><p className="eyebrow">Evidence</p><h1>Compare models.<br/>Compare layouts.</h1></div><p>The same shopping tasks, different models and shelf placements. Compare completion, purchased products, movement and API cost.</p></header>
    <EvidenceDashboard/>
    <details className="evidence-studies"><summary>Paired comparisons & original study reports</summary><MatrixResults/></details>
    <details className="evidence-studies"><summary>Individual runs & recordings</summary><RunHistory/></details>
    <details className="evidence-studies"><summary>Controlled layout & model studies</summary><ExperimentReport/></details>
    <footer className="evidence-method"><p>For a fair layout comparison, keep the shoppers, products, prices, model and navigation policy fixed. Change placement only. Use repeated runs to measure variation.</p><p>Inspired by <a href="https://github.com/ved-2004/Gary-2">Gary-2</a>. Python owns the simulation and its metrics; this page displays the saved results.</p><Link className="text-link" href="/lab">Open shopper lab <Icon name="arrow" size={14}/></Link></footer>
  </div></main>;
}
