import type { CSSProperties } from "react";
type Name = "chat" | "chart" | "shield" | "arrow" | "book" | "close" | "chevron" | "code" | "check" | "clock" | "refresh" | "plus";
const paths: Record<Name, string> = {
  chat: "M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z",
  chart: "M4 3v18h17M8 16v-4m5 4V7m5 9V4", shield: "M12 3 3 7v5c0 5 9 10 9 10s9-5 9-10V7zM8 12l3 3 5-6",
  arrow: "M5 12h14m-6-6 6 6-6 6", book: "M4 3h13a3 3 0 0 1 3 3v15H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3M3 17h17M8 7h8M8 11h6",
  close: "m6 6 12 12M6 18 18 6", chevron: "m9 5 7 7-7 7", code: "m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18", check: "m5 12 4 4L19 6",
  clock: "M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0", refresh: "M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3", plus: "M12 5v14M5 12h14",
};
export function Icon({name, size = 20, style}: {name: Name; size?: number; style?: CSSProperties}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}
