/**
 * Presenter-facing notes under the results table. Prose only: it shows no computed metric
 * and has no simulation state. Numbers quoted here come from the recorded runs named below.
 */
export default function OpenQuestions(){
  return <section className="open-questions" aria-labelledby="open-questions-title">
    <h2 id="open-questions-title">Two things we are still learning</h2>
    <p className="evidence-footnote">Observations and open questions, not findings. Ten shoppers, one or two runs each.</p>
    <div className="open-questions-grid">
      <article>
        <h3>Do shoppers follow their profile, or the model’s assumptions?</h3>
        <p>Each shopper has a profile: budget, price sensitivity, whether they bring a list, how impulsive they are. We want to know whether the model acts on those fields or on a stereotype it builds from them, such as “a family on a budget”.</p>
        <p>Isabella Rossi shows the question. She is impulsive, has the largest budget in the group, and has a list of seven must-have items but is not set to stick to it. In the same two layouts, Terra picked up 12 off-list items for her. Luna picked up none. Terra’s items were cheap, sensible and within budget.</p>
        <ul>
          <li>Neither model is the baseline. We have no real shopper to compare to, and her 45% impulse rate is a number we chose.</li>
          <li>Per visit, Terra is close to what 45% predicts. She is not a statistical outlier.</li>
          <li>A repeat Terra run on Layout A did it again: 11 off-list items for her, against 12 before. The pattern is stable for Terra, not a fluke.</li>
          <li>Luna taking none for an impulsive shopper is also questionable. It may be treating the list as the whole job.</li>
          <li>We can’t say yet. Next step: change one profile field at a time and check that behaviour moves with it.</li>
        </ul>
        <p className="evidence-footnote">Source runs: or-v3-gpt-6.1-terra-20261117, or-v3-gpt-6-luna-20261117 and or-v3-gpt-6.1-terra-layout-a-replicate-20261118.</p>
      </article>
      <article>
        <h3>How far can a shopper see?</h3>
        <p>You can’t impulse-buy what you never notice, so what a shopper can see shapes the result. We have not settled that yet.</p>
        <p>The idea is a visibility radius: everything within a set number of blocks is visible, including products behind the aisles. A shopper at the bottom row of a shelf block would also see its top row. This is not line of sight, which would hide anything behind a shelf.</p>
        <ul>
          <li>The current plan is narrower: a product is visible only from a cell next to it.</li>
          <li>A tighter or wider view changes impulse counts for every model, so results are only comparable within one rule.</li>
          <li>The rule would be recorded in each run, so earlier runs stay valid under the one they used.</li>
          <li>A new rule shows the models different inputs, so the fine-tuned model may do worse until it is retrained.</li>
        </ul>
        <p className="evidence-footnote">Not built yet. Nothing on this page depends on it.</p>
      </article>
    </div>
  </section>;
}
