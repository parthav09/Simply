import report from '../data/run-checks.json';

/**
 * Pass / review / fail results written by Python (simulation/evaluation/guardrails.py) from the saved
 * recordings behind the results table. This component only lays out that report.
 */
type Finding={check:string;severity:string;detail:string};
type Flagged={shopper_id:string;name:string;verdict:string;findings:Finding[]};
type Row={model_id:string;model_label:string;layout_id:string;layout_label:string;run_id:string;verdict:string;
  shoppers_total:number;shoppers_pass:number;shoppers_review:number;shoppers_fail:number;
  checks:{check:string;severity:string;shoppers:string[]}[];flagged:Flagged[]};
type Rule={check:string;severity:string;label:string;description:string};
const rows=report.runs as unknown as Row[];
const rules=report.rules as unknown as Rule[];
const label=(check:string)=>rules.find(r=>r.check===check)?.label??check;
const VERDICT:Record<string,string>={pass:'Pass',review:'Review',fail:'Fail'};

export default function RunChecks(){
  return <section className="results-extra" aria-labelledby="run-checks-title">
    <h2 id="run-checks-title">Run checks</h2>
    <p className="evidence-footnote">Automatic pass, review and fail checks on every recording behind the results table. Python reads the saved runs and flags anything unusual, so a run is not judged by eye. It covers exactly the {rows.length} recordings behind the results table above, and no others.</p>
    <ul className="run-check-key" aria-label="What the results mean">
      <li><span className="run-badge is-fail">Fail</span> A hard rule is broken, such as a shopper who never checked out or an allergen in an unplanned purchase.</li>
      <li><span className="run-badge is-review">Review</span> Something unusual worth a look, such as more unplanned items than the impulse tier allows. Not proof of a fault.</li>
      <li><span className="run-badge is-pass">Pass</span> Nothing flagged. It does not prove the behaviour is realistic.</li>
    </ul>
    <div className="report-table"><table aria-label="Guardrail results for each recorded run"><thead><tr><th scope="col">Model</th><th scope="col">Layout</th><th scope="col">Run result</th><th scope="col">Shoppers (pass / review / fail)</th><th scope="col">Most common flags</th></tr></thead>
      <tbody>{rows.map(row=><tr key={row.run_id}>
        <th scope="row">{row.model_label}</th>
        <td>{row.layout_id==='costco_back_anchor'?'A':'B'}<small>run {row.run_id.slice(0,8)}</small></td>
        <td><span className={`run-badge is-${row.verdict}`}>{VERDICT[row.verdict]}</span></td>
        <td>{row.shoppers_pass} / {row.shoppers_review} / {row.shoppers_fail}<small>of {row.shoppers_total}</small></td>
        <td>{row.checks.length===0?'None':row.checks.slice(0,3).map(c=><span className="run-flag" key={c.check}>{label(c.check)}<small>{c.shoppers.length} {c.shoppers.length===1?'shopper':'shoppers'}</small></span>)}</td>
      </tr>)}</tbody></table></div>
    <p className="evidence-footnote">The impulse limits come from our own tier rule (more impulsive shoppers may add more unplanned items). It was written for the fine-tuning data. We have not confirmed that the prompt tells the model about it, so an impulse flag is a prompt for review, not a verdict on the model.</p>
    <details className="evidence-details"><summary>Flagged shoppers, run by run</summary>
      {rows.filter(r=>r.flagged.length>0).map(row=><div key={row.run_id} className="run-flagged">
        <strong>{row.model_label} · Layout {row.layout_id==='costco_back_anchor'?'A':'B'}</strong>
        <ul>{row.flagged.map(s=><li key={s.shopper_id}><span className={`run-badge is-${s.verdict}`}>{VERDICT[s.verdict]}</span> <strong>{s.name}</strong>: {s.findings.map(f=>`${label(f.check)} (${f.detail})`).join('; ')}</li>)}</ul>
      </div>)}
    </details>
    <details className="evidence-details"><summary>All rules and thresholds</summary>
      <ul>{rules.map(rule=><li key={rule.check}><span className={`run-badge is-${rule.severity}`}>{VERDICT[rule.severity]}</span> <strong>{rule.label}.</strong> {rule.description}</li>)}</ul>
      <p>Source: simulation/evaluation/guardrails.py. Thresholds are constants in that file and can be changed in one place.</p>
    </details>
  </section>;
}
