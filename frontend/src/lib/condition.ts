/** The three condition classes the model can PREDICT. None of them is a confirmed failure. */
export const CONDITION_ORDER = ["Normal", "Alert", "Danger"] as const;
export type Condition = (typeof CONDITION_ORDER)[number];

export interface ConditionMeta {
  label: string;
  /** Plain-language meaning for plant operators. */
  meaning: string;
  /** CSS custom property names defined in styles/global.css */
  colorVar: string;
  softVar: string;
  shape: "circle" | "triangle" | "diamond";
}

const META: Record<Condition, ConditionMeta> = {
  Normal: {
    label: "Normal",
    meaning: "The readings look like the records labelled Normal in the training data.",
    colorVar: "--status-normal", softVar: "--status-normal-soft", shape: "circle",
  },
  Alert: {
    label: "Alert",
    meaning: "The readings look like the records labelled Alert in the training data. Consider a closer look.",
    colorVar: "--status-alert", softVar: "--status-alert-soft", shape: "triangle",
  },
  Danger: {
    label: "Danger",
    meaning: "The readings look like the records labelled Danger in the training data. Have a qualified person inspect the motor.",
    colorVar: "--status-danger", softVar: "--status-danger-soft", shape: "diamond",
  },
};

const UNKNOWN: ConditionMeta = {
  label: "Unknown", meaning: "This class name is not one the page knows.", colorVar: "--text-secondary", softVar: "--surface-2", shape: "circle",
};

export const isCondition = (v: string): v is Condition => (CONDITION_ORDER as readonly string[]).includes(v);
export const conditionMeta = (v: string): ConditionMeta => (isCondition(v) ? META[v] : { ...UNKNOWN, label: v });
export const severityRank = (v: string): number => {
  const i = (CONDITION_ORDER as readonly string[]).indexOf(v);
  return i < 0 ? -1 : i;
};
