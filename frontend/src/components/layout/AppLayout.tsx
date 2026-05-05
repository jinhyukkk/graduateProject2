import React from 'react';
import { Layout, Menu, Typography, Avatar, Tag } from 'antd';
import {
  MessageOutlined,
  ExperimentOutlined,
  BarChartOutlined,
  SwapOutlined,
  UserOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <MessageOutlined />, label: '데이터 조회' },
  { key: '/experiment', icon: <ExperimentOutlined />, label: '실험 실행' },
  { key: '/results', icon: <BarChartOutlined />, label: '결과 분석' },
  { key: '/comparison', icon: <SwapOutlined />, label: '모델 비교' },
];

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = menuItems
    .map((item) => item.key)
    .filter((key) => location.pathname.startsWith(key) && key !== '/')
    .pop() || '/';

  // 데모 모드(메인): 실제 사내 포털처럼 — 다른 페이지: 연구 대시보드 톤
  const isDemoPage = selectedKey === '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          background: isDemoPage
            ? 'linear-gradient(90deg, #0f2a5b 0%, #1f4eb6 100%)'
            : '#001529',
          padding: '0 24px',
          height: 56,
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <ApartmentOutlined style={{ color: '#fff', fontSize: 20 }} />
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15 }}>
          <Typography.Text style={{ color: '#fff', fontSize: 15, fontWeight: 700, letterSpacing: '0.02em' }}>
            HR Data Assistant
          </Typography.Text>
          <Typography.Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: 11 }}>
            자연어로 묻고, SQL 없이 바로 답을 받는 사내 데이터 도우미
          </Typography.Text>
        </div>

        <div style={{ flex: 1 }} />

        <Tag color={isDemoPage ? 'blue' : 'default'} style={{ marginRight: 0, fontSize: 11 }}>
          {isDemoPage ? '데모 환경' : '연구 대시보드'}
        </Tag>

        {/* 사용자 식별 (시연 페르소나) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Avatar size={28} icon={<UserOutlined />} style={{ background: '#fff', color: '#1f4eb6' }} />
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
            <Typography.Text style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>
              김인사 매니저
            </Typography.Text>
            <Typography.Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 10 }}>
              인사기획팀 · 일반 권한
            </Typography.Text>
          </div>
        </div>
      </Header>
      <Layout>
        <Sider
          width={200}
          theme="light"
          breakpoint="lg"
          collapsedWidth={60}
          style={{ borderRight: '1px solid #f0f0f0' }}
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        <Content style={{ padding: 24, background: '#f5f5f5', overflow: 'auto' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
