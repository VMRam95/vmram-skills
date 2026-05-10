---
name: remotion
description: |
  Create programmatic videos with Remotion (React-based video framework).
  Trigger phrases: "remotion", "create video", "programmatic video", "/remotion"
---

# Remotion Video Creation

Use this skill when creating programmatic videos with Remotion (React-based video framework).

## Setup Project

```bash
mkdir -p /tmp/remotion-project && cd /tmp/remotion-project
npm init -y
npm install remotion @remotion/cli @remotion/bundler typescript @types/react @types/node
mkdir -p src public
```

## Project Structure

```
/tmp/remotion-project/
├── public/           # Static assets (images, fonts)
├── src/
│   ├── index.ts      # Entry point with registerRoot()
│   ├── Root.tsx      # Composition definitions
│   └── MyVideo.tsx   # Video components
├── remotion.config.ts
└── tsconfig.json
```

---

## Core Rules

### 1. Animations - ALWAYS use useCurrentFrame()

**NEVER use CSS animations or Tailwind animation classes. They won't render.**

```tsx
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

export const MyComponent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Convert seconds to frames
  const durationSeconds = 2;
  const durationFrames = durationSeconds * fps;

  const opacity = interpolate(
    frame,
    [0, durationFrames],
    [0, 1],
    { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
  );

  return <div style={{ opacity }}>Animated content</div>;
};
```

### 2. Spring Animations - Natural Movement

```tsx
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

export const SpringAnimation: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Smooth reveal
  const smoothProgress = spring({ frame, fps, config: { damping: 200 } });

  // UI elements (slight bounce)
  const uiProgress = spring({ frame, fps, config: { damping: 20, stiffness: 200 } });

  // Playful motion (bouncy)
  const playfulProgress = spring({ frame, fps, config: { damping: 8 } });

  // Heavy objects (slow, weighty)
  const heavyProgress = spring({ frame, fps, config: { damping: 15, stiffness: 80, mass: 2 } });

  // With delay
  const delayedProgress = spring({ frame, fps, config: { damping: 200 }, delay: 30 });

  return <div style={{ transform: `translateY(${(1 - smoothProgress) * 100}px)` }} />;
};
```

### 3. Easing Functions - Custom Curves

```tsx
import { interpolate, Easing } from "remotion";

// Available easing combinations:
// Convexity: in, out, inOut
// Curves: quad, sin, exp, circle, cubic, back, bounce, elastic

const value = interpolate(frame, [0, 100], [0, 1], {
  easing: Easing.inOut(Easing.quad),  // Smooth acceleration/deceleration
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});

// Other examples:
// Easing.out(Easing.exp)     - Fast start, slow end
// Easing.in(Easing.circle)   - Slow start, fast end
// Easing.inOut(Easing.cubic) - Natural movement
// Easing.out(Easing.back)    - Overshoot effect
```

### 4. Images - ALWAYS use <Img> component

**NEVER use native <img>, Next.js Image, or CSS background-image.**

```tsx
import { Img, staticFile } from "remotion";

// Local images (from public/ folder)
<Img src={staticFile("background.png")} style={{ width: "100%", height: "100%" }} />

// Remote images (must have CORS enabled)
<Img src="https://example.com/image.png" />

// Dynamic images
<Img src={staticFile(`frames/frame${frame}.png`)} />
```

### 5. Sequencing - Timeline Control

```tsx
import { Sequence, Series, useCurrentFrame } from "remotion";

export const SequencedVideo: React.FC = () => {
  return (
    <>
      {/* Delayed appearance */}
      <Sequence from={30} durationInFrames={60} premountFor={10}>
        <FadeInComponent />
      </Sequence>

      {/* Sequential playback */}
      <Series>
        <Series.Sequence durationInFrames={60}>
          <Scene1 />
        </Series.Sequence>
        <Series.Sequence durationInFrames={60} offset={-15}> {/* Overlap */}
          <Scene2 />
        </Series.Sequence>
      </Series>
    </>
  );
};

// Inside Sequence, useCurrentFrame() returns LOCAL frame (starts at 0)
```

### 6. Loop-Friendly Animations

For seamless loops, ensure start and end states match:

```tsx
const { durationInFrames } = useVideoConfig();

// Cyclic animation (returns to start)
const rotation = interpolate(
  frame,
  [0, durationInFrames],
  [0, 360]  // Full rotation
);

// Ping-pong effect
const pingPong = Math.sin((frame / durationInFrames) * Math.PI * 2);

// Seamless particle loop
const particleY = ((frame * speed + offset) % totalHeight) - startOffset;
```

---

## Composition Setup

### remotion.config.ts
```ts
import { Config } from "@remotion/cli/config";
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
```

### src/index.ts
```ts
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
```

### src/Root.tsx
```tsx
import { Composition } from "remotion";
import { MyVideo } from "./MyVideo";

export const Root: React.FC = () => (
  <Composition
    id="MyVideo"
    component={MyVideo}
    durationInFrames={150}  // 5 seconds at 30fps
    fps={30}
    width={1920}
    height={1080}
  />
);
```

---

## Rendering

```bash
# Basic render
npx remotion render src/index.ts MyVideo out/video.mp4

# With options
npx remotion render src/index.ts MyVideo out/video.mp4 \
  --codec h264 \
  --fps 30 \
  --width 1920 \
  --height 1080

# Preview in browser
npx remotion studio
```

---

## Common Patterns

### Rain Effect
```tsx
const RainDrop: React.FC<{ x: number; delay: number; speed: number }> = ({ x, delay, speed }) => {
  const frame = useCurrentFrame();
  const { height, durationInFrames } = useVideoConfig();

  const y = ((frame * speed + delay) % (height + 100)) - 50;

  return (
    <div style={{
      position: "absolute",
      left: x,
      top: y,
      width: 1,
      height: 30,
      background: "linear-gradient(to bottom, transparent, rgba(200,220,255,0.5))",
    }} />
  );
};
```

### Flickering Light
```tsx
const flicker = useMemo(() => {
  const base = Math.sin(frame * 0.5) * 0.1 + 0.9;
  const noise = Math.sin(frame * 0.3 + 2) * 0.05;
  const spike = frame % 47 < 3 ? 0.7 : 1;
  return base * spike + noise;
}, [frame]);
```

### Parallax Layers
```tsx
const { fps } = useVideoConfig();

// Use spring for organic parallax movement
const parallaxProgress = spring({
  frame,
  fps,
  config: { damping: 200 },
  durationInFrames: durationInFrames,
});

const backgroundX = interpolate(parallaxProgress, [0, 1], [0, 20]);
const foregroundX = interpolate(parallaxProgress, [0, 1], [0, 40]);
```
