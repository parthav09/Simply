import type {Metadata} from 'next';
import SiteNav from '../../site/SiteNav';
import EvidenceDashboard from '../../ui/EvidenceDashboard';
import OpenQuestions from '../../ui/OpenQuestions';
import CostQuality from '../../ui/CostQuality';
import RunChecks from '../../ui/RunChecks';
import ResultsQuestions from '../../ui/ResultsQuestions';

export const metadata:Metadata={title:'Results · Simply',description:'Which models and store layouts lead simulated shoppers to impulse buys, alongside completion, list fulfillment and cost.'};

export default function Page(){
  return <main className="evaluation-page"><SiteNav active="evaluation"/><div className="evaluation-content" id="main-content">
    <header className="page-head"><div><h1>Results</h1><p>The same ten shoppers in two store layouts, shopped by different models. Impulse buys are paid items that weren’t on the shopper’s list. These are the latest runs only.</p></div></header>
    <EvidenceDashboard/>
    <OpenQuestions/>
    <CostQuality/>
    <RunChecks/>
    <ResultsQuestions/>
  </div></main>;
}
