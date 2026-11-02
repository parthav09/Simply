'use client';

import { memo, useEffect, useId, useMemo, useState } from 'react';
import { frameAt, shopperHistory, type ReplayData } from '../lib/replay';
import { Icon } from './Icons';
import {loadDemoRecording} from '../lib/recordings';
import {departmentColor, departmentSymbols, productEmoji, zoneSymbols} from './map-theme';
import {CELL_SIZE, shelfItemBlocks, shelfPlate} from '../lib/map-items';

const project = (x: number, y: number): [number, number] => [(x - y) * 20, (x + y) * 10];
const polygon = (corners: [number, number][], elevation = 0) => corners.map(([x, y]) => {
  const [px, py] = project(x, y);
  return `${px},${py - elevation}`;
}).join(' ');

const IsometricFixtures=memo(function IsometricFixtures({layout,id}:{layout:ReplayData['layout'];id:string}) {
  return <>        <defs><filter id={`${id}-shadow`} x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="15" stdDeviation="14" floodColor="var(--map-shadow)" floodOpacity=".12"/></filter><pattern id={`${id}-floor`} width="40" height="20" patternUnits="userSpaceOnUse"><path d="M0 10 20 0 40 10 20 20Z" fill="none" stroke="var(--map-grid)" strokeWidth=".55"/></pattern></defs>
        <g filter={`url(#${id}-shadow)`}>
          <polygon points={`${polygon([[0,layout.height],[layout.width,layout.height],[layout.width,0]])} ${polygon([[layout.width,0],[layout.width,layout.height],[0,layout.height]],-13)}`} fill="var(--map-fixture)"/>
          <polygon points={polygon([[0,0],[layout.width,0],[layout.width,layout.height],[0,layout.height]])} fill="var(--map-floor)" stroke="var(--map-fixture-edge)" strokeWidth="1.5"/>
          <polygon points={polygon([[0,0],[layout.width,0],[layout.width,layout.height],[0,layout.height]])} fill={`url(#${id}-floor)`}/>
          {layout.entrance.map(([x,y]) => <polygon key={`in-${x}-${y}`} points={polygon([[x,y],[x+1,y],[x+1,y+1],[x,y+1]])} fill="var(--map-entrance)" stroke="var(--map-entrance)" strokeWidth=".6"/>)}
          {layout.checkout.map(([x,y]) => <polygon key={`out-${x}-${y}`} points={polygon([[x,y],[x+1,y],[x+1,y+1],[x,y+1]])} fill="var(--map-checkout)" stroke="var(--map-checkout)" strokeWidth=".6"/>)}
          {layout.entrance[0] && <text x={project(layout.entrance[0][0]+.5, layout.entrance[0][1]+.5)[0]} y={project(layout.entrance[0][0]+.5, layout.entrance[0][1]+.5)[1]+3} textAnchor="middle" fontSize="8">{zoneSymbols.entrance}</text>}
          {layout.checkout[0] && <text x={project(layout.checkout[0][0]+.5, layout.checkout[0][1]+.5)[0]} y={project(layout.checkout[0][0]+.5, layout.checkout[0][1]+.5)[1]+3} textAnchor="middle" fontSize="8">{zoneSymbols.checkout}</text>}
          {layout.shelves.toSorted((a,b) => a.x+a.y-b.x-b.y).map((shelf, index) => {
            const color = departmentColor(shelf.department);
            const plate = shelfPlate(shelf);
            const blocks = shelfItemBlocks(shelf);
            if (!plate || !blocks.length) return null;
            const [labelX,labelY] = project(plate.centerX/CELL_SIZE, (plate.y+4)/CELL_SIZE + plate.height/CELL_SIZE/2);
            return <g key={index}>
              {blocks.map(block => {
                const x=block.x/CELL_SIZE,y=block.y/CELL_SIZE,w=block.width/CELL_SIZE,h=block.height/CELL_SIZE;
                const face=block.products[0];
                const [emojiX,emojiY]=project(x+w/2,y+h/2);
                return <g key={`${block.cellX},${block.cellY}`} data-product-id={face.id}>
                  <title>{face.name}{block.products.length>1?` · +${block.products.length-1} more`:''}</title>
                  <polygon points={`${polygon([[x,y+h],[x+w,y+h],[x+w,y]],5)} ${polygon([[x+w,y],[x+w,y+h],[x,y+h]])}`} fill="var(--map-fixture-edge)"/>
                  <polygon points={polygon([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],5)} fill={color} stroke="var(--map-fixture-top)" strokeWidth=".5"/>
                  <text x={emojiX} y={emojiY-3} textAnchor="middle" fontSize="9">{productEmoji(face)}</text>
                </g>;
              })}
              <text x={labelX} y={labelY+18} textAnchor="middle" fill="var(--map-label)" fontSize="8">{departmentSymbols[shelf.department]??'🛒'} {shelf.department}</text>
            </g>;
          })}
        </g></>;
});

