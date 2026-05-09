import React, { useState, useEffect } from "react";
import {
  Card,
  Typography,
  Select,
  Button,
  Steps,
  Space,
  List,
  Avatar,
  Descriptions,
  Tag,
  Row,
} from "antd";
import {
  FileSearchOutlined,
  UserOutlined,
  EnvironmentOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  RocketOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";

const { Title } = Typography;
const { Option } = Select;
const { Step } = Steps;

export default function Extraction() {
  const [novels, setNovels] = useState(null);
  const [selectedNovel, setSelectedNovel] = useState(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [extractionResult, setExtractionResult] = useState(null);

  useEffect(() => {
    api.listNovels().then(setNovels);
  }, []);

  const handleStart = () => {
    if (!selectedNovel) return;
    setLoading(true);
    setStep(1);
    // 模拟萃取过程
    setTimeout(() => {
      setStep(2);
      setTimeout(() => {
        setStep(3);
        setLoading(false);
        setExtractionResult({
          novelId: selectedNovel,
          characters: [
            { id: "char1", name: "角色1", description: "主要角色描述" },
            { id: "char2", name: "角色2", description: "配角描述" },
            { id: "char3", name: "角色3", description: "反派描述" },
          ],
          worldSettings: [
            { key: "地点1", value: "主要场景描述" },
            { key: "地点2", value: "次要场景描述" },
          ],
          foreshadowings: [
            { chapter: 1, content: "伏笔1内容描述" },
            { chapter: 3, content: "伏笔2内容描述" },
          ],
          themes: ["主题1", "主题2", "主题3"],
        });
      }, 1500);
    }, 1000);
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Title level={4}>小说信息萃取</Title>

      {/* 选择小说 */}
      <Card title="选择要萃取的小说">
        <Space.Compact style={{ width: "100%" }}>
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
          <Button
            type="primary"
            icon={<FileSearchOutlined />}
            onClick={handleStart}
            disabled={!selectedNovel || step > 0}
            loading={loading}
          >
            开始萃取
          </Button>
        </Space.Compact>
      </Card>

      {/* 步骤 */}
      <Card title="萃取进度">
        <Steps current={step} items={[
          { title: "准备", icon: <FileSearchOutlined /> },
          { title: "分析原文", icon: <UserOutlined /> },
          { title: "萃取完成", icon: <CheckCircleOutlined /> },
        ]} />
      </Card>

      {/* 萃取结果 */}
      {step === 3 && extractionResult && (
        <>
          <Card title="角色信息" extra={<UserOutlined />}>
            <List
              dataSource={extractionResult.characters}
              renderItem={(char) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} />}
                    title={char.name}
                    description={char.description}
                  />
                </List.Item>
              )}
            />
          </Card>

          <Card title="世界观设定" extra={<EnvironmentOutlined />}>
            <Descriptions column={1} bordered>
              {extractionResult.worldSettings.map((ws) => (
                <Descriptions.Item key={ws.key} label={ws.key}>
                  {ws.value}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>

          <Card title="主题与风格" extra={<ThunderboltOutlined />}>
            <Space wrap>
              {extractionResult.themes.map((t, i) => (
                <Tag key={i} color="blue">{t}</Tag>
              ))}
            </Space>
          </Card>

          <Row justify="center">
            <Button
              type="primary"
              size="large"
              icon={<RocketOutlined />}
              onClick={() => {
                window.location.href = "/ip-generation";
              }}
            >
              前往 IP 生成
            </Button>
          </Row>
        </>
      )}
    </Space>
  );
}
