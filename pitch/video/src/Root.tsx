import { Composition } from "remotion";

import { Pitch, PITCH_FRAMES, SCENES } from "./Pitch";
import { FPS, H, W } from "./theme";

export function Root() {
  return (
    <>
      <Composition id="Pitch" component={Pitch} durationInFrames={PITCH_FRAMES} fps={FPS} width={W} height={H} />
      {SCENES.map((s) => (
        <Composition key={s.name} id={`Scene-${s.name}`} component={() => <>{s.render(s.frames)}</>} durationInFrames={s.frames} fps={FPS} width={W} height={H} />
      ))}
    </>
  );
}
