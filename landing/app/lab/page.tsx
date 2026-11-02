import type { Metadata } from 'next';
import SiteNav from '../../site/SiteNav';
import LiveWorkspace from '../../ui/LiveWorkspace';
export const metadata: Metadata = { title: 'Shopper lab · Simply', description: 'Watch Python shoppers live or replay their saved decisions.' };
export default function Page(){return <main className="lab-page lab-application"><SiteNav active="lab"/><div className="lab-content" id="main-content"><LiveWorkspace/></div></main>;}
