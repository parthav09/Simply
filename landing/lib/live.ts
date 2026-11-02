/** Validated Python display messages; no decisions or outcome calculations. */
import {validateReplay,type ReplayData,type ReplayEvent} from './replay';
export type LiveControl={controllable:boolean;status:string};
export type LiveSnapshot={stream_version:number;run:ReplayData;control:LiveControl};
export type LiveTransition={stream_version:number;source:ReplayData['source'];frame:ReplayData['final'];event:ReplayEvent|null;control:LiveControl};
export function liveSnapshot(message:LiveSnapshot,previous?:ReplayData|null):ReplayData{
  if(message.stream_version!==1)throw new Error('Unsupported live stream');
  const next=validateReplay(message.run);
  if(previous&&['provider','model','recorded_at','prompt_version'].some(field=>next.source[field as keyof typeof next.source]!==previous.source[field as keyof typeof previous.source]))throw new Error('Live provider or prompt identity changed during reconnect');
  if(previous&&(next.source.run_id!==previous.source.run_id||next.events.length<previous.events.length||
    JSON.stringify(next.events.slice(0,previous.events.length))!==JSON.stringify(previous.events)||
    JSON.stringify([next.layout,next.catalogue,next.shoppers,next.initial])!==JSON.stringify([previous.layout,previous.catalogue,previous.shoppers,previous.initial])))throw new Error('Confirmed live history changed during reconnect');
  return next;
}
export function liveTransition(current:ReplayData,message:LiveTransition):ReplayData{
  if(current.source.status!=='incomplete')throw new Error('Live run has already ended');
  if(message.stream_version!==1||message.source.run_id!==current.source.run_id)throw new Error('Live run identity changed');
  for(const field of ['provider','model','recorded_at','prompt_version'] as const)if(message.source[field]!==current.source[field])throw new Error('Live provider or prompt identity changed');
  if(message.event?.sequence!==undefined&&message.event.sequence!==current.events.length+1)throw new Error('Live event is missing or duplicated');
  if(message.event===null&&message.frame.sequence!==current.events.length)throw new Error('Invalid live completion');
  return validateReplay({...current,source:message.source,events:message.event?[...current.events,message.event]:current.events,
    summary:message.frame.summary,final:message.frame});
}
