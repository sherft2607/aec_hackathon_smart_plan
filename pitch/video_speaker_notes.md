# 4site pitch video: speaker notes (v2)

The video ([`4site_pitch_v2.mp4`](4site_pitch_v2.mp4), 5:00, silent, no captions) plays while we talk. Each
line fits its beat at a calm pace (about 2.5 words a second). Start each line when its timecode comes up; if
you fall behind, drop the last sentence rather than rushing. v1 is [`4site_pitch.mp4`](4site_pitch.mp4); the
team's direction for v2 is in [video_direction.md](video_direction.md).

**Words to use:** similar projects, patterns compared with similar sites, signals, a prompt to look.
**Never say:** predicts, will fail, safe, would have prevented. On the Brooklyn collapse: what happened, and
that the cause is under investigation. Nothing about what could have prevented it, and no blame.

---

## 0:00 Intro (8 s)
> We're 4site. Build on hindsight, design with foresight.

## 0:08 Team (13 s)
> We're eight people across five disciplines: architects, a structural engineer, computational designers, a
> developer, and software and AI engineers. This problem sits between our disciplines.

## 0:21 Problem (44 s)
**0:21 Brooklyn.**
> On November 11, a building on Flatbush Avenue in Brooklyn collapsed next to an excavation. People lost
> their lives. The cause is under investigation. What was publicly reported: the site next door had open
> excavation permits, and had been cited for working after a stop-work order.

**0:32 The wrong building.**
> That's the pattern: the warnings are public, but they sit on the construction site's record, not on the
> old building next door that they affect, and no one links the two.

**0:41 One slice each.**
> The architect, the engineer, the geotech, the contractor, DOB, the neighbors: everyone holds one slice
> and works in their own silo. What's missing is one live checklist the whole team shares.

**0:48 The scale.**
> And it repeats: more than sixteen thousand structural complaints since 2024, nearly fifteen hundred
> incidents, and 1,187 active excavations next to old attached buildings right now.

**0:56 The cost today.**
> Pulling this together for one site today takes several thousand dollars and one to three weeks. 4site
> does it in minutes, before you sign or file.

## 1:05 Who it's for (8 s)
> It's for architects and structural engineers first, and developers and contractors too.

## 1:13 Solution (9 s)
> 4site is one risk-intelligence map for every site in New York.

## 1:22 Product demo (100 s)
*The real app, recorded and sped up. Each step has its own title card.*

**1:22** *(title card)*
> Here's the product, on an active site in Brooklyn: 861 Park Avenue.

**1:25 Step 1, pick a site.**
> The whole city in 3D. We search for the address, and the map flies to it with its touching lots.

**1:33 Step 2, similar projects.**
> Right away: past projects like this one, closest first. "Watch out for" sums up what went wrong on most of
> them, a neighbor damaged next to an excavation, with the checklist items that address it.

**1:44** *(the case and its popup)*
> 211 East 34th Street: a strong match. It partly collapsed next to an excavation in 2020, with no injuries.
> The popup shows what it has in common with this site, its lessons, and what happened, as publicly reported.

**1:56 Step 3, this lot.**
> This lot's own record: the top signals, and early warnings, like work continuing after a stop-work order.

**2:08 Step 4, start a project.**
> Pick what you'd do here, a new build with excavation, and start a project. Setup already knows the lot:
> nine attached neighbors, what's filed with DOB. It only asks what the records can't tell us, like how
> deep you'll dig.

**2:27 Step 5, one checklist.**
> 4site drafts one live checklist for the whole team, along the project's milestones: design, DOB filing,
> neighbors notified, survey, excavation. Every item has an owner, the code section, and the proof it
> needs. Some come from DOB NOW: similar filings held at objections, so check those drawings before you file.

**2:45 Step 6, ask the chat.**
> And anyone can ask. A first answer arrives in seconds from this site's data, with the code sections, while
> the full answer searches the records and past cases.

## 3:02 Inputs, process, outputs (13 s)
> An address, the project and public records go in. We build a site profile, then run similarity,
> early-warning rules and Claude, where every answer cites its source record. Out come similar projects, warnings, a checklist and answers.

## 3:15 How it works (23 s)
**3:15 Similarity.**
> Similarity is a weighted sum of facts an engineer can check. Against 211 East 34th: masonry wall,
> attached, excavation, geotech records. That's 52 of 100, a strong match. A fact nobody reported never
> counts as a difference, and a near miss earns half.

**3:28 The checklist.**
> The checklist turns all of it into work: 21 items from four sources, code duties, hazard rules, lessons
> from similar projects, and DOB objections, each with an owner and the proof it needs. It's live: when
> anyone uploads a structural plan or a geotech report, the checklist updates.

## 3:38 Data sources (9 s)
> It's all public and all dated: DOB filings, complaints and violations, façades, flood, soil, weather, a
> case library, and the building code.

## 3:48 Tech stack (9.5 s)
> React, MapLibre and deck.gl on Vercel, Claude for the chat, Python and FastAPI underneath, and Cityweft
> for the 3D city.

## 3:57 Impact (9 s)
> The neighbor's risk shows up on your site, hindsight becomes a checklist, and the whole team works from
> one picture.

## 4:06 Limits and next steps (10.5 s)
> Public records only, not engineering advice, never a prediction. Next: the reasons behind DOB objections,
> a forensics ledger, daily alerts, and more cities.

## 4:17 How we built it (19 s)
**4:17 The process.**
> For our process we also took on Alex's meta hackathon provocation and the challenge of how to collaborate on a hackathon in this new era of agents. We recorded our brainstorms with Wispr Flow, synthesized them with Cursor and Claude, iterated on the
> plan, made concept videos, and took feedback, including from a Thornton Tomasetti forensic expert.

**4:31 The build.**
> BUILD.md was our single source of truth. Each of us ran an agent session from it, and the pull requests
> merged in order.

## 4:36 Close (8 s)
> 4site turns warnings into risk intelligence, before work starts. Build on hindsight, design with foresight.

## 4:44 Try it (7 s, held to the end for scanning)
*QR code.*
> Try it for yourself: scan the code, or find us on GitHub. Thank you.

---

### Facts behind the lines
- 1321 Flatbush Ave, Nov 11, 2026: as reported by the Associated Press (Nov 12). The cause is under
  investigation. The neighbouring site's permits and its April citation are from the same reports and DOB
  records.
- The cost and lead time are our team's estimate from practice, labelled that way on screen; there is no
  published figure.
- Counts are from NYC Open Data, pulled Nov 14, 2026: 16,581 structural complaints and 1,495 construction
  incidents since 2024. The 1,187 is the watchlist of active earth-work, foundation and SOE permits next to
  attached pre-1940 buildings.
- 211 E 34th St (2020): partial collapse of a vacant building next to an excavation; no injuries reported.
  Its score of 52 is 18 (wall system) + 10 (attached) + 20 (earth work) + 4 (record hazards), with the
  current weights in `site_profile/similarity.py`. Strong is 50 and up.
- The demo checklist has 21 items: Design 6, DOB filing 6, Neighbors notified 2, Survey done 1, Excavation 6.
  The objection items count DOB NOW filings still held at objections (e.g. 35 of 154 similar foundation
  filings); what the objections were about is not public.
