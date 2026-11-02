import type { Metadata } from "next";
import Landing from "../site/Landing";

export const metadata: Metadata = {
  title: "Simply · A new perspective on retail",
  description:
    "Explore recorded AI shopper journeys. Follow decisions, inspect baskets, and investigate store layouts with evidence behind every result.",
};

export default function Page() {
  return <Landing />;
}
