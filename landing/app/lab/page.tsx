import type { Metadata } from 'next';
import SiteNav from '../../site/SiteNav';
import LiveWorkspace from '../../ui/LiveWorkspace';
export const metadata: Metadata = { title: 'Live run · Simply', description: 'Run a model-driven shopping trip and watch it live.' };
export default function Page(){return <main className="lab-page lab-application"><SiteNav active="lab"/><div className="lab-content" id="main-content"><LiveWorkspace/></div></main>;}
