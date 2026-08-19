export type Severity = "info" | "warning" | "error";

export interface PlanSummary {
  included: number;
  omitted: number;
  warnings: number;
  errors: number;
}

export interface CapacitySummary {
  capacity: number;
  compatible_candidates: number;
  used: number;
  omitted_for_capacity: number;
}

export interface ToneSpec {
  mode: string;
  encode_hz: number | null;
  decode_hz: number | null;
  dtcs_code: number | null;
  dtcs_polarity: string;
}

export interface CompiledMemory {
  source_channel_id: string;
  memory_number: number;
  target_name: string;
  receive_frequency_hz: number;
  transmit_behavior: string;
  transmit_frequency_hz: number | null;
  offset_hz: number | null;
  mode: string;
  tone: ToneSpec;
  bank_assignments: string[];
  applied_transformations: string[];
}

export interface OmittedChannel {
  channel_id: string;
  reason: string;
}

export interface Diagnostic {
  code: string;
  severity: Severity;
  channel_id: string | null;
  message: string;
  details: Record<string, string>;
}

export interface ChannelRecord {
  id: string;
  name: string;
  receive_frequency_hz: number;
  transmit_behavior: string;
  transmit_frequency_hz: number | null;
  offset_hz: number | null;
  mode: string;
  tags: string[];
  priority: string;
}

export interface CompileResult {
  schema_version: number;
  compiler_version: string;
  profile: { id: string; name: string };
  target: { id: string; manufacturer: string; model: string };
  summary: PlanSummary;
  capacity: CapacitySummary;
  memories: CompiledMemory[];
  omitted_channels: OmittedChannel[];
  diagnostics: Diagnostic[];
  channel_library: ChannelRecord[];
  csv_path: string | null;
}
