import store from "../data/store_v2.json";
import Workspace from "../ui/Workspace";

export default function Page() { return <Workspace store={store} />; }
