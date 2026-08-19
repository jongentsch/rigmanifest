export const textScaleOptions = [
  { value: "1", label: "Standard · 100%" },
  { value: "1.15", label: "Comfortable · 115%" },
  { value: "1.3", label: "Large · 130%" },
  { value: "1.45", label: "Extra large · 145%" },
] as const;

export type TextScale = (typeof textScaleOptions)[number]["value"];

const storageKey = "rigmanifest-text-scale";
const baseFontSizePx = 16;

export function isTextScale(value: string | null): value is TextScale {
  return textScaleOptions.some((option) => option.value === value);
}

export function loadTextScale(): TextScale {
  if (typeof localStorage === "undefined") return "1";
  const stored = localStorage.getItem(storageKey);
  return isTextScale(stored) ? stored : "1";
}

export function applyTextScale(scale: TextScale): void {
  if (typeof document === "undefined") return;
  document.documentElement.style.fontSize = `${baseFontSizePx * Number(scale)}px`;
  document.documentElement.dataset.textScale = scale;
}

export function saveTextScale(scale: TextScale): void {
  localStorage.setItem(storageKey, scale);
  applyTextScale(scale);
}