export default function RecordedShowcase() {
  const [run, setRun] = useState<ReplayData | null>(null);
  const [error, setError] = useState('');
  const id = useId().replaceAll(':', '');

  useEffect(() => {
    let cancelled=false;
    const load=async()=>{
      const data=await loadDemoRecording('costco_back_anchor');
      if(!cancelled)setRun(data);
    };
    load().catch(error=>{if(!cancelled)setError(error.message);});
    return()=>{cancelled=true;};
  },[]);

  // A still from an existing run; the poster has no playback or interactive controls.
  const cursor = run ? Math.min(200, run.events.length) : 0;
  const frame = useMemo(() => run ? frameAt(run, cursor) : null, [run, cursor]);
  const event = run?.events[cursor - 1];
  const shopper = run?.shoppers.find(s => s.id === event?.agent_id) ?? run?.shoppers[0];
  const layoutLabel = run ? ({ costco_back_anchor: 'Layout A · Anchor loop', neighborhood_express: 'Layout B · Express essentials' }[run.layout.id] ?? run.layout.id) : '';
  return <figure className="store-showcase store-poster" aria-label="Still picture of a recorded store simulation">
    <div className="showcase-topline"><span><i /> THE SHOPPER’S PERSPECTIVE</span><span>RECORDED STILL</span></div>
    {run && frame && shopper ? <>
      <div className="showcase-caption"><span className="showcase-layout"><Icon name="map" size={14}/>{layoutLabel}</span><span>{run.shoppers.length} shoppers · one block, one item</span></div>
      <svg className="isometric-store" viewBox={`${-run.layout.height * 20 - 35} -65 ${(run.layout.width + run.layout.height) * 20 + 70} ${(run.layout.width + run.layout.height) * 10 + 125}`} role="img" aria-label={`Isometric ${layoutLabel}, showing saved shopper positions at event ${cursor} of ${run.events.length}`}>
        <IsometricFixtures layout={run.layout} id={id}/>
        {run.shoppers.map(s => {
          const state=frame.states[s.id];
          if (state.phase==='FinishedState') return null;
          const [x,y]=project(state.x+.5,state.y+.5);
          const selected=s.id===shopper.id;
          const last=shopperHistory(run,cursor,s.id).at(-1);
          const direction=({move_left:1,move_right:2,move_up:3} as Record<string,number>)[last?.action?.step??'']??0;
          return <g key={s.id} className="showcase-shopper" transform={`translate(${x},${y})`}>
            <ellipse cx="0" cy="2" rx="13" ry="6" fill={selected?'var(--color-accent)':'var(--color-text-muted)'} opacity=".25"/>
            {selected&&<ellipse cx="0" cy="2" rx="17" ry="8" fill="none" stroke="var(--color-accent)" strokeWidth="1"/>}
            <foreignObject x="-20" y="-35" width="40" height="40"><span className="shopper-sprite" style={{backgroundPosition:`0px -${(s.sprite_index*4+direction)*40}px`}}/></foreignObject>
            {selected&&<g aria-hidden="true"><rect x="-28" y="-51" width="56" height="15" rx="7" fill="var(--color-accent)"/><text x="0" y="-40.5" textAnchor="middle" fill="var(--color-on-accent)" fontSize="8">{s.name.split(' ')[0]}</text></g>}
          </g>;
        })}
      </svg>
      <figcaption className="showcase-source">A moment from Layout A · {run.source.model} · run {run.source.run_id.slice(0,8)}. Scroll down to replay both layouts from above.</figcaption>
    </> : <div className="showcase-empty" role={error?'alert':'status'}><Icon name="map" size={36}/><h2>{error?'The picture is unavailable.':'Opening the store…'}</h2><p>{error || 'Loading a still from the saved shopper journey.'}</p></div>}
  </figure>;
}
