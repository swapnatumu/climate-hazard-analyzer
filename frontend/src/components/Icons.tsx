// Small inline stroke icons; they inherit the text colour.
const base = {
  width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const HeatIcon = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
  </svg>
);

export const DroughtIcon = () => (
  <svg {...base}>
    <path d="M12 3s6 6.3 6 10.5a6 6 0 0 1-12 0C6 9.300 12 3 12 3z" />
    <path d="M4 4l16 16" />
  </svg>
);

export const RainIcon = () => (
  <svg {...base}>
    <path d="M7 15a4 4 0 0 1 .5-8 5.500 5.500 0 0 1 10.600 1.500A3.300 3.300 0 0 1 17.500 15z" />
    <path d="M8.500 18l-1 2.500M12.500 18l-1 2.500M16.500 18l-1 2.500" />
  </svg>
);

export const SunIcon = HeatIcon;

export const MoonIcon = () => (
  <svg {...base}>
    <path d="M20 14.500A8 8 0 0 1 9.500 4a8 8 0 1 0 10.500 10.500z" />
  </svg>
);

export const HAZARD_ICONS: Record<string, () => JSX.Element> = {
  heatwave: HeatIcon,
  drought: DroughtIcon,
  rainfall: RainIcon,
};
