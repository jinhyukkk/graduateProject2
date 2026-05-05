import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
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
  TeamOutlined,
  DollarOutlined,
  ApartmentOutlined,
  CalendarOutlined,
  BarChartOutlined,
  BulbOutlined,
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

// ── 페르소나 기반 예시 질문 (HRDB 시나리오: 인사 담당자가 실제로 묻는 것) ──
interface ExampleCategory {
  key: string;
  label: string;
  icon: React.ComponentType<{ style?: React.CSSProperties }>;
  color: string;
  questions: string[];
}

const HRDB_EXAMPLES: ExampleCategory[] = [
  {
    key: 'workforce',
    label: '인력 현황',
    icon: TeamOutlined,
    color: '#1677ff',
    questions: [
      '재직 중인 전체 직원 수를 알려줘',
      '이번 달 신규 입사자 명단',
      '직급별 인원 분포를 보여줘',
      '여성 직원 비율은?',
    ],
  },
  {
    key: 'org',
    label: '조직',
    icon: ApartmentOutlined,
    color: '#52c41a',
    questions: [
      '개발1팀 소속 직원 명단',
      '부서별 인원수 상위 5개',
      '팀장 직책을 맡은 직원 목록',
      '본부별 평균 근속연수',
    ],
  },
  {
    key: 'comp',
    label: '급여·보상',
    icon: DollarOutlined,
    color: '#fa8c16',
    questions: [
      '부서별 평균 급여를 알려줘',
      '가장 최근 급여 지급월은 언제야?',
      '직급별 평균 연봉을 비교해줘',
      '올해 성과급 지급 대상자 수',
    ],
  },
  {
    key: 'attendance',
    label: '근태·휴가',
    icon: CalendarOutlined,
    color: '#722ed1',
    questions: [
      '이번 주 휴가 신청자 명단',
      '연차 잔여일이 5일 미만인 직원',
      '지난달 평균 근무시간',
      '재택근무 신청 건수 추이',
    ],
  },
  {
    key: 'analytics',
    label: '분석',
    icon: BarChartOutlined,
    color: '#13c2c2',
    questions: [
      '부서별 퇴사율 추이',
      '근속연수 5년 이상 직원 수',
      '연도별 신규 입사자 추이',
      '직급별 평균 재직 기간',
    ],
  },
];

