import React, { useState, useEffect } from "react";
import {
  Card,
  Typography,
  Select,
  Button,
  Space,
  Steps,
  Form,
  Input,
  Row,
  Col,
  Divider,
} from "antd";
import {
  RocketOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";

const { Title, Paragraph, Text } = Typography;
const { Option } = Select;
const { Step } = Steps;

const types = [
  {
    label: "文字内容",
    value: "text",
    icon: <FileTextOutlined />,
    description: "生成简介、摘要、同人等文字内容",
  },
  {
    label: "视频/音频",
    value: "media",
    icon: <PlayCircleOutlined />,
    description: "生成有声书、动画、短视频",
  },
  {
    label: "Agent",
    value: "agent",
    icon: <RobotOutlined />,
    description: "创建小说角色对话 Agent",
  },
];

export default function IPGeneration() {
  const [novels, setNovels] = useState(null);
  const [selectedNovel, setSelectedNovel] = useState(null);
  const [selectedType, setSelectedType] = useState("text");
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    api.listNovels().then(setNovels);
  }, []);

  const handleStart = async (values) => {
    if (!selectedNovel) return;
    setLoading(true);
    setStep(1);

    // 模拟生成过程
    setTimeout(() => {
      setStep(2);
      setTimeout(() => {
        setStep(3);
        setLoading(false);
        setResult({
          type: selectedType,
          title: values.title || "IP 生成结果",
          output: selectedType === "text"
            ? "生成的小说介绍文案..."
            : selectedType === "media"
            ? "生成的视频预览..."
            : "Agent 配置信息...",
        });
      }, 1500);
    }, 1000);
  };

  const typeInfo = types.find((t) => t.value === selectedType);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Title level={4}>IP 生成</Title>

      {/* 选择小说 */}
      <Card title="选择要生成 IP 的小说">
        <Select
          placeholder="请选择小说"
          style={{ width: "100%" }}
          value={selectedNovel}
          onChange={setSelectedNovel}
          disabled={step > 0}
          options={
            novels?.map((n) => ({
              label: n.novel_title,
              value: n.novel_id,
            })) || []
          }
        />
      </Card>

      {/* 选择 IP 类型 */}
      {selectedNovel && step === 0 && (
        <Card title="选择 IP 类型">
          <Row gutter={16}>
            {types.map((type) => (
              <Col xs={24} sm={8} key={type.value}>
                <Card
                  hoverable
                  bordered={selectedType === type.value}
                  style={{
                    borderColor: selectedType === type.value ? "#1890ff" : undefined,
                  }}
                  onClick={() => setSelectedType(type.value)}
                >
                  <Space direction="vertical" align="center" style={{ width: "100%" }}>
                    <span style={{ fontSize: 32 }}>{type.icon}</span>
                    <Text strong>{type.label}</Text>
                    <Text type="secondary" style={{ fontSize: 12, textAlign: "center" }}>
                      {type.description}
                    </Text>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>

          <Divider />

          <Form
            form={form}
            layout="vertical"
            onFinish={handleStart}
          >
            <Form.Item
              name="title"
              label="IP 标题"
              rules={[{ required: true, message: "请输入标题" }]}
            >
              <Input placeholder="为这个 IP 取个标题" />
            </Form.Item>

            <Form.Item
              name="description"
              label="描述"
            >
              <Input.TextArea placeholder="描述你想要生成的 IP" rows={3} />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                size="large"
                icon={<RocketOutlined />}
                htmlType="submit"
                block
              >
                开始生成
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}

      {/* 步骤 */}
      {step > 0 && (
        <Card title="生成进度">
          <Steps current={step} items={[
            { title: "准备", icon: <RocketOutlined /> },
            { title: "生成中", icon: <ThunderboltOutlined /> },
            { title: "完成", icon: <CheckCircleOutlined /> },
          ]} />
        </Card>
      )}

      {/* 生成结果 */}
      {step === 3 && result && (
        <Card title="生成结果">
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Card size="small" type="inner">
              <Title level={5}>{result.title}</Title>
              <Paragraph>{result.output}</Paragraph>
            </Card>

            <Row justify="center">
              <Space>
                <Button size="large">预览</Button>
                <Button type="primary" size="large">下载/部署</Button>
              </Space>
            </Row>
          </Space>
        </Card>
      )}
    </Space>
  );
}
