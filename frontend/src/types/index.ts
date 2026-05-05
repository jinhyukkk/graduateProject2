// ============================================================
// Domain Models — matches API contract snake_case responses
// ============================================================

export interface CorrectionStep {
  round: number;
  error_type: string;
  original_sql: string;
  corrected_sql: string;
  validation_success: boolean;
  semantic_score: number;
}

export interface ValidationResult {
  success: boolean;
  error_type: string | null;
  error_message: string | null;
  is_empty: boolean;
  is_excessive: boolean;
  row_count: number;
}

export interface VerificationResult {
  back_translation: string;
  similarity_score: number;
  // 3축 검증: LLM 자기 비평 (Claude/GPT 류 self-critique)
  llm_critique_score?: number;
  llm_critique_pass?: boolean;
  llm_critique_reason?: string;
  is_consistent: boolean;
  mismatch_diagnosis: string | null;
}

export interface SchemaColumn {
  name: string;
  type: string;
  is_primary_key: boolean;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export interface ForeignKey {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
}

export interface SchemaContext {
  tables: SchemaTable[];
  foreign_keys: ForeignKey[];
}

// Phase 3: Guardrails info — §6.2 운영 가이드라인 6 케이스 권장 액션 포함
export interface GuardrailsInfo {
  rows_truncated: boolean;
  original_row_count: number;
  low_confidence_warning: boolean;
  warning_message: string;
  // §6.2 운영 가이드라인 케이스별 권장 액션
  action?: string;            // 'auto_execute' | 'auto_with_note' | 'user_warning' |
                              // 'hitl_triage' | 'retry_auto' | 'empty_result_info' |
                              // 'clarification_request'
  action_severity?: string;   // 'info' | 'success' | 'warning' | 'error'
  action_title?: string;
  action_detail?: string;
  case_id?: string;           // 'C1' | 'C2' | 'C3' | 'C4' | 'C5' | 'C6' | 'Cq' | 'C1m'
  persona_scenario?: string;  // 'S1' ~ 'S5' (페르소나 시나리오 ID)
}

// Phase 3: Conversation turn
export interface ConversationTurn {
  question: string;
  sql: string;
  explanation?: string;
}

// POST /api/query response
export interface QueryResult {
  id: string;
  query: string;
  db_id: string;
  original_sql: string;
  final_sql: string;
  was_corrected: boolean;
  correction_steps: CorrectionStep[];
  schema_context: SchemaContext;
  result: { columns: string[]; rows: Record<string, unknown>[] };
  explanation: string;
  latency: number;
  validation: ValidationResult;
  verification: VerificationResult;
  // Phase 2
  sql_confidence?: number;
  // Phase 3
  guardrails?: GuardrailsInfo;
}

// ============================================================
// Streaming query types
// ============================================================

/** sc_tsql.py の on_event が emit するパイプラインステージ名 */
export type PipelineStage =
  | 'schema_link'
  | 'sql_generating'
  | 'validating'
  | 'verifying'
  | 'correcting'
  | 'explaining';

/** QueryPage でストリーミング中に蓄積する状態 */
export interface StreamState {
  stage: PipelineStage | null;
  sql: string | null;
  confidence: number | null;
  /** SQL 생성 LLM의 CoT(Chain-of-Thought) 추론을 토큰 단위로 누적한 텍스트.
   *  reasoning_chunk 이벤트가 도착할 때마다 추가되어 ChatGPT 스타일 점진 표시. */
  reasoning: string;
  validation: { success: boolean; error_type: string | null } | null;
  verification: { score: number; is_consistent: boolean; back_translation: string } | null;
  correctionSteps: CorrectionStep[];
  explanation: string | null;
  finalResult: QueryResult | null;
}

export const initialStreamState = (): StreamState => ({
  stage: null,
  sql: null,
  confidence: null,
  reasoning: '',
  validation: null,
  verification: null,
  correctionSteps: [],
  explanation: null,
  finalResult: null,
});

// ============================================================
// Experiment types
// ============================================================

export interface AblationFlags {
  disable_schema_linker: boolean;
  disable_execution_validator: boolean;
  disable_semantic_verifier: boolean;
  disable_correction_loop: boolean;
}

export type PipelineMode = 'zero-shot' | 'din-sql' | 'dail-sql' | 'chess' | 'sc-tsql' | 'custom';

export interface ExperimentConfig {
  dataset: 'hrdb' | 'bird';
  model: string;
  max_rounds: number;
  semantic_threshold: number;
  sample_count: number | null;
  pipeline_mode?: PipelineMode;
  ablation?: AblationFlags;
}

export interface KSweepConfig {
  dataset: 'hrdb' | 'bird';
  model: string;
  semantic_threshold: number;
  sample_count: number | null;
  k_values: number[];
}

export interface BatchExperiment {
  batch_id: string;
  experiment_ids: string[];
  k_values: number[];
  status: string;
  current_k?: number;
  completed_count?: number;
}

export interface ExperimentMetrics {
  execution_accuracy: number;
  correction_success_rate: number;
  average_latency: number;
  total_evaluated: number;
}

export interface ExperimentSummary {
  id: string;
  dataset: string;
  status: 'running' | 'completed' | 'failed';
  config: ExperimentConfig;
  created_at: string;
  metrics: ExperimentMetrics | null;
}

export interface CorrectionProgress {
  round: number;
  cumulative_accuracy: number;
  newly_corrected: number;
}

export interface ErrorDistribution {
  error_type: string;
  count: number;
}

export interface ExperimentDetail extends ExperimentSummary {
  correction_progress: CorrectionProgress[];
  error_distribution: ErrorDistribution[];
}

export interface ExperimentDetailedResult {
  index: number;
  db_id: string;
  question: string;
  gold_sql: string;
  predicted_sql: string;
  correct: boolean;
  latency: number;
  correction_rounds: number;
  correction_history: CorrectionStep[];
}

export interface QueryDetailResult extends ExperimentDetailedResult {
  final_validation: ValidationResult;
  final_verification: VerificationResult;
  result: { columns: string[]; rows: Record<string, unknown>[] };
}

// ============================================================
// API Response wrappers
// ============================================================

export interface DatabaseInfo {
  id: string;
  dataset: string;
  table_count: number;
  path: string;
}

export interface DatabasesResponse {
  databases: DatabaseInfo[];
}

export interface ExperimentsResponse {
  experiments: ExperimentSummary[];
  total: number;
}

export interface ExperimentResultsResponse {
  results: ExperimentDetailedResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExperimentCreateResponse {
  id: string;
  status: string;
  dataset: string;
  config: ExperimentConfig;
  created_at: string;
  total_samples: number;
}

export interface ConfigResponse {
  llm: {
    model: string;
    temperature: number;
    max_tokens: number;
  };
  correction: {
    max_rounds: number;
    semantic_threshold: number;
  };
  available_models: string[];
  available_datasets: Array<{ id: string; label: string; dev_count: number }>;
}

// ============================================================
// WebSocket message types
// ============================================================

export interface WsProgressMessage {
  type: 'progress';
  current: number;
  total: number;
  status: string;
  current_item: {
    index: number;
    db_id: string;
    question: string;
    correct: boolean;
    latency: number;
    correction_rounds: number;
  };
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

export interface WsLogMessage {
  type: 'log';
  entry: LogEntry;
}

export interface WsCompletedMessage {
  type: 'completed';
  metrics: ExperimentMetrics;
}

export interface WsErrorMessage {
  type: 'error';
  message: string;
}

export type WsMessage =
  | WsProgressMessage
  | WsLogMessage
  | WsCompletedMessage
  | WsErrorMessage;

// ============================================================
// Chart data
// ============================================================

export interface ChartDataPoint {
  label: string;
  value: number;
}
