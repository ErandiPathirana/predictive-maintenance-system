import { createTheme, type MantineColorsTuple } from "@mantine/core";

const steel: MantineColorsTuple = ["#e7f2f5", "#cde2e8", "#a6ccd7", "#7db3c3", "#559bb0", "#2f829a", "#0f5c73", "#0a4659", "#07333f", "#04212a"];

/** Mantine's default red (#fa5252 at shade 6) gives only 3.3:1 with white text, which fails WCAG AA on the Danger notice and red buttons. Shades 6 to 9 are darkened; lighter shades are unchanged. */
const red: MantineColorsTuple = ["#fff5f5", "#ffe3e3", "#ffc9c9", "#ffa8a8", "#ff8787", "#e5484d", "#b3261e", "#a9211a", "#8f1d17", "#741813"];

export const theme = createTheme({
  primaryColor: "steel",
  primaryShade: 6,
  colors: { steel, red },
  fontFamily: 'var(--font-body)',
  headings: { fontFamily: 'var(--font-display)' },
  defaultRadius: "sm",
  focusRing: "auto",
});
