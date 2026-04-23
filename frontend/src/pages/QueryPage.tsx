import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Typography,
  Select,
  Tag,
  Space,
  Alert,
  Button,
  Tooltip,
} from 'antd';
import {
  CheckCircleFilled,
  ThunderboltFilled,
  DatabaseOutlined,
  RobotOutlined,
  CodeOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  BranchesOutlined,
  SyncOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useDatabases } from '../hooks/useApi';
import { streamQuery } from '../hooks/useApi';
import QueryInput from '../components/query/QueryInput';
import ResultTable from '../components/query/ResultTable';
import SqlDisplay from '../components/query/SqlDisplay';
import SchemaContextDisplay from '../components/query/SchemaContextDisplay';
import PipelineVisualizer from '../components/query/PipelineVisualizer';
import type { QueryResult, StreamState, PipelineStage } from '../types';
import { initialStreamState } from '../types';

// ── 예시 질문 ──────────────────────────────────────────────────
const EXAMPLE_QUESTIONS = [
  '부서별 평균 급여를 알려줘',
  '올해 입사한 직원 목록',
  '직책별 인원 현황',
  '가장 최근에 입사한 직원 5명',
  '부서별 퇴사율 추이',
];

// ── 타입 ───────────────────────────────────────────────────────
interface ChatEntry {
  id: string;
  question: string;
  stream: StreamState;
  isLoading: boolean;
  error: string | null;
}

// ── PipelineStage → PipelineVisualizer currentStep 변환 ────────
function stageToStep(stage: PipelineStage | null): number {
  switch (stage) {
    case 'schema_link':  return 1;
    case 'sql_generating': return 2;
    case 'validating':   return 3;
    case 'verifying':    return 4;
    case 'correcting':   return 3; // 교정 후 검증 재진입
    case 'explaining':   return 4;
    default:             return 1;
  }
}

// ── 단계 한국어 설명 ────────────────────────────────────────────
const STAGE_LABEL: Record<string, string> = {
  schema_link:   '관련 테이블 탐색 중...',
  sql_generating:'SQL 생성 중...',
  validating:    '실행 검증 중...',
  verifying:     '의미 검증(NLI) 중...',
  correcting:    'SQL 교정 중...',
  explaining:    '결과 설명 생성 중...',
};

// ── 공용 스타일 ────────────────────────────────────────────────
const avatarStyle: React.CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: '50%',
  background: '#f0f5ff',
  border: '1px solid #d6e4ff',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
  color: '#1677ff',
};

// ── 사용자 말풍선 ──────────────────────────────────────────────
function UserBubble({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
      <div
        style={{
          maxWidth: '72%',
          background: '#1677ff',
          color: '#fff',
          borderRadius: '18px 18px 4px 18px',
          padding: '10px 16px',
          fontSize: 14,
          lineHeight: 1.65,
          wordBreak: 'break-word',
          boxShadow: '0 1px 3px rgba(22,119,255,0.2)',
        }}
      >
        {text}
      </div>
    </div>
  );
}

