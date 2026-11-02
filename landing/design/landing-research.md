# Simply landing page — reference study

Reviewed 26 October 2026, before implementation. This is a design sample of 20 prominent B2B AI products and AI-enabled SaaS applications, not a revenue or market-share ranking. Official pages were read and their browser presentations inspected. Animation-heavy sites were also assessed from their page structure. Dribbble concepts are visual references, not verified products or evidence of conversion performance.

## Twenty product references

| Reference | Observed approach | Useful lesson for Simply |
| --- | --- | --- |
| [Codex](https://openai.com/codex/) | Broad lavender atmosphere, one concise proposition, restrained navigation and actions. | A coherent environment matters more than coloring individual cards. |
| [Claude Enterprise](https://claude.com/solutions/enterprise) | Editorial typography, substantial text scale, clear enterprise paths and customer material. | Give the message a confident hierarchy; make supporting copy readable. |
| [Cursor](https://cursor.com/) | Modest introductory copy followed by a large, detailed working-product presentation. | The product can carry more of the story than the headline. |
| [Linear](https://linear.app/) | Exact interface details, clear section hierarchy, restrained palette, product workflows. | Treat the simulation and its details as the primary visual material. |
| [Notion AI](https://www.notion.com/product/ai) | Immediately recognizable illustration, direct role-based explanation, a compact proposition. | Distinctive imagery should relate to what the product does. |
| [Glean](https://www.glean.com/) | Strong centered proposition, unusual textural product surround, enterprise proof. | Give the demonstration a designed setting. Do not borrow unsupported customer proof. |
| [Harvey](https://www.harvey.ai/) | Editorial left/right introduction, high-contrast type, substantial product image on a textured field. | Establish authority through proportion, contrast, and a large demonstration. |
| [Sierra](https://sierra.ai/) | Cinematic human imagery, restrained green identity, outcomes-led section structure. | Connect the product to human behavior; avoid ornamental complexity. |
| [Hebbia](https://www.hebbia.com/) | Architectural cinematic environment, compact navigation, finance-specific positioning. | The subject's world can establish the visual language. Simply's world is a store. |
| [Decagon](https://decagon.ai/) | Large direct typography, spacious composition, one dominant conversion action. | Use a strong focal point and a clear next step. |
| [Clay](https://www.clay.com/) | Custom dimensional world, distinctive materials and color, asymmetric headline and explanation. | Build an ownable spatial scene connected to the product rather than a generic app card. |
| [Gong](https://www.gong.io/) | Condensed bold type, purple identity, active benefit statement, sales-specific narrative. | Typography can carry personality, but it needs a consistent system. |
| [Fin](https://fin.ai/) | Sculptural imagery with a large conversational interface integrated into the composition. | Combine visual identity and an actual product interaction in the same focal area. |
| [Jasper](https://www.jasper.ai/) | Navy editorial display type, sharp orange actions, composed product/content material. | Use a disciplined contrast between display type, body copy, and actions. |
| [WRITER](https://writer.com/) | Large cinematic brand environment and a singular offer, followed by customer/workflow material. | Establish one intentional art direction instead of many unrelated effects. |
| [Typeface](https://www.typeface.ai/) | Clear enterprise-specific introduction, red actions, visual product narrative. | State audience and job clearly; maintain a recognizable accent. |
| [Synthesia](https://www.synthesia.io/) | Clear product category, business audience, product-mode tabs and demonstration area. | Let visitors explore the product's distinct modes through meaningful controls. |
| [ElevenLabs](https://elevenlabs.io/) | Asymmetric typography, material-rich product imagery, navigable product families and usable samples. | Give the user something concrete to inspect and try. |
| [Replit](https://replit.com/) | A functional product entry point directly in the hero; examples explain usage. | Put the first useful interaction above the fold. |
| [Devin](https://devin.ai/) | Straightforward introductory text and a large layered interface walkthrough. | The strongest evidence is a legible product workflow. |

## Dribbble references

- [Hatypo Studio — Warehouse Monitoring Dashboard](https://dribbble.com/shots/27640072-Warehouse-Monitoring-Dashboard): isometric blueprint visualization with contextual information. Most directly relevant to Simply's spatial product. Borrow the diagram-to-information relationship, not its UI or artwork.
- [LAIN — Floware warehouse SaaS landing page](https://dribbble.com/shots/27246128-Floware-Warehouse-SaaS-Platform-Dashboard-Website-Landing-Page): detailed spatial hero, sparse surrounding typography, light technical palette. Borrow the way a complex product becomes tangible at first sight.
- [Hatypo Studio — Warehouse Automation Landing Page](https://dribbble.com/shots/27633677-Warehouse-Automation-Landing-Page): technical illustration and editorial composition. Useful as a direction for retail/architecture rather than generic chatbot branding.
- [Orix Creative — responsive B2B landing page](https://dribbble.com/shots/27328378-SaaS-Web-Design-Responsive-B2B-Landing-Page-All-Breakpoints): documented reflow and action-color discipline. Borrow the responsive hierarchy, not claims about performance.
- [Riazul Islam — Next-Gen B2B SaaS](https://dribbble.com/shots/26538276-Next-Gen-B2B-SaaS-Website-Landing-Page): strong depth and lighting, but the floating device and generic product promises are a poor fit for Simply. Rejected as a primary direction.
- [Pixel Lab — AI Startup Landing Page](https://dribbble.com/shots/27032736-AI-Startup-Landing-Page-Clean-SaaS-UI-Design): calm palette and hierarchy described by its author. Its general-purpose nature/AI visual treatment is less relevant than the spatial references.

## Diagnosis of the current Simply page

The current page is a standard centered headline, italic accent, two buttons, and a small dashboard. Its visual identity comes from common marketing conventions instead of its subject. The simulation is harder to see than the headline. Supporting sections repeat the same density and shape. Pale small text weakens the product's authority.

## Direction chosen after the research

**A working store, presented like a spatial design study.**

1. Create an original isometric store scene from the existing floorplan data. Give it enough scale to be the hero's visual anchor. Animate actual simulated shoppers and routes, not unrelated decoration.
2. Keep the page light with white, cool gray, cobalt blue, and indigo. Use depth in the store fixtures and precise lines; avoid a page-wide pastel wash.
3. Pair a characterful grotesk display face with the existing readable sans-serif for body and product text. No alternating italic slogan treatment.
4. Present a clear retail-simulation proposition, a useful layout switch, and actual run metrics in the first experience.
5. Use varied section compositions: spatial hero, a narrow dataset strip, an inspectable comparison, a shopper/decision story, and a concise workflow.
6. Show sample-data and browser-engine limitations plainly. Derive numbers from the engine. Do not invent customer logos, testimonials, certifications, forecasts, or revenue lifts.
7. Verify desktop and phone compositions. On phones, stack copy and scene, simplify annotations, and keep layout controls usable.

The original code-native store illustration is not copied from Dribbble or any product. The retained simulation engine, lab route, benchmarks, and decision trace remain the functional basis of the page.

## Implemented and checked

- Original isometric SVG store view derived from the sample floorplans; shopper positions, route traces, basket counts, and revenue come from the browser simulation engine.
- Layout A/B switching and explicit run/pause controls. The simulation stops advancing while its scene is off screen or the document is hidden.
- Bricolage Grotesque display typography, readable sans-serif supporting text, light technical surfaces, and blue/indigo accents.
- Reworked comparison, profile, workflow, and closing sections. The full lab remains the primary action.
- Reviewed at desktop and 390-pixel phone widths. Verified layout switching, simulation advancement, pause, and the lab link.
- Production build, TypeScript, targeted ESLint, and the existing engine benchmark contract pass.
