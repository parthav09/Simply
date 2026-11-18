'use client';

import {useEffect,useState} from 'react';
import {loadCatalog} from '../lib/recordings';
import {decodeDashboard,type Dashboard} from '../lib/dashboard';

/** Loads the same integrity-checked Python dashboard the results table uses. Display only. */
export function useDashboardData(){
  const [data,setData]=useState<Dashboard|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let active=true;
    loadCatalog().then(async catalog=>{
      if(!catalog.dashboard)throw new Error('No comparison dashboard has been exported');
      const response=await fetch(catalog.dashboard.url,{cache:'no-store'});
      if(!response.ok)throw new Error('The comparison dashboard is unavailable');
      const decoded=await decodeDashboard(await response.text(),catalog.dashboard);
      if(active)setData(decoded);
    }).catch(cause=>{if(active)setError(cause instanceof Error?cause.message:'Unable to load results');});
    return()=>{active=false;};
  },[]);
  return {data,error};
}
