export type Severity = "info" | "warning" | "error";
export type CatalogOrigin = "preset" | "user";
export type CapabilityStatus = "supported" | "unsupported" | "unknown";

export interface PlanSummary {
  included: number;
  programmed: number;
  factory_provided: number;
  factory_sets: number;
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

export type SignalingKind = "none" | "ctcss" | "dcs";

export interface SignalingSpec {
  kind: SignalingKind;
  ctcss_hz: number | null;
  dcs_code: number | null;
  dcs_polarity: "N" | "R";
}

export interface CompiledMemory {
  source_frequency_definition_id: string;
  source_frequency_set_ids: string[];
  source_profile_ids: string[];
  selected_directly: boolean;
  memory_number: number;
  target_name: string;
  receive_frequency_hz: number;
  transmit_behavior: string;
  transmit_frequency_hz: number | null;
  offset_hz: number | null;
  mode: string;
  transmit_access: SignalingSpec;
  receive_squelch: SignalingSpec;
  power_dbm: number | null;
  power_label: string | null;
  scan_skip: string;
  tuning_step_hz: number | null;
  bank_assignments: string[];
  applied_transformations: string[];
}

export interface OmittedFrequencyDefinition {
  frequency_definition_id: string;
  reason: string;
}

export interface FactorySetCoverage {
  frequency_set_id: string;
  frequency_set_name: string;
  interface_label: string;
  frequency_definition_ids: string[];
  definition_count: number;
  frequency_editing: CapabilityStatus;
  chirp_editing: CapabilityStatus;
}

export interface Diagnostic {
  code: string;
  severity: Severity;
  frequency_definition_id: string | null;
  frequency_set_id: string | null;
  message: string;
  details: Record<string, string>;
}

export interface FrequencyDefinitionRecord {
  id: string;
  name: string;
  origin: CatalogOrigin;
  read_only: boolean;
  receive_frequency_hz: number;
  transmit_behavior: string;
  transmit_frequency_hz: number | null;
  offset_hz: number | null;
  mode: string;
  transmit_access: SignalingSpec;
  receive_squelch: SignalingSpec;
  tags: string[];
  priority: string;
  notes: string;
  power_dbm?: number | null;
  power_label?: string | null;
  scan_skip?: string;
  tuning_step_hz?: number | null;
}

export interface FrequencySetMemberRecord {
  frequency_definition_id: string;
  position: number;
  channel_designator: string | null;
}

export interface FrequencySetRecord {
  id: string;
  name: string;
  origin: CatalogOrigin;
  read_only: boolean;
  description: string;
  jurisdiction?: string | null;
  source_label?: string | null;
  source_url?: string | null;
  reviewed_at?: string | null;
  members: FrequencySetMemberRecord[];
}

export interface ProfileRecord {
  id: string;
  name: string;
  description: string;
  frequency_set_ids: string[];
  frequency_definition_ids: string[];
  frequency_plan_id: string | null;
}

export interface FactoryFrequencySetRecord {
  frequency_set_id: string;
  frequency_set_name: string;
  interface_label: string;
  frequency_editing: CapabilityStatus;
  chirp_editing: CapabilityStatus;
}

export interface RadioModelRecord {
  id: string;
  manufacturer: string;
  model: string;
  memory_capacity: number;
  memory_start: number;
  max_label_length: number;
  supports_banks: boolean;
  bank_count: number;
  chirp_driver_reference: string | null;
  receive_ranges: [number, number][];
  transmit_ranges: [number, number][];
  supported_modes: string[];
  supported_tone_modes: string[];
  valid_cross_modes: string[];
  valid_tuning_steps_hz: number[];
  valid_ctcss_tones_hz: number[];
  valid_dtcs_codes: number[];
  factory_frequency_sets: FactoryFrequencySetRecord[];
}

export interface FrequencyPlanSegmentRecord {
  id: string;
  name: string;
  lower_hz: number;
  upper_hz: number;
  use: "simplex" | "repeater-output";
  suggested_offset_hz: number | null;
  raster_anchor_hz: number | null;
  raster_spacing_hz: number | null;
  notes: string;
}

export interface FrequencyPlanRecord {
  id: string;
  name: string;
  jurisdiction: string;
  authority_tier: "national-recommendation" | "regional-coordinator";
  reviewed_at: string;
  source_label: string;
  source_url: string;
  advisory: boolean;
  segments: FrequencyPlanSegmentRecord[];
}

export interface WorkspaceCatalog {
  schema_version: number;
  ctcss_tones_hz: number[];
  profiles: ProfileRecord[];
  radio_models: RadioModelRecord[];
  frequency_sets: FrequencySetRecord[];
  frequency_definitions: FrequencyDefinitionRecord[];
  frequency_plans: FrequencyPlanRecord[];
}

export interface UserCatalogRecords {
  frequencyDefinitions: FrequencyDefinitionRecord[];
  frequencySets: FrequencySetRecord[];
}

export interface WorkspaceState {
  schema_version: number;
  user_catalog: UserCatalogRecords;
  radios: RadioInstance[];
  profiles: ProfileRecord[];
  default_frequency_plan_id: string | null;
  migrated_legacy?: boolean;
}

export interface ChirpCatalogImportResult {
  source_path: string;
  definition_count: number;
  frequency_definitions: FrequencyDefinitionRecord[];
  frequency_set: FrequencySetRecord;
}

export interface ChirpImageImportResult {
  source_path: string;
  source_filename: string;
  driver_reference: string;
  manufacturer: string;
  model: string;
  definition_count: number;
  bank_count: number;
  setting_count: number;
  memory_start: number;
  memory_capacity: number;
  max_label_length: number;
  frequency_definitions: FrequencyDefinitionRecord[];
  frequency_sets: FrequencySetRecord[];
  profile: ProfileRecord;
  image_version: RadioImageVersion;
}

export interface RadioImageVersion {
  id: string;
  radio_id: string;
  kind: "source" | "compiled";
  path: string;
  filename: string;
  driver_reference: string;
  byte_size: number;
  sha256: string;
  created_at: string;
}

export interface CompileConfiguration {
  memoryStart: number;
  mapSetsToBanks: boolean;
  useFactorySets: boolean;
  additionalFrequencySetIds: string[];
  additionalFrequencyDefinitionIds: string[];
  advisoryPlanId: string | null;
}

export interface RadioInstance {
  id: string;
  name: string;
  radioModelId: string;
  driverReference?: string;
  manufacturer?: string;
  model?: string;
  imageFilename?: string;
  memoryCapacity?: number;
  maxLabelLength?: number;
  bankCount?: number;
  settingCount?: number;
  memoryStart: number;
  mapSetsToBanks: boolean;
  notes: string;
}

export interface CompiledBank {
  bank_number: number;
  frequency_set_id: string;
  name: string;
  memory_numbers: number[];
}

export interface CompileResult {
  schema_version: number;
  compiler_version: string;
  profile: ProfileRecord;
  profiles: ProfileRecord[];
  selection: {
    additional_frequency_set_ids: string[];
    additional_frequency_definition_ids: string[];
    advisory_plan_id: string | null;
  };
  target: { id: string; manufacturer: string; model: string };
  summary: PlanSummary;
  capacity: CapacitySummary;
  memories: CompiledMemory[];
  banks: CompiledBank[];
  factory_sets: FactorySetCoverage[];
  omitted_frequency_definitions: OmittedFrequencyDefinition[];
  diagnostics: Diagnostic[];
  csv_path: string | null;
  image_path?: string | null;
  managed_image_path?: string | null;
  image_version?: RadioImageVersion | null;
}
