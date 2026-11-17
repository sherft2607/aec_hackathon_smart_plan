// The whole pitch, scene after scene. Each scene fades at its own edges, so a plain series reads as soft cuts.
import { Series } from "remotion";

import { Data } from "./scenes/Data";
import { Demo, DEMO_FRAMES } from "./scenes/Demo";
import { Flow } from "./scenes/Flow";
import { HowItWorks } from "./scenes/HowItWorks";
import { Impact } from "./scenes/Impact";
import { Intro } from "./scenes/Intro";
import { Limits } from "./scenes/Limits";
import { Outro } from "./scenes/Outro";
import { Problem, PROBLEM_FRAMES } from "./scenes/Problem";
import { Cta } from "./scenes/Cta";
import { Process } from "./scenes/Process";
import { Solution } from "./scenes/Solution";
import { Stack } from "./scenes/Stack";
import { Team } from "./scenes/Team";
import { Users } from "./scenes/Users";

type Scene = { name: string; frames: number; render: (duration: number) => React.ReactNode };

export const SCENES: Scene[] = [
  { name: "Intro", frames: 240, render: (d) => <Intro duration={d} /> },
  { name: "Team", frames: 380, render: (d) => <Team duration={d} /> },
  { name: "Problem", frames: PROBLEM_FRAMES, render: (d) => <Problem duration={d} /> },
  { name: "Users", frames: 240, render: (d) => <Users duration={d} /> },
  { name: "Solution", frames: 270, render: (d) => <Solution duration={d} /> },
  { name: "Demo", frames: DEMO_FRAMES, render: () => <Demo /> },
  { name: "Flow", frames: 390, render: (d) => <Flow duration={d} /> },
  { name: "HowItWorks", frames: 700, render: (d) => <HowItWorks duration={d} /> },
  { name: "Data", frames: 280, render: (d) => <Data duration={d} /> },
  { name: "Stack", frames: 285, render: (d) => <Stack duration={d} /> },
  { name: "Impact", frames: 265, render: (d) => <Impact duration={d} /> },
  { name: "Limits", frames: 320, render: (d) => <Limits duration={d} /> },
  { name: "Process", frames: 590, render: (d) => <Process duration={d} /> },
  { name: "Outro", frames: 240, render: (d) => <Outro duration={d} /> },
  { name: "Cta", frames: 210, render: (d) => <Cta duration={d} /> },
];

export const PITCH_FRAMES = SCENES.reduce((n, s) => n + s.frames, 0);

export function Pitch() {
  return (
    <Series>
      {SCENES.map((s) => (
        <Series.Sequence key={s.name} durationInFrames={s.frames} name={s.name} premountFor={30}>
          {s.render(s.frames)}
        </Series.Sequence>
      ))}
    </Series>
  );
}
