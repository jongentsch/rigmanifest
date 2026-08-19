import type { CompiledMemory, FrequencyDefinitionRecord } from "$lib/types";

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
