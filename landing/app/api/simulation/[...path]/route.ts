/** Loopback transport proxy only. Python owns sessions, decisions and metrics. */
import type { NextRequest } from 'next/server';

type Context={params:Promise<{path:string[]}>};
async function forward(request:NextRequest,context:Context){
  const {path}=await context.params;
  const endpoint=path.join('/');
  if(!/^(health|preview|evidence|runs|runs\/[a-f0-9]{32}\/(events|control|export))$/.test(endpoint))return Response.json({error:'Unknown simulation endpoint'},{status:404});
  const origin=request.headers.get('origin');
  let matchingOrigin=!origin;
  if(origin){try{const parsed=new URL(origin);matchingOrigin=parsed.protocol===request.nextUrl.protocol&&parsed.host===request.headers.get('host');}catch{matchingOrigin=false;}}
  // Next's internal URL can use localhost while the browser uses 127.0.0.1.
  // Compare with the actual incoming Host, preserving the port boundary.
  if(request.method==='POST'&&(!matchingOrigin||(!origin&&request.headers.get('sec-fetch-site')==='cross-site')))return Response.json({error:'Same-origin request required'},{status:403});
  const base=new URL(process.env.SIMPLY_PYTHON_URL??'http://127.0.0.1:8765');
  if(base.protocol!=='http:'||!['127.0.0.1','localhost'].includes(base.hostname))return Response.json({error:'Python service must use a local address'},{status:503});
  let body:string|undefined;
  if(request.method==='POST'){
    body=await request.text();
    if(body.length>8192)return Response.json({error:'Run configuration is too large'},{status:413});
  }
  const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),5000);
  try{
    const upstream=await fetch(new URL('/'+endpoint+request.nextUrl.search,base),{method:request.method,body,
      headers:body?{'Content-Type':'application/json'}:undefined,cache:'no-store',
      signal:AbortSignal.any([request.signal,controller.signal])});
    clearTimeout(timer);
    return new Response(upstream.body,{status:upstream.status,headers:{
      'Content-Type':upstream.headers.get('content-type')??'application/json',
      'Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'}});
  }catch{return Response.json({error:'Python live service is unavailable. Start npm run simulation:serve in landing.'},{status:503});}
  finally{clearTimeout(timer);}
}
export const GET=forward;
export const POST=forward;
