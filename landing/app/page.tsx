import type { Metadata } from "next";
import Landing from "../site/Landing";

export const metadata: Metadata = {
  title: "Simply · Spot the impulse buy",
  description:
    "Replay AI shoppers through a store and see which purchases were planned and which were impulse buys — where, what it cost, and why.",
};

export default function Page() {
  return <Landing />;
}
