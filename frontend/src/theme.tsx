import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "light" | "dark";

/** Chart colours per theme. Canvas charts cannot read CSS variables, so they live here.
 *  The dark values are the same hues re-stepped for a dark surface, not an inversion. */
export interface ChartColors {
  blue: string; blueTint: string; orange: string; yellow: string;
  ink: string; grey: string; grid: string; text: string; surface: string;
}
export type SeriesColor = "blue" | "orange" | "yellow";

const CHART_COLORS: Record<Theme, ChartColors> = {
  light: { blue: "#2a78d6", blueTint: "#a9c9ef", orange: "#eb6834", yellow: "#d99000",
    ink: "#1d2330", grey: "#7a8291", grid: "#ebe8e1", text: "#4b5565", surface: "#ffffff" },
  dark: { blue: "#3987e5", blueTint: "#24507f", orange: "#e8703c", yellow: "#d99a1c",
    ink: "#e8ecf2", grey: "#8b94a3", grid: "#27303c", text: "#aab3c0", surface: "#171d26" },
};

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: "light", toggle: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  // index.html has already set data-theme (saved choice, else the OS preference).
  const [theme, setTheme] = useState<Theme>(
    () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light"),
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* private mode: the choice just won't persist */
    }
  }, [theme]);
  return (
    <ThemeContext.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
export const useChartColors = (): ChartColors => CHART_COLORS[useContext(ThemeContext).theme];
