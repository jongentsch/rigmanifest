import type { RadioInstance } from "$lib/types";

const storageKey = "rigmanifest-radio-inventory-v2";
const legacyStorageKey = "rigmanifest-radio-inventory-v1";

export const defaultRadio: RadioInstance = {
  id: "default-vx6r",
  name: "My VX-6R",
  radioModelId: "yaesu-vx6r",
  memoryStart: 1,
  mapSetsToBanks: true,
  notes: "",
};

function isRadioInstance(value: unknown): value is RadioInstance {
  if (!value || typeof value !== "object") return false;
  const radio = value as Record<string, unknown>;
  return (
    typeof radio.id === "string" &&
    typeof radio.name === "string" &&
    typeof radio.radioModelId === "string" &&
    typeof radio.memoryStart === "number" &&
    Number.isInteger(radio.memoryStart) &&
    radio.memoryStart >= 0 &&
    typeof radio.mapSetsToBanks === "boolean" &&
    typeof radio.notes === "string"
  );
}

function migrateLegacyRadio(value: unknown): RadioInstance | null {
  if (!value || typeof value !== "object") return null;
  const radio = value as Record<string, unknown>;
  if (
    typeof radio.id !== "string" ||
    typeof radio.name !== "string" ||
    typeof radio.radioTypeId !== "string" ||
    typeof radio.memoryStart !== "number" ||
    typeof radio.mapGroupsToBanks !== "boolean" ||
    typeof radio.notes !== "string"
  ) return null;

  return {
    id: radio.id,
    name: radio.name,
    radioModelId: radio.radioTypeId,
    memoryStart: radio.memoryStart,
    mapSetsToBanks: radio.mapGroupsToBanks,
    notes: radio.notes,
  };
}

export function readLegacyRadioInventory(): RadioInstance[] | null {
  const stored = localStorage.getItem(storageKey);
  if (stored) {
    try {
      const parsed: unknown = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed.every(isRadioInstance)) {
        return parsed;
      }
    } catch {
      // Fall through to migration or a safe starter radio.
    }
  }

  const legacy = localStorage.getItem(legacyStorageKey);
  if (legacy) {
    try {
      const parsed: unknown = JSON.parse(legacy);
      if (Array.isArray(parsed)) {
        const migrated = parsed.map(migrateLegacyRadio);
        if (migrated.length > 0 && migrated.every((item) => item !== null)) {
          return migrated as RadioInstance[];
        }
      }
    } catch {
      // Fall through to a safe starter radio.
    }
  }

  return null;
}

export function clearLegacyRadioInventory(): void {
  localStorage.removeItem(storageKey);
  localStorage.removeItem(legacyStorageKey);
}

export function createRadioInstance(
  radioModelId: string,
  memoryStart: number,
  name = "New radio",
): RadioInstance {
  return {
    id: crypto.randomUUID(),
    name,
    radioModelId,
    memoryStart,
    mapSetsToBanks: true,
    notes: "",
  };
}