const BIRD_EXAMPLES: ExampleCategory[] = [
  {
    key: 'general',
    label: '일반 조회',
    icon: BulbOutlined,
    color: '#1677ff',
    questions: [
      'List the top 10 records',
      'Show distinct categories',
      'Count rows by group',
    ],
  },
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

// ── CoT 추론 카드 (LLM 토큰 단위 점진 표시) ───────────────────
function ReasoningCard({ text, streaming }: { text: string; streaming: boolean }) {
  // 체크리스트 항목(- **Intent**: ...)을 라인 단위로 살짝 강조
  // 굵게 처리한 부분(**...**)을 styled span으로 변환
  const renderInline = (line: string) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <span key={i} style={{ fontWeight: 600, color: '#262626' }}>
            {part.slice(2, -2)}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  // 펜스 코드 블록(```...```)은 SQL/JSON이 추론 패널에 새는 것을 막기 위해 제거한다.
  // 백엔드 chat_completion_streaming이 1차 가드를 하지만, 비스트리밍 경로 안전망을 둔다.
  // 닫히지 않은 마지막 펜스도 함께 잘라낸다.
  const cleaned = text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/```[\s\S]*$/, '')
    .trimEnd();

  return (
    <div
      style={{
        background: 'linear-gradient(180deg, #f9fbff 0%, #f3f6fc 100%)',
        border: '1px solid #d9e6ff',
        borderRadius: 10,
        padding: '10px 14px',
        marginBottom: 10,
        fontSize: 12.5,
        lineHeight: 1.65,
        color: '#3a4150',
        fontFamily:
          '"Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.6), 0 1px 3px rgba(31,78,182,0.05)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 6,
          fontSize: 11,
          fontWeight: 600,
          color: '#1f4eb6',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        <BulbOutlined style={{ fontSize: 12 }} />
        추론 과정 {streaming ? '(생성 중...)' : ''}
      </div>
      {cleaned.split('\n').map((line, idx, arr) => (
        <div key={idx} style={{ minHeight: 18 }}>
          {renderInline(line)}
          {streaming && idx === arr.length - 1 && (
            <span
              style={{
                display: 'inline-block',
                width: 6,
                height: 12,
                background: '#1677ff',
                marginLeft: 2,
                verticalAlign: 'middle',
                animation: 'reasoning-cursor 1s steps(2) infinite',
              }}
            />
          )}
        </div>
      ))}
      <style>{`
        @keyframes reasoning-cursor {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}


// ── 시연 안내 카드 (첫 화면 — 5층 기여 한눈 요약) ──────────────
// 심사위원이 시연 시작 전 본 시스템의 학술적 위치를 즉시 파악하도록 한다.
function WelcomeCard() {
  const [collapsed, setCollapsed] = useState(false);
  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        style={{
          background: '#f5f9ff',
          border: '1px dashed #91caff',
          borderRadius: 8,
          padding: '6px 12px',
          fontSize: 11,
          color: '#1f4eb6',
          cursor: 'pointer',
          marginBottom: 12,
        }}
      >
        <BulbOutlined /> 시연 안내 다시 보기
      </button>
    );
  }
  return (
    <div
      style={{
        background: 'linear-gradient(180deg, #f0f7ff 0%, #fafcff 100%)',
        border: '1px solid #d6e4ff',
        borderRadius: 12,
        padding: '14px 18px',
        marginBottom: 16,
        position: 'relative',
      }}
    >
      <button
        onClick={() => setCollapsed(true)}
        style={{
          position: 'absolute',
          top: 8,
          right: 10,
          background: 'transparent',
          border: 'none',
          fontSize: 16,
          color: '#999',
          cursor: 'pointer',
          padding: 0,
        }}
        title="접기"
      >
        ×
      </button>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#1f4eb6', marginBottom: 6 }}>
        HR Data Assistant — 비전공자가 자연어로 사내 데이터에 접근
      </div>
      <div style={{ fontSize: 12, color: '#555', lineHeight: 1.6, marginBottom: 10 }}>
        본 시스템은 한국IT서비스학회 투고 논문의 시연 시스템입니다. 심사위원께서는
        아래 5계층 기여가 화면에서 어떻게 작동하는지 직접 확인하실 수 있습니다.
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {[
          { num: '1', label: '응용 시스템', desc: '비전공자 SQL 접근', color: '#1677ff' },
          { num: '2', label: '의도 검증', desc: 'NLI 의미 일치 진단', color: '#fa541c' },
          { num: '3', label: '한국 도메인', desc: '4축 비대칭 처리', color: '#52c41a' },
          { num: '4', label: 'Self-Consistency', desc: 'k=5 다수결', color: '#722ed1' },
          { num: '5', label: '운영 가이드라인', desc: 'EIED=68.1%', color: '#13c2c2' },
        ].map((c) => (
          <div
            key={c.num}
            style={{
              flex: '1 1 140px',
              minWidth: 140,
              background: '#fff',
              border: `1px solid ${c.color}40`,
              borderLeft: `3px solid ${c.color}`,
              borderRadius: 6,
              padding: '6px 10px',
            }}
          >
            <div style={{ fontSize: 10, color: c.color, fontWeight: 700 }}>
              기여 {c.num}
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#333', marginTop: 2 }}>
              {c.label}
            </div>
            <div style={{ fontSize: 10.5, color: '#888', marginTop: 1 }}>
              {c.desc}
            </div>
          </div>
        ))}
      </div>
      <div
        style={{
          marginTop: 10,
          fontSize: 11,
          color: '#666',
          background: '#fff',
          padding: '6px 10px',
          borderRadius: 6,
          border: '1px dashed #d9d9d9',
        }}
      >
        <strong style={{ color: '#fa541c' }}>★ 핵심 발견:</strong> NLI 의도 일치 검증을
        <em> 교정 트리거</em>가 아닌 <em>독립 진단 축</em>으로 운영하면 실행 검증의
        사각지대(EX=0임에도 통과한 쿼리) 중 <strong>68.1%(EIED)</strong>를 단독 탐지합니다.
        화면 우상단 <strong>★ 사각지대</strong> 마커로 직접 확인하실 수 있습니다.
      </div>
    </div>
  );
}

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

        {/* CoT 추론 과정 (SQL 생성 LLM이 점진적으로 흘려보내는 reasoning) */}
        {stream.reasoning && (
          <ReasoningCard text={stream.reasoning} streaming={!stream.sql} />
        )}

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

        {/* 진행 중 재시도 인라인 표시 — 라운드 발생 즉시 노출 */}
        {stream.correctionSteps && stream.correctionSteps.length > 0 && (
          <div
            style={{
              background: '#fff7e6',
              border: '1px dashed #ffd591',
              borderLeft: '3px solid #fa8c16',
              borderRadius: 6,
              padding: '6px 10px',
              marginBottom: 8,
              fontSize: 11.5,
              color: '#7a3d18',
            }}
          >
            <SyncOutlined spin style={{ marginRight: 6, color: '#fa8c16' }} />
            <strong>재시도 진행 중</strong> — 지금까지 {stream.correctionSteps.length}회 시도.
            마지막 시도에서 <em>{stream.correctionSteps[stream.correctionSteps.length - 1].error_type}</em>
            를 감지해 다시 생성하고 있습니다…
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
function ResultBubble({ result, reasoning }: { result: QueryResult; reasoning: string }) {
  const r = result;
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      {/* CoT 추론 과정 (완료 후엔 접혀 있음) */}
      <ReasoningCollapsed text={reasoning} />

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
        <div style={{ marginBottom: 10 }}>
          <ResultTable
            columns={r.result.columns}
            rows={r.result.rows}
            title="조회 결과"
            maxRows={1000}
          />
        </div>
      )}

      {/* 자연어 설명 — 최종 답변 (조회 결과 아래) */}
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

// ── 완료 후 추론 과정 collapsible (선택 표시) ──────────────────
function ReasoningCollapsed({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const cleaned = text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/```[\s\S]*$/, '')
    .trimEnd();
  if (!cleaned) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          background: 'transparent',
          border: '1px dashed #d9e6ff',
          borderRadius: 8,
          padding: '5px 12px',
          fontSize: 11,
          color: '#1f4eb6',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <BulbOutlined style={{ fontSize: 11 }} />
        추론 과정 {open ? '닫기' : '보기'}
      </button>
      {open && <div style={{ marginTop: 6 }}><ReasoningCard text={cleaned} streaming={false} /></div>}
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
        <ResultBubble
          result={entry.stream.finalResult}
          reasoning={entry.stream.reasoning}
        />
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

  // 선택된 DB의 dataset에 따라 페르소나 예시 카테고리 분기
  const exampleCategories = useMemo<ExampleCategory[]>(() => {
    const dataset = dbData?.databases.find((d) => d.id === selectedDb)?.dataset;
    if (dataset === 'bird') return BIRD_EXAMPLES;
    return HRDB_EXAMPLES; // hrdb 기본
  }, [dbData, selectedDb]);

  const [activeCategory, setActiveCategory] = useState<string>(exampleCategories[0].key);

  useEffect(() => {
    setActiveCategory(exampleCategories[0].key);
  }, [exampleCategories]);

  const activeCategoryQuestions = useMemo(
    () =>
      exampleCategories.find((c) => c.key === activeCategory)?.questions ??
      exampleCategories[0].questions,
    [exampleCategories, activeCategory],
  );

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
          case 'reasoning_chunk':
            updateStream(id, (s) => ({
              ...s,
              reasoning: s.reasoning + (d.text as string),
            }));
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
      {/* ── 상단 헤더: 데모 안내 + DB 선택 ── */}
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
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #1f4eb6, #1677ff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            flexShrink: 0,
          }}
        >
          <RobotOutlined style={{ fontSize: 14 }} />
        </div>
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <Typography.Text style={{ fontSize: 13, fontWeight: 600, display: 'block' }}>
            대화형 데이터 조회
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>
            자연어로 질문하면 사내 DB에서 답을 찾아 표·요약으로 보여드립니다
          </Typography.Text>
        </div>
        <Tag color="green" style={{ fontSize: 11, marginRight: 0 }}>
          온라인
        </Tag>
        <DatabaseOutlined style={{ color: '#8c8c8c', fontSize: 13 }} />
        <Select
          value={selectedDb || undefined}
          onChange={setSelectedDb}
          loading={dbLoading}
          placeholder="데이터베이스 선택"
          style={{ width: 220 }}
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
        {/* 빈 상태: 시연 안내 + 페르소나 카테고리 + 예시 질문 그리드 */}
        {entries.length === 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'stretch',
              justifyContent: 'flex-start',
              minHeight: '100%',
              gap: 22,
              padding: '12px 4px',
              userSelect: 'none',
            }}
          >
            {/* 시연 안내 카드 — 5계층 기여 한눈 요약 */}
            <WelcomeCard />

            {/* 인사말 */}
            <div style={{ textAlign: 'center' }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #e6f0ff, #d6e4ff)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 12px',
                }}
              >
                <RobotOutlined style={{ fontSize: 24, color: '#1f4eb6' }} />
              </div>
              <Typography.Title level={4} style={{ margin: 0, color: '#1f1f1f', fontWeight: 600 }}>
                무엇을 알아볼까요?
              </Typography.Title>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                자연어로 질문하면 사내 데이터베이스에서 바로 답을 찾아드려요. SQL 작성은 필요 없습니다.
              </Typography.Text>
            </div>

            {/* 카테고리 탭 */}
            <div
              style={{
                display: 'flex',
                gap: 6,
                flexWrap: 'wrap',
                justifyContent: 'center',
                maxWidth: 720,
              }}
            >
              {exampleCategories.map((cat) => {
                const Icon = cat.icon;
                const active = cat.key === activeCategory;
                return (
                  <button
                    key={cat.key}
                    onClick={() => setActiveCategory(cat.key)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '7px 14px',
                      borderRadius: 18,
                      border: `1px solid ${active ? cat.color : '#e8e8e8'}`,
                      background: active ? `${cat.color}14` : '#fff',
                      color: active ? cat.color : '#595959',
                      fontSize: 13,
                      fontWeight: active ? 600 : 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    <Icon style={{ fontSize: 13 }} />
                    {cat.label}
                  </button>
                );
              })}
            </div>

            {/* 예시 질문 카드 그리드 */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                gap: 10,
                width: '100%',
                maxWidth: 720,
              }}
            >
              {activeCategoryQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => setInputText(q)}
                  style={{
                    textAlign: 'left',
                    padding: '12px 14px',
                    background: '#fff',
                    border: '1px solid #ececec',
                    borderRadius: 10,
                    cursor: 'pointer',
                    fontSize: 13,
                    color: '#262626',
                    lineHeight: 1.5,
                    transition: 'all 0.15s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#1677ff';
                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(22,119,255,0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#ececec';
                    e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.02)';
                  }}
                >
                  <BulbOutlined style={{ color: '#1677ff', fontSize: 13, flexShrink: 0 }} />
                  <span>{q}</span>
                </button>
              ))}
            </div>

            {/* 안전성 안내 */}
            <div
              style={{
                marginTop: 8,
                fontSize: 11,
                color: '#8c8c8c',
                textAlign: 'center',
                maxWidth: 560,
              }}
            >
              · 의도 일치 검증(NLI)으로 잘못된 SQL을 자동 진단합니다 · 대용량 결과는 1,000행으로 제한됩니다 · 본 데모의 인사 데이터는 합성 데이터입니다
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
