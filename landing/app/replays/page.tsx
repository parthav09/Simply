import type {Metadata} from 'next';
import SiteNav from '../../site/SiteNav';
import ReplayGallery from '../../ui/ReplayGallery';

export const metadata: Metadata = {title: 'Replays · Simply', description: 'Replay each model shopping each store layout from recorded Python decisions.'};

export default function Page() {
  return <main className="lab-page lab-application replays-page"><SiteNav active="replays"/><div className="lab-content" id="main-content">
    <ReplayGallery/>
  </div></main>;
}
