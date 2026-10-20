import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Emerald accent. Shade 5 is #059669; shade 6 (#047857) is the primary shade so white button text keeps 4.5:1 contrast (white on #059669 is only 3.8:1).
const emerald: MantineColorsTuple = ["#ecfdf5", "#d1fae5", "#a7f3d0", "#6ee7b7", "#34d399", "#059669", "#047857", "#065f46", "#064e3b", "#022c22"];

/** Mantine's default red (#fa5252 at shade 6) gives only 3.3:1 with white text, which fails WCAG AA on the Danger notice and red buttons. Shades 6 to 9 are darkened; lighter shades are unchanged. */
const red: MantineColorsTuple = ["#fff5f5", "#ffe3e3", "#ffc9c9", "#ffa8a8", "#ff8787", "#e5484d", "#b3261e", "#a9211a", "#8f1d17", "#741813"];

export const theme = createTheme({
  primaryColor: "emerald",
  primaryShade: 6,
  colors: { emerald, red },
  fontFamily: 'var(--font-body)',
  headings: { fontFamily: 'var(--font-display)' },
  defaultRadius: "sm",
  focusRing: "auto",
});
