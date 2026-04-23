import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Card,
  Tag,
  Row,
  Col,
  Button,
  Spin,
  Alert,
  Descriptions,
  Space,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useExperimentQueryDetail } from '../hooks/useApi';
import SqlDisplay from '../components/query/SqlDisplay';
import ResultTable from '../components/query/ResultTable';
import CorrectionStepper from '../components/correction/CorrectionStepper';

export default function QueryDetailPage() {
  const { id: expId, qid } = useParams<{ id: string; qid: string }>();
  const navigate = useNavigate();

  const {
    data: detail,
    isLoading,
    error,
  } = useExperimentQueryDetail(expId || null, qid ? Number(qid) : null);

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="Failed to load query detail"
        description={String(error)}
        type="error"
        showIcon
      />
    );
  }

  if (!detail) return null;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(`/results/${expId}`)}
        style={{ marginBottom: 16 }}
      >
        Back to Results
      </Button>

      {/* Query Info */}
      <Card title="Query Info" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="Question" span={2}>
            <Typography.Text strong>"{detail.question}"</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="Database">
            <Tag>{detail.db_id}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Status">
            {detail.correct ? (
              <Tag icon={<CheckCircleOutlined />} color="success">
                CORRECT
              </Tag>
            ) : (
              <Tag icon={<CloseCircleOutlined />} color="error">
                INCORRECT
              </Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Latency">
            {detail.latency.toFixed(1)}s
          </Descriptions.Item>
          <Descriptions.Item label="Correction Rounds">
            {detail.correction_rounds}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Gold vs Predicted SQL */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <SqlDisplay sql={detail.gold_sql} label="Gold SQL" />
        </Col>
        <Col span={12}>
          <SqlDisplay
            sql={detail.predicted_sql}
            label="Predicted SQL"
            corrected={detail.correction_rounds > 0}
          />
        </Col>
      </Row>

      {/* Correction History */}
      {detail.correction_history.length > 0 && (
        <Card size="small" title="Correction History" style={{ marginBottom: 16 }}>
          <CorrectionStepper steps={detail.correction_history} />
        </Card>
      )}

      {/* Validation & Verification */}
      {detail.final_validation && (
        <Card
          size="small"
          title="Final Validation & Verification"
          style={{ marginBottom: 16 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Descriptions size="small" column={1} title="Validation">
                <Descriptions.Item label="Success">
                  {detail.final_validation.success ? (
                    <Tag color="success">PASS</Tag>
                  ) : (
                    <Tag color="error">FAIL</Tag>
                  )}
                </Descriptions.Item>
                {detail.final_validation.error_type && (
                  <Descriptions.Item label="Error">
                    <Tag color="error">{detail.final_validation.error_type}</Tag>
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="Row Count">
                  {detail.final_validation.row_count}
                </Descriptions.Item>
                <Descriptions.Item label="Empty">
                  {detail.final_validation.is_empty ? 'Yes' : 'No'}
                </Descriptions.Item>
              </Descriptions>
            </Col>
            <Col span={12}>
              {detail.final_verification && (
                <Descriptions size="small" column={1} title="Verification">
                  <Descriptions.Item label="Back-Translation">
                    <Typography.Text italic>
                      "{detail.final_verification.back_translation}"
                    </Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="Similarity">
                    <Tag
                      color={
                        detail.final_verification.similarity_score >= 0.75
                          ? 'success'
                          : 'warning'
                      }
                    >
                      {detail.final_verification.similarity_score.toFixed(2)}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Consistent">
                    {detail.final_verification.is_consistent ? (
                      <Tag color="success">CONSISTENT</Tag>
                    ) : (
                      <Tag color="warning">MISMATCH</Tag>
                    )}
                  </Descriptions.Item>
                  {detail.final_verification.mismatch_diagnosis && (
                    <Descriptions.Item label="Diagnosis">
                      {detail.final_verification.mismatch_diagnosis}
                    </Descriptions.Item>
                  )}
                </Descriptions>
              )}
            </Col>
          </Row>
        </Card>
      )}

      {/* Final Result */}
      {detail.result && (
        <ResultTable
          columns={detail.result.columns}
          rows={detail.result.rows}
          title="Execution Result"
        />
      )}
    </div>
  );
}
