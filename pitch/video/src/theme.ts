// The pitch deck's look: warm paper with a faint grid, a bold grotesk, pixel-font labels, one blue accent.
import { loadFont as loadGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadPixel } from "@remotion/google-fonts/Silkscreen";

export const { fontFamily: GROTESK } = loadGrotesk("normal", { weights: ["400", "500", "600", "700"], subsets: ["latin"] });
export const { fontFamily: PIXEL } = loadPixel("normal", { weights: ["400", "700"], subsets: ["latin"] });

export const C = {
  paper: "#f1efe9",
  paperLine: "rgba(20, 20, 20, 0.055)",
  ink: "#141414",
  ink2: "#4a4a48",
  muted: "#8a8984",
  blue: "#4a6cf7",
  red: "#e0412f",
  green: "#2f8f5b",
  amber: "#d08a1e",
  night: "#0f1013",
  nightLine: "rgba(255, 255, 255, 0.06)",
  nightInk: "#f1efe9",
  card: "#fbfaf7",
};

export const FPS = 30;
export const W = 1920;
export const H = 1080;
export const s = (seconds: number) => Math.round(seconds * FPS);