// ── 스트리밍 중 말풍선 (실제 파이프라인 진행 반영) ────────────
function StreamingBubble({ stream }: { stream: StreamState }) {
  const step = stageToStep(stream.stage);
  const stageLabel = stream.stage ? STAGE_LABEL[stream.stage] : '파이프라인 준비 중...';

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 18 }}>
      <div style={avatarStyle}>
        <RobotOutlined style={{ fontSize: 14 }} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 파이프라인 단계 (실제 진행 기반) */}
        <div style={{ width: 260, marginBottom: 10 }}>
          <PipelineVisualizer currentStep={step} isLoading={true} />
        </div>

        {/* 현재 단계 텍스트 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginBottom: 10,
            color: '#8c8c8c',
            fontSize: 12,
          }}
        >
          <LoadingOutlined style={{ color: '#1677ff' }} />
          <span>{stageLabel}</span>
        </div>

        {/* SQL (생성되는 순간부터 표시) */}
        {stream.sql && (
          <div style={{ marginBottom: 10 }}>
            <SqlDisplay sql={stream.sql} label="생성된 SQL" />
          </div>
        )}

        {/* 실행 검증 결과 */}
        {stream.validation && (
          <div style={{ marginBottom: 6 }}>
            <Tag color={stream.validation.success ? 'green' : 'red'} style={{ fontSize: 11 }}>
              실행 검증 {stream.validation.success ? '통과' : `실패: ${stream.validation.error_type}`}
            </Tag>
          </div>
        )}

        {/* 의미 검증 결과 */}
        {stream.verification && (
          <div style={{ marginBottom: 6 }}>
            <Tag
              color={stream.verification.is_consistent ? 'green' : 'orange'}
              style={{ fontSize: 11 }}
            >
              의도 일치 {(stream.verification.score * 100).toFixed(0)}%
            </Tag>
            {stream.verification.back_translation && (
              <Typography.Text
                type="secondary"
                style={{ fontSize: 11, display: 'block', marginTop: 2, fontStyle: 'italic' }}
              >
                "{stream.verification.back_translation}"
              </Typography.Text>
            )}
          </div>
        )}


        {/* 설명 (설명 단계에서 미리 표시) */}
        {stream.explanation && (
          <div
            style={{
              background: '#fff',
              borderRadius: '4px 18px 18px 18px',
              padding: '10px 14px',
              border: '1px solid #f0f0f0',
              fontSize: 13,
              lineHeight: 1.7,
              color: '#595959',
              fontStyle: 'italic',
            }}
          >
            {stream.explanation}
          </div>
        )}
      </div>
    </div>
  );
}

