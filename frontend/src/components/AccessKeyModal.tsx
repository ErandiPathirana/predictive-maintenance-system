import { Button, Group, Modal, PasswordInput, Text } from "@mantine/core";
import { useState } from "react";
import { hasAccessKey, setAccessKey } from "../api/client";

/** The key is held in memory only. Reloading the page forgets it. */
export function AccessKeyModal({ opened, onClose, onSaved }: { opened: boolean; onClose: () => void; onSaved: () => void }) {
  const [value, setValue] = useState("");
  const save = () => { setAccessKey(value); setValue(""); onSaved(); onClose(); };
  return (
    <Modal opened={opened} onClose={onClose} title="Access key" centered>
      <Text size="sm" mb="sm">
        Only needed if the server administrator turned on key protection. The key stays in this browser tab's memory and is forgotten when you reload.
      </Text>
      <PasswordInput label="Access key" value={value} onChange={(e) => setValue(e.currentTarget.value)} autoComplete="off" data-autofocus />
      <Group justify="space-between" mt="md">
        <Button variant="subtle" color="gray" disabled={!hasAccessKey()} onClick={() => { setAccessKey(null); onSaved(); onClose(); }}>Forget key</Button>
        <Group>
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={!value.trim()}>Use this key</Button>
        </Group>
      </Group>
    </Modal>
  );
}
