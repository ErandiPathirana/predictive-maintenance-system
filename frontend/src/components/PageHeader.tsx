import { Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

export function PageHeader({ title, intro, children }: { title: string; intro?: ReactNode; children?: ReactNode }) {
  return (
    <Stack gap={4} mb="md">
      <Title order={1} size="h2">{title}</Title>
      {intro && <Text c="dimmed" maw={760} component="div">{intro}</Text>}
      {children}
    </Stack>
  );
}