// ── 파이프라인 단계 결과 요약 ──────────────────────────────────
function PipelineSummaryBar({ result }: { result: QueryResult }) {
  const tableCount = result.schema_context?.tables?.length ?? 0;
  const confidence = result.sql_confidence;
  const validation = result.validation;
  const verification = result.verification;
  const correctionCount = result.correction_steps.length;

  type StageStatus = 'success' | 'error' | 'warning';

  interface Stage {
    icon: React.ComponentType<{ style?: React.CSSProperties; spin?: boolean }>;
    label: string;
    detail: string;
    status: StageStatus;
  }

  const stages: Stage[] = [
    {
      icon: DatabaseOutlined,
      label: 'Schema Link',
      detail: tableCount > 0 ? `${tableCount}개 테이블` : '완료',
      status: 'success',
    },
    {
      icon: CodeOutlined,
      label: 'SQL 생성',
      detail: confidence != null ? `신뢰도 ${(confidence * 100).toFixed(0)}%` : '완료',
      status: 'success',
    },
    {
      icon: PlayCircleOutlined,
      label: '실행 검증',
      detail: validation?.success ? '통과' : (validation?.error_type ?? '실패'),
      status: validation?.success ? 'success' : 'error',
    },
    {
      icon: BranchesOutlined,
      label: '의미 검증',
      detail: verification
        ? `${(verification.similarity_score * 100).toFixed(0)}% 일치`
        : '완료',
      status: verification?.is_consistent ? 'success' : 'warning',
    },
    ...(correctionCount > 0
      ? [
          {
            icon: SyncOutlined,
            label: '자기교정',
            detail: `${correctionCount}회 교정`,
            status: 'warning' as StageStatus,
          },
        ]
      : []),
  ];

  const statusColor: Record<StageStatus, string> = {
    success: '#52c41a',
    error: '#ff4d4f',
    warning: '#fa8c16',
  };
  const statusBg: Record<StageStatus, string> = {
    success: '#f6ffed',
    error: '#fff2f0',
    warning: '#fff7e6',
  };

  return (
    <div
      style={{
        background: '#fafafa',
        borderRadius: 8,
        padding: '8px 12px',
        border: '1px solid #f0f0f0',
        marginBottom: 10,
      }}
    >
      <Typography.Text
        type="secondary"
        style={{
          fontSize: 10,
          display: 'block',
          marginBottom: 8,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        파이프라인 실행 결과
      </Typography.Text>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
        {stages.map((stage, idx) => {
          const color = statusColor[stage.status];
          const bg = statusBg[stage.status];
          const Icon = stage.icon;
          return (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div
                style={{
                  background: bg,
                  border: `1px solid ${color}44`,
                  borderRadius: 6,
                  padding: '3px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                <Icon style={{ fontSize: 11, color }} />
                <div>
                  <Typography.Text
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#262626',
                      display: 'block',
                      lineHeight: 1.3,
                    }}
                  >
                    {stage.label}
                  </Typography.Text>
                  <Typography.Text
                    style={{ fontSize: 10, color: '#8c8c8c', display: 'block', lineHeight: 1.3 }}
                  >
                    {stage.detail}
                  </Typography.Text>
                </div>
              </div>
              {idx < stages.length - 1 && (
                <span style={{ color: '#bfbfbf', fontSize: 12 }}>›</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 완료된 응답 카드 ───────────────────────────────────────────
function ResultBubble({ result }: { result: QueryResult }) {
  const r = result;
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* Phase 3: Guardrails 경고 */}
      {r.guardrails?.low_confidence_warning && (
        <Alert
          type="warning"
          showIcon
          message="낮은 신뢰도 경고"
          description={r.guardrails.warning_message}
          style={{ marginBottom: 10, borderRadius: '4px 12px 12px 12px', fontSize: 12 }}
        />
      )}
      {r.guardrails?.rows_truncated && (
        <Alert
          type="info"
          showIcon
          message={`결과가 1,000행으로 제한됨 (전체 ${r.guardrails.original_row_count.toLocaleString()}행)`}
          style={{ marginBottom: 8, borderRadius: '4px 12px 12px 12px', fontSize: 12 }}
        />
      )}

      {/* 자연어 설명 */}
      {r.explanation && (
        <div
          style={{
            background: '#fff',
            borderRadius: '4px 18px 18px 18px',
            padding: '12px 16px',
            border: '1px solid #f0f0f0',
            marginBottom: 10,
            fontSize: 14,
            lineHeight: 1.75,
            color: '#262626',
            boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
          }}
        >
          {r.explanation}
        </div>
      )}

      {/* 파이프라인 실행 결과 요약 */}
      <PipelineSummaryBar result={r} />

      {/* 생성된 SQL (항상 표시) */}
      <div style={{ marginBottom: 10 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <SqlDisplay sql={r.original_sql} label="생성된 SQL" />
          {r.was_corrected && (
            <SqlDisplay sql={r.final_sql} label="최종 SQL (교정됨)" corrected />
          )}
          <SchemaContextDisplay schema={r.schema_context} />
        </Space>
      </div>


      {/* 결과 테이블 */}
      {r.result.columns.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <ResultTable
            columns={r.result.columns}
            rows={r.result.rows}
            title="조회 결과"
            maxRows={1000}
          />
        </div>
      )}

      {/* 메타데이터 태그 */}
      <Space size={4} wrap style={{ marginBottom: 4 }}>
        <Tag style={{ fontSize: 11 }}>{r.result.rows.length.toLocaleString()}행</Tag>
        <Tag style={{ fontSize: 11 }}>{r.latency.toFixed(1)}s</Tag>
        {r.was_corrected ? (
          <Tag icon={<CheckCircleFilled />} color="orange" style={{ fontSize: 11 }}>
            교정 완료
          </Tag>
        ) : (
          <Tag icon={<ThunderboltFilled />} color="blue" style={{ fontSize: 11 }}>
            즉시 생성
          </Tag>
        )}
        {r.verification && (
          <Tag
            color={r.verification.is_consistent ? 'green' : 'volcano'}
            style={{ fontSize: 11 }}
          >
            의도 일치 {(r.verification.similarity_score * 100).toFixed(0)}%
          </Tag>
        )}
      </Space>
    </div>
  );
}

// ── 어시스턴트 말풍선 (스트리밍/완료 통합) ────────────────────
function AssistantBubble({ entry }: { entry: ChatEntry }) {
  if (entry.error) {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 18 }}>
        <div style={avatarStyle}>
          <RobotOutlined style={{ fontSize: 14 }} />
        </div>
        <Alert
          message="오류가 발생했습니다"
          description={entry.error}
          type="error"
          showIcon
          style={{ flex: 1, borderRadius: '4px 12px 12px 12px', fontSize: 13 }}
        />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 22 }}>
      <div style={avatarStyle}>
        <RobotOutlined style={{ fontSize: 14 }} />
      </div>

      {/* 스트리밍 중: StreamingBubble / 완료: ResultBubble */}
      {entry.isLoading || entry.stream.finalResult === null ? (
        <StreamingBubble stream={entry.stream} />
      ) : (
        <ResultBubble result={entry.stream.finalResult} />
      )}
    </div>
  );
}

// ── 메인 페이지 ────────────────────────────────────────────────
export default function QueryPage() {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [inputText, setInputText] = useState('');
  const [selectedDb, setSelectedDb] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRefs = useRef<Map<string, AbortController>>(new Map());

  const { data: dbData, isLoading: dbLoading } = useDatabases();

  // DB 목록 로드 후 첫 번째 DB 자동 선택
  useEffect(() => {
    if (dbData?.databases.length && !selectedDb) {
      setSelectedDb(dbData.databases[0].id);
    }
  }, [dbData, selectedDb]);

  // 새 메시지 추가 시 스크롤
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  const isAnyLoading = entries.some((e) => e.isLoading);

  // ── 스트림 이벤트 → StreamState 업데이트 ─────────────────────
  const updateStream = useCallback(
    (id: string, updater: (prev: StreamState) => StreamState) => {
      setEntries((prev) =>
        prev.map((e) => (e.id === id ? { ...e, stream: updater(e.stream) } : e)),
      );
    },
    [],
  );

  const handleSubmit = () => {
    if (!inputText.trim() || !selectedDb || isAnyLoading) return;

    const id = crypto.randomUUID();
    const question = inputText.trim();

    // 멀티턴 히스토리 (최근 3턴 성공 턴)
    const history = entries
      .filter((e) => e.stream.finalResult !== null && !e.error)
      .slice(-3)
      .map((e) => ({
        question: e.question,
        sql: e.stream.finalResult!.final_sql,
        explanation: e.stream.finalResult!.explanation,
      }));

    setEntries((prev) => [
      ...prev,
      { id, question, stream: initialStreamState(), isLoading: true, error: null },
    ]);
    setInputText('');

    const abortController = new AbortController();
    abortRefs.current.set(id, abortController);

    streamQuery(
      {
        query: question,
        db_id: selectedDb,
        dataset: dbData?.databases.find((d) => d.id === selectedDb)?.dataset || 'hrdb',
        conversation_history: history,
      },
      (event, data) => {
        const d = data as Record<string, unknown>;
        switch (event) {
          case 'step':
            updateStream(id, (s) => ({ ...s, stage: d.stage as StreamState['stage'] }));
            break;
          case 'sql_generated':
            updateStream(id, (s) => ({
              ...s,
              sql: d.sql as string,
              confidence: d.confidence as number,
            }));
            break;
          case 'validated':
            updateStream(id, (s) => ({
              ...s,
              validation: {
                success: d.success as boolean,
                error_type: (d.error_type as string | null) ?? null,
              },
            }));
            break;
          case 'verified':
            updateStream(id, (s) => ({
              ...s,
              verification: {
                score: d.score as number,
                is_consistent: d.is_consistent as boolean,
                back_translation: (d.back_translation as string) || '',
              },
            }));
            break;
          case 'corrected':
            updateStream(id, (s) => ({
              ...s,
              correctionSteps: [
                ...s.correctionSteps,
                {
                  round: d.round as number,
                  error_type: d.error_type as string,
                  original_sql: d.original_sql as string,
                  corrected_sql: d.corrected_sql as string,
                  validation_success: d.validation_success as boolean,
                  semantic_score: d.semantic_score as number,
                },
              ],
            }));
            break;
          case 'explanation':
            updateStream(id, (s) => ({ ...s, explanation: d.text as string }));
            break;
          case 'result':
            setEntries((prev) =>
              prev.map((e) =>
                e.id === id
                  ? {
                      ...e,
                      isLoading: false,
                      stream: { ...e.stream, finalResult: d as unknown as QueryResult },
                    }
                  : e,
              ),
            );
            break;
          case 'error':
            setEntries((prev) =>
              prev.map((e) =>
                e.id === id
                  ? { ...e, isLoading: false, error: (d.message as string) || '알 수 없는 오류' }
                  : e,
              ),
            );
            break;
        }
      },
      abortController.signal,
    )
      .catch((err: Error) => {
        if (err.name === 'AbortError') return;
        setEntries((prev) =>
          prev.map((e) =>
            e.id === id ? { ...e, isLoading: false, error: err.message } : e,
          ),
        );
      })
      .finally(() => {
        abortRefs.current.delete(id);
        // 스트림이 끝났는데 finalResult가 없으면 isLoading 해제
        setEntries((prev) =>
          prev.map((e) =>
            e.id === id && e.isLoading ? { ...e, isLoading: false } : e,
          ),
        );
      });
  };

  const handleClearHistory = () => {
    // 진행 중인 스트림 모두 중단
    abortRefs.current.forEach((ctrl) => ctrl.abort());
    abortRefs.current.clear();
    setEntries([]);
  };

  return (
    <div
      style={{
        height: 'calc(100vh - 112px)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        borderRadius: 10,
        background: '#f7f8fa',
        border: '1px solid #e8e8e8',
        boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
      }}
    >
      {/* ── 상단 헤더: DB 선택 ── */}
      <div
        style={{
          padding: '10px 18px',
          borderBottom: '1px solid #ebebeb',
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexShrink: 0,
        }}
      >
        <RobotOutlined style={{ color: '#1677ff', fontSize: 16 }} />
        <Typography.Text style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>
          자연어 데이터 조회
        </Typography.Text>
        <DatabaseOutlined style={{ color: '#8c8c8c', fontSize: 13 }} />
        <Select
          value={selectedDb || undefined}
          onChange={setSelectedDb}
          loading={dbLoading}
          placeholder="데이터베이스 선택"
          style={{ width: 200 }}
          size="small"
          options={dbData?.databases.map((db) => ({
            value: db.id,
            label: `${db.id}  (${db.table_count}개 테이블)`,
          }))}
        />
        {entries.length > 0 && (
          <Tooltip title="대화 초기화">
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              onClick={handleClearHistory}
              style={{ color: '#bfbfbf' }}
            />
          </Tooltip>
        )}
      </div>

      {/* ── 채팅 영역 ── */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 28px',
          scrollBehavior: 'smooth',
        }}
      >
        {/* 빈 상태: 예시 질문 */}
        {entries.length === 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 18,
              userSelect: 'none',
            }}
          >
            <RobotOutlined style={{ fontSize: 44, color: '#c8d8f8' }} />
            <Typography.Text
              type="secondary"
              style={{ fontSize: 15, textAlign: 'center' }}
            >
              자연어로 데이터베이스에 질문하세요
            </Typography.Text>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 8,
                justifyContent: 'center',
                maxWidth: 520,
              }}
            >
              {EXAMPLE_QUESTIONS.map((q) => (
                <Tag
                  key={q}
                  style={{
                    cursor: 'pointer',
                    borderRadius: 14,
                    padding: '5px 14px',
                    fontSize: 13,
                    border: '1px solid #d6e4ff',
                    background: '#f0f5ff',
                    color: '#1677ff',
                    transition: 'all 0.15s',
                  }}
                  onClick={() => setInputText(q)}
                >
                  {q}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* 메시지 목록 */}
        {entries.map((entry) => (
          <div key={entry.id}>
            <UserBubble text={entry.question} />
            <AssistantBubble entry={entry} />
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* ── 입력 영역 ── */}
      <div
        style={{
          padding: '12px 18px 14px',
          borderTop: '1px solid #ebebeb',
          background: '#fff',
          flexShrink: 0,
        }}
      >
        <QueryInput
          value={inputText}
          onChange={setInputText}
          onSubmit={handleSubmit}
          isLoading={isAnyLoading}
        />
      </div>
    </div>
  );
}
