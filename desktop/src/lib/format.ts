import type {
  CompiledMemory,
  FrequencyDefinitionRecord,
  SignalingSpec,
} from "$lib/types";

export function mhz(frequencyHz: number): string {
  return `${(frequencyHz / 1_000_000).toFixed(6)} MHz`;
}

export function offsetSummary(offsetHz: number): string {
  const sign = offsetHz > 0 ? "+" : "-";
  return `${sign}${(Math.abs(offsetHz) / 1_000_000).toFixed(3)} MHz`;
}

export function memoryTxSummary(memory: CompiledMemory): string {
  if (memory.transmit_behavior === "same") return "Same as RX";
  if (memory.transmit_behavior === "disabled") return "Disabled";
  if (memory.transmit_behavior === "offset" && memory.offset_hz !== null) {
    return offsetSummary(memory.offset_hz);
  }
  if (memory.transmit_frequency_hz !== null) return mhz(memory.transmit_frequency_hz);
  return "-";
}

export function definitionTxSummary(definition: FrequencyDefinitionRecord): string {
  if (definition.transmit_behavior === "same") return "Same as RX";
  if (definition.transmit_behavior === "disabled") return "Receive only";
  if (definition.transmit_behavior === "offset" && definition.offset_hz !== null) {
    return offsetSummary(definition.offset_hz);
  }
  if (definition.transmit_frequency_hz !== null) {
    return mhz(definition.transmit_frequency_hz);
  }
  return "-";
}

export function signalingSummary(signaling: SignalingSpec): string {
  if (signaling.kind === "ctcss" && signaling.ctcss_hz !== null) {
    return `CTCSS ${signaling.ctcss_hz.toFixed(1)} Hz`;
  }
  if (signaling.kind === "dcs" && signaling.dcs_code !== null) {
    return `DCS ${signaling.dcs_code.toString().padStart(3, "0")} ${signaling.dcs_polarity}`;
  }
  return "None";
}

export function tuningStepSummary(stepHz: number | null | undefined): string {
  if (stepHz === null || stepHz === undefined) return "Default";
  return `${Number((stepHz / 1_000).toFixed(3))} kHz`;
}

export function powerSummary(
  value: Pick<FrequencyDefinitionRecord, "power_dbm" | "power_label">,
): string {
  if (value.power_label) return value.power_label;
  if (value.power_dbm !== null && value.power_dbm !== undefined) {
    return `${Number(value.power_dbm.toFixed(1))} dBm`;
  }
  return "Default";
}

export function scanSummary(scanSkip: string | null | undefined): string {
  return scanSkip ? `Skip ${scanSkip}` : "Scan";
}
