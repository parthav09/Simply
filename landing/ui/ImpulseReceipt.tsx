'use client';

import Link from 'next/link';
import {useEffect, useState} from 'react';
import type {CatalogEntry, ReplayData} from '../lib/replay';
import {loadShowcaseRecording, showcase} from '../lib/recordings';
import {impulseBuys, isPlanned, money, offListUnits, productOf} from '../lib/impulse';
import {productEmoji} from './map-theme';
import {Icon} from './Icons';

const cents = (v: number | null | undefined) => v == null ? '—' : `$${(v / 100).toFixed(2)}`;
const modelName = (id: string) => ({'gpt-6-luna': 'GPT-6 Luna', 'gpt-6.1-terra': 'GPT-6.1 Terra'} as Record<string, string>)[id] ?? id;
const layoutName = (id: string) => id === 'costco_back_anchor' ? 'Layout A' : 'Layout B';

/** A receipt rebuilt from one recorded trip: every paid item, tagged planned or impulse. */
export default function ImpulseReceipt() {
  const [state, setState] = useState<{run: ReplayData; entry: CatalogEntry} | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    loadShowcaseRecording().then(value => {if (active) setState(value);}).catch(cause => {if (active) setError(cause.message);});
    return () => {active = false;};
  }, []);
  if (!state) return <div className="receipt receipt-empty" role={error ? 'alert' : 'status'}><Icon name="bag" size={26}/><p>{error ? `${error} No receipt is shown without its recording.` : 'Printing a recorded receipt…'}</p>{!error && <div className="receipt-skeleton" aria-hidden="true"><i/><i/><i/><i/></div>}</div>;
  const {run} = state;
  const shopper = run.shoppers.find(s => s.id === showcase.shopper_id)!;
  const final = run.final.states[shopper.id];
  const metric = run.summary.shoppers.find(s => s.agent_id === shopper.id)!;
  const impulses = impulseBuys(run, run.events.length, shopper.id);
  const tendency = typeof shopper.persona.impulse_buy_probability === 'number' ? Math.round(shopper.persona.impulse_buy_probability * 100) : null;
  const items = [...final.cart].sort((a, b) => Number(isPlanned(run, shopper.id, b.product_id)) - Number(isPlanned(run, shopper.id, a.product_id)));
  const offList = offListUnits(run.summary, shopper.id);
  return <figure className="receipt" aria-label={`Recorded receipt for ${shopper.name}`}>
    <header className="receipt-head">
      <span className="receipt-kicker">Recorded receipt · {layoutName(run.layout.id)} · {modelName(run.source.model)}</span>
      <div className="receipt-who">
        <span className="avatar"><span className="shopper-sprite" style={{backgroundPosition: `0px -${shopper.sprite_index * 4 * 40}px`}}/></span>
        <div><strong>{shopper.name}</strong><small>{shopper.style}{tendency != null && ` · ${tendency}% impulse tendency`}</small></div>
      </div>
    </header>
    <ul className="receipt-items">
      {items.map(item => {
        const planned = isPlanned(run, shopper.id, item.product_id);
        const product = productOf(run, item.product_id);
        const why = impulses.find(i => i.productId === item.product_id);
        return <li key={item.product_id} className={planned ? 'is-planned' : 'is-impulse'}>
          <div className="receipt-line">
            <span className="item-emoji" aria-hidden="true">{productEmoji(product ?? item.name)}</span>
            <span className="receipt-name">{item.name}</span>
            <span className={`tag ${planned ? 'tag-planned' : 'tag-impulse'}`}>{planned ? 'On list' : 'Impulse'}</span>
            <span className="receipt-price">{money(product?.price)}</span>
          </div>
          {why && <blockquote>“{why.reason}”<cite>{product?.department ?? 'Shelf'} · decision #{why.event.sequence}</cite></blockquote>}
        </li>;
      })}
    </ul>
    <footer className="receipt-foot">
      <div><span>Paid at checkout</span><strong>{cents(final.basket_cents)}</strong></div>
      <div><span>Budget</span><strong>{cents(shopper.budget_cents)}</strong></div>
      <div className="is-impulse"><span>Impulse items</span><strong>{offList ?? '—'}</strong></div>
    </footer>
    <Link className="receipt-link" href={`/replays?run=${run.source.run_id}&shopper=${shopper.id}`}>Replay this trip <Icon name="arrow" size={14}/></Link>
    <figcaption className="sr-only">{metric.fulfilled_units} of {metric.requested_units} list items bought. Run {run.source.run_id.slice(0, 8)}.</figcaption>
  </figure>;
}
