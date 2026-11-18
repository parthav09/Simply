/**
 * Plain-language answers to the questions these results raise. Prose only: it computes nothing and
 * has no simulation state. Counts quoted here come from the recorded runs named in each source line.
 */
const items:{q:string;a:string[];source?:string}[]=[
  {q:'Is 12 unplanned items for one shopper expected?',
   a:['We can’t say it is. Isabella is an impulsive shopper with the largest budget and a stock-up trip, and the items GPT-6.1 Terra picked for her were cheap, family-appropriate and within budget. Per shopping stop, her impulse rate is close to the 45% we gave her.',
      'But the checks above flag it: 12 unplanned units is far past the limit our impulse tier allows for her. We have not yet confirmed whether the prompt states that limit, so this is either the model overshooting or the prompt and the rule being out of sync.'],
   source:'Source runs: or-v3-gpt-6.1-terra-20261117 and or-v3-gpt-6.1-terra-layout-a-replicate-20261118.'},
  {q:'Why don’t the other models do the same?',
   a:['Models weigh a profile differently, and that is what this evaluation measures. Terra took 12, 12 and then 11 unplanned items for her across three runs. GPT-6 Luna took none in every completed run. Both are stable, so it is a real difference between the models, not a fluke.',
      'It does not tell us which is right. Terra may be reading the fields that point toward buying, or Luna may be treating the list as the whole job. Luna is also less stable across other shoppers, so we do not quote its cohort totals as fixed.'],
   source:'Source runs: or-v3-gpt-6.1-terra-20261117, or-v3-gpt-6-luna-20261117 and their Layout A repeats.'},
  {q:'Can we say which model is right?',
   a:['No. The shoppers are synthetic, there are ten of them, and there is no real shopper to compare against. Her 45% impulse rate is a number we chose. So the results compare models with each other on identical shoppers. They do not predict how real customers behave.']},
  {q:'How do we know a run has not gone wrong?',
   a:['The run checks above. Python reads each saved recording and flags hard failures, such as a shopper who never checked out, and softer signs worth a look, such as extra impulse items, going over budget or looping. A pass is not proof the behaviour is realistic, and a review flag is not a verdict.']},
  {q:'What would settle the open questions?',
   a:['Change one profile field at a time, such as price sensitivity or whether the shopper uses a list, and repeat each run a few times per model. A model that acts on the field changes its behaviour when the field changes. One that acts on an assumption does not, or changes for the wrong field.']},
];

export default function ResultsQuestions(){
  return <section className="results-extra" aria-labelledby="results-questions-title">
    <h2 id="results-questions-title">Questions these results raise</h2>
    <p className="evidence-footnote">Honest answers, including what we do not know yet. Ten simulated shoppers, one or two runs each.</p>
    <div className="results-faq">{items.map(item=><article key={item.q}>
      <h3>{item.q}</h3>
      {item.a.map(text=><p key={text}>{text}</p>)}
      {item.source&&<p className="evidence-footnote">{item.source}</p>}
    </article>)}</div>
  </section>;
}
