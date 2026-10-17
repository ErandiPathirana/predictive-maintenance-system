import { Button, Group, Modal, Text } from "@mantine/core";

/** Asks before anything is thrown away. Cancel is the default (focused) choice. */
export function ConfirmModal({ opened, title, message, confirmLabel, onConfirm, onCancel }: {
  opened: boolean; title: string; message: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Modal opened={opened} onClose={onCancel} title={title} centered>
      <Text size="sm" mb="md">{message}</Text>
      <Group justify="flex-end">
        <Button variant="default" onClick={onCancel} data-autofocus>Keep it</Button>
        <Button color="red" onClick={onConfirm}>{confirmLabel}</Button>
      </Group>
    </Modal>
  );
}
