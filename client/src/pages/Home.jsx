import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Row,
  Col,
  Typography,
  Button,
  Space,
  Steps,
  Divider,
  Result,
  Tag,
} from "antd";
import {
  RocketOutlined,
  BookOutlined,
  FileSearchOutlined,
  ImportOutlined,
  ReadOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";

const { Title, Paragraph, Text } = Typography;
const { Step } = Steps;

export default function Home() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listNovels()
      .then((data) => {
        setNovels(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const totalNovels = novels?.length || 0;
  const totalChapters = novels?.reduce((sum, n) => sum + (n.total_chapters || 0), 0) || 0;
  const totalApproved = novels?.reduce((sum, n) => sum + (n.approved_chapters || 0), 0) || 0;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 顶部欢迎区域 */}
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            style={{
              background:
                "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              color: "white",
              textAlign: "center",
              padding: "48px 24px",
            }}
          >
            <Title level={2} style={{ color: "white", marginBottom: 8 }}>
              欢迎使用 StoryForge
            </Title>
            <Paragraph style={{ color: "rgba(255,255,255,0.9)", fontSize: 16 }}>
              多 Agent 小说创作平台，从创作、萃取到 IP 生成，一站式解决方案
            </Paragraph>
            <Space size="middle" style={{ marginTop: 16 }}>
              <Button
                type="primary"
                size="large"
                style={{
                  background: "rgba(255,255,255,0.2)",
                  border: "1px solid rgba(255,255,255,0.4)",
                }}
                onClick={() => navigate("/novels")}
              >
                <Space>
                  <BookOutlined />
                  开始创作
                </Space>
              </Button>
              <Button
                size="large"
                style={{
                  background: "white",
                  color: "#667eea",
                }}
                onClick={() => navigate("/import")}
              >
                <Space>
                  <ImportOutlined />
                  导入小说
                </Space>
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="小说总数"
              value={totalNovels}
              prefix={<BookOutlined />}
              valueStyle={{ color: "#3f8600" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总章节数"
              value={totalChapters}
              prefix={<ReadOutlined />}
              valueStyle={{ color: "#1890ff" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已完成章节"
              value={totalApproved}
              prefix={<FileSearchOutlined />}
              valueStyle={{ color: "#722ed1" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="IP 总数"
              value={0}
              prefix={<RocketOutlined />}
              valueStyle={{ color: "#fa8c16" }}
            />
          </Card>
        </Col>
      </Row>

      {/* Pipeline 工作流 */}
      <Card title="StoryForge 工作流">
        <Steps
          current={-1}
          items={[
            {
              title: "创作与管理",
              description: "新建、导入、管理你的小说作品",
              icon: <BookOutlined />,
            },
            {
              title: "信息萃取",
              description: "智能提取角色、世界观、故事脉络",
              icon: <FileSearchOutlined />,
            },
            {
              title: "IP 生成",
              description: "创作衍生内容、音频视频、AI Agent",
              icon: <RocketOutlined />,
            },
          ]}
        />
      </Card>

      {/* 快速入口 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            title="创作管理"
            extra={<BookOutlined />}
            onClick={() => navigate("/novels")}
          >
            <Paragraph>
              管理你的所有小说作品，查看创作进度，继续编写内容
            </Paragraph>
            <Space>
              <Tag color="blue">创作中</Tag>
              <Tag color="green">已完成</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            title="信息萃取"
            extra={<FileSearchOutlined />}
            onClick={() => navigate("/extraction")}
          >
            <Paragraph>
              从已有作品中提取关键信息，建立知识图谱，为 IP 生成做准备
            </Paragraph>
            <Space>
              <Tag color="purple">角色提取</Tag>
              <Tag color="cyan">世界观整理</Tag>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            hoverable
            title="IP 生成"
            extra={<RocketOutlined />}
            onClick={() => navigate("/ip-generation")}
          >
            <Paragraph>
              基于萃取的信息，生成衍生内容、音频视频、AI 对话 Agent
            </Paragraph>
            <Space>
              <Tag color="orange">内容创作</Tag>
              <Tag color="red">多媒体制作</Tag>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 关于 StoryForge */}
      <Card title="关于 StoryForge">
        <Paragraph>
          StoryForge 是一个多 Agent 小说创作平台，通过智能工作流，
          帮助你从故事创作、信息萃取到 IP 生成，一站式完成所有工作。
        </Paragraph>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <ul>
              <li>
                <Text strong>创作管理：</Text>
                支持新建、导入、编辑小说作品
              </li>
              <li>
                <Text strong>智能萃取：</Text>
                自动提取角色、世界观、故事脉络
              </li>
            </ul>
          </Col>
          <Col xs={24} sm={12}>
            <ul>
              <li>
                <Text strong>IP 衍生：</Text>
                创作内容、音频视频、AI Agent
              </li>
              <li>
                <Text strong>多 Agent：</Text>
                智能协作，高效创作
              </li>
            </ul>
          </Col>
        </Row>
      </Card>
    </Space>
  );
}

// 缺失的 Statistic 组件，这里补全一下
function Statistic({ title, value, prefix, valueStyle }) {
  return (
    <div>
      <div style={{ color: "rgba(0,0,0,0.45)", marginBottom: 4 }}>
        {prefix && <span style={{ marginRight: 8 }}>{prefix}</span>}
        {title}
      </div>
      <div style={{ fontSize: 30, fontWeight: 600, ...valueStyle }}>
        {value}
      </div>
    </div>
  );
}
