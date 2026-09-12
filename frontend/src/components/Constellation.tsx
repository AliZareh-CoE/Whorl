// The living constellation (Observatory identity): a canvas particle field of your research.
// The drawing lives in static/js/constellation.js — a plain ES module shared with the login
// template and loaded lazily here so the SPA bundle stays lean and the login page needs no
// React. Renders nothing but a canvas; the parent positions it.
import { useEffect, useRef } from "react";

export type Anchor = { label: string; color?: string; weight?: number };

type Mod = {
  mountConstellation: (
    canvas: HTMLCanvasElement,
    opts: { anchors?: Anchor[]; density?: number; linkDist?: number },
  ) => () => void;
};

export function Constellation({ anchors, density = 1, className = "" }: { anchors: Anchor[]; density?: number; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const key = JSON.stringify(anchors);
  useEffect(() => {
    let stop: (() => void) | undefined;
    let cancelled = false;
    const canvas = ref.current;
    if (!canvas) return;
    const url = "/static/js/constellation.js"; // a served static file, not a bundled module
    import(/* @vite-ignore */ url)
      .then((mod: Mod) => {
        if (cancelled) return;
        stop = mod.mountConstellation(canvas, { anchors: JSON.parse(key), density });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [key, density]);
  return <canvas ref={ref} aria-hidden="true" className={`block h-full w-full ${className}`} />;
}
