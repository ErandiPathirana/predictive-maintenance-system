import { createTheme, type MantineColorsTuple } from "@mantine/core";

const steel: MantineColorsTuple = ["#e7f2f5", "#cde2e8", "#a6ccd7", "#7db3c3", "#559bb0", "#2f829a", "#0f5c73", "#0a4659", "#07333f", "#04212a"];

export const theme = createTheme({
  primaryColor: "steel",
  primaryShade: 6,
  colors: { steel },
  fontFamily: 'var(--font-body)',
  headings: { fontFamily: 'var(--font-display)' },
  defaultRadius: "sm",
  focusRing: "auto",
});
