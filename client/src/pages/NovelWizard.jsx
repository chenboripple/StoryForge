import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Steps,
  Button,
  Form,
  Input,
  Select,
  Space,
  Typography,
  Tag,
  message,
  Spin,
  Alert,
  Collapse,
  List,
  Avatar,
  Badge,
  Divider,
  Modal,
  Tooltip,
  Row,
  Col,
} from "antd";
import {
  RocketOutlined,
  BulbOutlined,
  BookOutlined,
  UserOutlined,
  GlobalOutlined,
  SaveOutlined,
  SendOutlined,
  RobotOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  EditOutlined,
  PlusOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { Panel } = Collapse;
const { Step } = Steps;

const STEPS = [
  {
    key: "concept",
    title: "概念构思",
    icon: <BulbOutlined />,
    description: "确定核心概念和主题",
  },
  {
    key: "outline",
    title: "故事大纲",
    icon: <BookOutlined />,
    description: "设计故事结构和情节",
  },
  {
    key: "characters",
    title: "角色画像",
    icon: <UserOutlined />,
    description: "创建角色和关系",
  },
  {
    key: "world",
    title: "世界观",
    icon: <GlobalOutlined />,
    description: "构建世界观设定",
  },
  {
    key: "review",
    title: "确认完成",
    icon: <CheckCircleOutlined />,
    description: "检查并保存",
  },
];

export default function NovelWizard() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [form] = Form.useForm();
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [novelData, setNovelData] = useState({
    novel_id: "",
    novel_title: "",
    genre: "未分类",
    concept: "",
    outline: "",
    characters: [],
    world_setting: "",
    target_word_count: 3000,
  });
  const [saving, setSaving] = useState(false);
  const chatEndRef = useRef(null);

  // 自动滚动到聊天底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // 获取当前步骤的信息
  const currentStepInfo = STEPS[currentStep];

  // AI 交互函数
  const handleAIChat = async (userInput) => {
    if (!userInput.trim()) return;

    // 添加用户消息到历史
    const userMessage = {
      role: "user",
      content: userInput,
      timestamp: new Date().toISOString(),
    };
    setChatHistory((prev) => [...prev, userMessage]);

    setAiLoading(true);
    try {
      const resp = await fetch("/api/v1/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: userInput,
          step: currentStepInfo.key,
          context: {
            ...novelData,
            current_step: currentStep,
          },
        }),
      });

      const data = await resp.json();

      if (data.success) {
        const aiMessage = {
          role: "assistant",
          content: data.content,
          suggestions: data.suggestions,
          timestamp: new Date().toISOString(),
        };
        setChatHistory((prev) => [...prev, aiMessage]);
        setAiResponse(data);
      } else {
        message.error(data.error || "AI 生成失败");
      }
    } catch (err) {
      message.error(`请求失败: ${err.message}`);
    } finally {
      setAiLoading(false);
    }
  };

  // 保存当前步骤的数据
  const saveStepData = () => {
    const values = form.getFieldsValue();
    setNovelData((prev) => ({
      ...prev,
      ...values,
    }));
    message.success("已保存当前进度");
  };

  // 下一步
  const handleNext = () => {
    saveStepData();
    if (currentStep < STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
      setAiResponse(null);
      // 自动触发 AI 建议
      setTimeout(() => {
        handleAIChat("请给我一些建议");
      }, 500);
    }
  };

  // 上一步
  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
      setAiResponse(null);
    }
  };

  // 完成创建
  const handleFinish = async () => {
    setSaving(true);
    try {
      // 先创建小说
      const createResult = await api.createNovel({
        novel_id: novelData.novel_id,
        novel_title: novelData.novel_title,
        genre: novelData.genre,
        concept: novelData.concept,
        target_word_count: novelData.target_word_count,
      });

      if (createResult.success) {
        // 保存大纲、角色、世界观等
        // TODO: 添加保存这些内容的 API
        message.success("小说创建成功！");
        navigate(`/novels/${createResult.novel_id}`);
      } else {
        message.error(createResult.error || "创建失败");
      }
    } catch (err) {
      message.error(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // 渲染步骤内容
  const renderStepContent = () => {
    switch (currentStepInfo.key) {
      case "concept":
        return (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Form form={form} layout="vertical" initialValues={novelData}>
              <Form.Item
                name="novel_id"
                label="小说ID"
                rules={[
                  { required: true, message: "请输入小说ID" },
                  {
                    pattern: /^[a-zA-Z0-9_-]+$/,
                    message: "只能使用字母、数字、下划线和横线",
                  },
                ]}
                extra="用于URL和文件系统，建议使用英文"
              >
                <Input placeholder="例如：my-novel-001" />
              </Form.Item>

              <Form.Item
                name="novel_title"
                label="小说标题"
                rules={[{ required: true, message: "请输入小说标题" }]}
              >
                <Input placeholder="给你的小说起个名字" />
              </Form.Item>

              <Form.Item name="genre" label="类型" initialValue="未分类">
                <Select placeholder="请选择类型">
                  <Option value="未分类">未分类</Option>
                  <Option value="科幻">科幻</Option>
                  <Option value="玄幻">玄幻</Option>
                  <Option value="都市">都市</Option>
                  <Option value="历史">历史</Option>
                  <Option value="悬疑">悬疑</Option>
                  <Option value="言情">言情</Option>
                  <Option value="年代重生">年代重生</Option>
                  <Option value="末日科幻">末日科幻</Option>
                  <Option value="古代权谋">古代权谋</Option>
                  <Option value="其他">其他</Option>
                </Select>
              </Form.Item>

              <Form.Item name="target_word_count" label="目标字数">
                <Input type="number" placeholder="目标字数" />
              </Form.Item>

              <Form.Item
                name="concept"
                label="核心概念"
                rules={[{ required: true, message: "请描述核心概念" }]}
              >
                <TextArea
                  rows={6}
                  placeholder="用几句话描述你的故事核心：主角是谁？他/她想要什么？遇到什么阻碍？最终会怎样？"
                />
              </Form.Item>
            </Form>
          </Space>
        );

      case "outline":
        return (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Form form={form} layout="vertical" initialValues={novelData}>
              <Form.Item
                name="outline"
                label="故事大纲"
                rules={[{ required: true, message: "请填写故事大纲" }]}
              >
                <TextArea
                  rows={12}
                  placeholder="详细描述你的故事结构：&#10;1. 开头：如何引入故事？&#10;2. 发展：主要情节和转折？&#10;3. 高潮：最精彩的部分？&#10;4. 结局：如何收尾？"
                />
              </Form.Item>
            </Form>
          </Space>
        );

      case "characters":
        return (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Card
              title="角色列表"
              extra={
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    setNovelData((prev) => ({
                      ...prev,
                      characters: [
                        ...prev.characters,
                        {
                          id: `char_${Date.now()}`,
                          name: "",
                          role: "supporting",
                          description: "",
                          personality: "",
                          background: "",
                        },
                      ],
                    }));
                  }}
                >
                  添加角色
                </Button>
              }
            >
              <List
                dataSource={novelData.characters}
                renderItem={(char, index) => (
                  <List.Item
                    actions={[
                      <Button
                        type="link"
                        danger
                        onClick={() => {
                          setNovelData((prev) => ({
                            ...prev,
                            characters: prev.characters.filter(
                              (_, i) => i !== index
                            ),
                          }));
                        }}
                      >
                        删除
                      </Button>,
                    ]}
                  >
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Input
                        placeholder="角色姓名"
                        value={char.name}
                        onChange={(e) => {
                          const newChars = [...novelData.characters];
                          newChars[index].name = e.target.value;
                          setNovelData((prev) => ({
                            ...prev,
                            characters: newChars,
                          }));
                        }}
                      />
                      <Select
                        value={char.role}
                        onChange={(value) => {
                          const newChars = [...novelData.characters];
                          newChars[index].role = value;
                          setNovelData((prev) => ({
                            ...prev,
                            characters: newChars,
                          }));
                        }}
                      >
                        <Option value="protagonist">主角</Option>
                        <Option value="supporting">配角</Option>
                        <Option value="antagonist">反派</Option>
                        <Option value="cameo">客串</Option>
                      </Select>
                      <TextArea
                        placeholder="角色描述"
                        rows={3}
                        value={char.description}
                        onChange={(e) => {
                          const newChars = [...novelData.characters];
                          newChars[index].description = e.target.value;
                          setNovelData((prev) => ({
                            ...prev,
                            characters: newChars,
                          }));
                        }}
                      />
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Space>
        );

      case "world":
        return (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Form form={form} layout="vertical" initialValues={novelData}>
              <Form.Item
                name="world_setting"
                label="世界观设定"
                rules={[{ required: true, message: "请描述世界观" }]}
              >
                <TextArea
                  rows={12}
                  placeholder="描述你的世界：&#10;1. 时间背景：什么时代？&#10;2. 地理环境：世界是什么样的？&#10;3. 社会结构：权力体系、组织？&#10;4. 特殊设定：魔法、科技、规则？&#10;5. 文化氛围：风俗、信仰、价值观？"
                />
              </Form.Item>
            </Form>
          </Space>
        );

      case "review":
        return (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Card title="小说概览">
              <Space direction="vertical" style={{ width: "100%" }}>
                <Text strong>标题：</Text>
                <Text>{novelData.novel_title}</Text>

                <Text strong>类型：</Text>
                <Tag color="blue">{novelData.genre}</Tag>

                <Text strong>目标字数：</Text>
                <Text>{novelData.target_word_count}</Text>

                <Divider />

                <Text strong>核心概念：</Text>
                <Paragraph>{novelData.concept}</Paragraph>

                <Text strong>故事大纲：</Text>
                <Paragraph ellipsis={{ rows: 5, expandable: true }}>
                  {novelData.outline}
                </Paragraph>

                <Text strong>角色数：</Text>
                <Text>{novelData.characters.length} 个</Text>

                <Text strong>世界观：</Text>
                <Paragraph ellipsis={{ rows: 5, expandable: true }}>
                  {novelData.world_setting}
                </Paragraph>
              </Space>
            </Card>

            <Alert
              message="准备创建"
              description="确认以上信息无误后，点击「完成创建」按钮保存你的小说。"
              type="info"
              showIcon
            />
          </Space>
        );

      default:
        return null;
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 头部 */}
      <Row justify="space-between" align="middle">
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <Space>
              <RocketOutlined />
              创作新小说
            </Space>
          </Title>
        </Col>
        <Col>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/novels")}>
            返回
          </Button>
        </Col>
      </Row>

      {/* 步骤条 */}
      <Card>
        <Steps current={currentStep} items={STEPS} />
      </Card>

      {/* 主要内容区 */}
      <Row gutter={[16, 16]}>
        {/* 左侧：表单 */}
        <Col xs={24} lg={14}>
          <Card
            title={
              <Space>
                {currentStepInfo.icon}
                {currentStepInfo.title}
              </Space>
            }
            extra={
              <Space>
                <Button onClick={saveStepData} icon={<SaveOutlined />}>
                  保存进度
                </Button>
              </Space>
            }
          >
            {renderStepContent()}

            {/* 底部导航 */}
            <Divider />
            <Row justify="space-between">
              <Col>
                <Button
                  disabled={currentStep === 0}
                  onClick={handlePrev}
                  icon={<ArrowLeftOutlined />}
                >
                  上一步
                </Button>
              </Col>
              <Col>
                {currentStep === STEPS.length - 1 ? (
                  <Button
                    type="primary"
                    onClick={handleFinish}
                    loading={saving}
                    icon={<CheckCircleOutlined />}
                  >
                    完成创建
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    onClick={handleNext}
                    icon={<ArrowRightOutlined />}
                  >
                    下一步
                  </Button>
                )}
              </Col>
            </Row>
          </Card>
        </Col>

        {/* 右侧：AI 助手 */}
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <RobotOutlined />
                AI 创作助手
              </Space>
            }
            style={{ height: "100%" }}
          >
            {/* 聊天历史 */}
            <div
              style={{
                maxHeight: 500,
                overflowY: "auto",
                marginBottom: 16,
                padding: 8,
                background: "#f5f5f5",
                borderRadius: 8,
              }}
            >
              {chatHistory.length === 0 ? (
                <Text type="secondary" style={{ display: "block", textAlign: "center", padding: 20 }}>
                  点击下方的建议或输入你的想法，与 AI 一起创作！
                </Text>
              ) : (
                chatHistory.map((msg, index) => (
                  <div
                    key={index}
                    style={{
                      marginBottom: 12,
                      textAlign: msg.role === "user" ? "right" : "left",
                    }}
                  >
                    <div
                      style={{
                        display: "inline-block",
                        maxWidth: "80%",
                        padding: 12,
                        borderRadius: 8,
                        background:
                          msg.role === "user" ? "#1890ff" : "#fff",
                        color: msg.role === "user" ? "#fff" : "#333",
                        border:
                          msg.role === "user"
                            ? "none"
                            : "1px solid #d9d9d9",
                      }}
                    >
                      <Text
                        style={{
                          color:
                            msg.role === "user" ? "#fff" : "inherit",
                        }}
                      >
                        {msg.content}
                      </Text>
                      {msg.suggestions && (
                        <div style={{ marginTop: 8 }}>
                          {msg.suggestions.map((s, i) => (
                            <Tag
                              key={i}
                              style={{ margin: "2px", cursor: "pointer" }}
                              onClick={() => handleAIChat(s)}
                            >
                              {s}
                            </Tag>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={chatEndRef} />
            </div>

            {/* 输入框 */}
            <Space.Compact style={{ width: "100%" }}>
              <TextArea
                placeholder="输入你的想法，或点击建议..."
                autoSize={{ minRows: 2, maxRows: 4 }}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    const value = e.target.value;
                    if (value.trim()) {
                      handleAIChat(value);
                      e.target.value = "";
                    }
                  }
                }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={aiLoading}
                onClick={() => {
                  const textarea = document.querySelector("textarea");
                  if (textarea && textarea.value.trim()) {
                    handleAIChat(textarea.value);
                    textarea.value = "";
                  }
                }}
              >
                发送
              </Button>
            </Space.Compact>

            {/* 快捷建议 */}
            <div style={{ marginTop: 12 }}>
              <Text type="secondary">快捷建议：</Text>
              <Space wrap style={{ marginTop: 8 }}>
                {currentStep === 0 && (
                  <>
                    <Tag
                      color="blue"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("帮我构思一个精彩的故事概念")
                      }
                    >
                      构思概念
                    </Tag>
                    <Tag
                      color="green"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("这个故事适合什么类型？")
                      }
                    >
                      确定类型
                    </Tag>
                  </>
                )}
                {currentStep === 1 && (
                  <>
                    <Tag
                      color="blue"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("帮我设计三幕式结构")
                      }
                    >
                      三幕式结构
                    </Tag>
                    <Tag
                      color="green"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("设计几个关键转折点")
                      }
                    >
                      关键转折
                    </Tag>
                  </>
                )}
                {currentStep === 2 && (
                  <>
                    <Tag
                      color="blue"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("帮我设计主角的成长弧线")
                      }
                    >
                      主角设计
                    </Tag>
                    <Tag
                      color="green"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("设计几个有趣的配角")
                      }
                    >
                      配角设计
                    </Tag>
                  </>
                )}
                {currentStep === 3 && (
                  <>
                    <Tag
                      color="blue"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("帮我构建独特的世界观")
                      }
                    >
                      世界观构建
                    </Tag>
                    <Tag
                      color="green"
                      style={{ cursor: "pointer" }}
                      onClick={() =>
                        handleAIChat("设计世界的基本规则")
                      }
                    >
                      世界规则
                    </Tag>
                  </>
                )}
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
