import { Timeline, Tag, Typography, Space, Empty } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { CorrectionStep } from '../../types';
import SqlDisplay from '../query/SqlDisplay';

interface CorrectionStepperProps {
  steps: CorrectionStep[];
}

const ERROR_TYPE_COLOR: Record<string, string> = {
  schema: 'volcano',
  join: 'orange',
  aggregation: 'gold',
  condition: 'cyan',
  logic: 'purple',
};

export default function CorrectionStepper({ steps }: CorrectionStepperProps) {
  if (!steps.length) {
    return (
      <Empty
        description={
          <Typography.Text type="secondary">
            교정 없음 — 첫 번째 생성에서 올바른 SQL을 반환했습니다
          </Typography.Text>
        }
        style={{ padding: 48 }}
      />
    );
  }

  const items = steps.map((step) => ({
    color: step.validation_success ? 'green' : 'red',
    dot: step.validation_success ? (
      <CheckCircleOutlined style={{ fontSize: 14, color: '#52c41a' }} />
    ) : (
      <CloseCircleOutlined style={{ fontSize: 14, color: '#ff4d4f' }} />
    ),
    children: (
      <div style={{ paddingBottom: 20 }}>
        <Space size={6} wrap style={{ marginBottom: 10 }}>
          <Typography.Text strong style={{ fontSize: 13 }}>
            Round {step.round}
          </Typography.Text>
          <Tag
            color={ERROR_TYPE_COLOR[step.error_type?.toLowerCase()] ?? 'default'}
            style={{ margin: 0 }}
          >
            {step.error_type}
          </Tag>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            의도 일치 {(step.semantic_score * 100).toFixed(0)}%
          </Typography.Text>
          {step.validation_success ? (
            <Tag color="success" style={{ margin: 0 }}>교정 성공</Tag>
          ) : (
            <Tag color="error" style={{ margin: 0 }}>교정 실패</Tag>
          )}
        </Space>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
              교정 전
            </Typography.Text>
            <SqlDisplay sql={step.original_sql} label="Before" />
          </div>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
              교정 후
            </Typography.Text>
            <SqlDisplay sql={step.corrected_sql} label="After" corrected />
          </div>
        </div>
      </div>
    ),
  }));

  return (
    <div style={{ padding: '8px 4px' }}>
      <Timeline items={items} />
    </div>
  );
}
