import { Alert, Button, Group, Loader, Stack, Text } from "@mantine/core";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <Group gap="sm" role="status" aria-live="polite" p="md">
      <Loader size="sm" />
      <Text>{label}</Text>
    </Group>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="panel" role="status">
      <Stack gap="xs" align="flex-start">
        <Text fw={600}>{title}</Text>
        {children && <Text c="dimmed" size="sm" component="div">{children}</Text>}
        {action}
      </Stack>
    </div>
  );
}

/** What went wrong in plain words, what to do about it, and a retry button when retrying makes sense. */
export function ErrorState({ error, onRetry, title = "Something went wrong" }: { error: ApiError | Error | null; onRetry?: () => void; title?: string }) {
  const api = error instanceof ApiError ? error : null;
  const hint =
    api?.code === "network_error" || api?.code === "timeout"
      ? "Check that the backend is running (see the Status light at the top). Then try again."
      : api?.code === "not_configured"
        ? "The site was built without a backend address. See docs/frontend.md, section 'Configuration'."
        : api?.status === 401 || api?.code === "unauthorized" || api?.code === "invalid_api_key"
          ? "This server asks for an access key. Choose 'Access key' at the top of the page and enter it."
          : undefined;
  return (
    <Alert color="red" variant="light" title={title} role="alert">
      <Stack gap="xs" align="flex-start">
        <Text size="sm">{error?.message ?? "Unknown error."}</Text>
        {hint && <Text size="sm">{hint}</Text>}
        {onRetry && <Button size="xs" variant="default" onClick={onRetry}>Try again</Button>}
      </Stack>
    </Alert>
  );
}
