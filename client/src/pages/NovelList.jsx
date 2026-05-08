import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Row,
  Col,
  Typography,
  Tag,
  Progress,
  Button,
  Empty,
  Spin,
  Alert,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
} from "antd";
import {
  BookOutlined,
  ImportOutlined,
  PlusOutlined,
  EyeOutlined,
  EditOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

export default function NovelList() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState(null);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadNovels();
  }, []);

  const loadNovels = () => {
    api
      .listNovels()
      .then(setNovels)
      .catch((err) => setError(err.message));
  };

  const handleCreateNovel = async (values) => {
    setCreating(true);
    try {
      const result = await api.createNovel({
        novel_id: values.novel_id,
        novel_title: values.novel_title,
        genre: values.genre,
        concept: values.concept,
        target_word_count: values.target_word_count || 3000,
      });

      if (result.success) {
        message.success(`小说「${result.novel_title}」创建成功！`);
        setIsModalOpen(false);
        form.resetFields();
        loadNovels();
        // 跳转到新创建的小说详情页
        navigate(`/novels/${result.novel_id}`);
      } else {
        message.error(result.error || "创建失败");
      }
    } catch (err) {
      message.error(`创建失败: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  if (error) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
      />
    );
  }

  if (novels === null) {
    return (
      <div style={{ textAlign: "center", padding: "40px" }}>
        <Spin size="large" />
        <p>加载中…</p>
      </div>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 页面标题和操作 */}
      <Row justify="space-between" align="middle">
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <Space>
              <BookOutlined />
              小说管理
            </Space>
          </Title>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<PlusOutlined />}
              onClick={() => setIsModalOpen(true)}
            >
              创建新小说
            </Button>
            <Button
              type="primary"
              icon={<ImportOutlined />}
              onClick={() => navigate("/import")}
            >
              导入小说
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 小说卡片 */}
      {novels.length === 0 ? (
        <Empty
          description="还没有任何小说"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Space>
            <Button onClick={() => setIsModalOpen(true)}>
              创建新小说
            </Button>
            <Button type="primary" onClick={() => navigate("/import")}>
              导入小说
            </Button>
          </Space>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {novels.map((n) => {
            const total = n.total_chapters || 0;
            const approved = n.approved_chapters || 0;
            const pct = total === 0 ? 0 : Math.round((approved / total) * 100);

            return (
              <Col xs={24} sm={12} lg={8} key={n.novel_id}>
                <Card
                  hoverable
                  onClick={() => navigate(`/novels/${n.novel_id}`)}
                  actions={[
                    <Space>
                      <EyeOutlined />
                      <span>查看详情</span>
                    </Space>,
                  ]}
                >
                  <Space direction="vertical" size="small" style={{ width: "100%" }}>
                    <Space>
                      <Tag color="blue">{n.genre || "未分类"}</Tag>
                      <Tag color="default">{labels.stage(n.current_stage)}</Tag>
                    </Space>

                    <Title level={5} style={{ margin: "8px 0" }}>
                      {n.novel_title || "未命名"}
                    </Title>

                    <Paragraph
                      ellipsis={{ rows: 2 }}
                      type="secondary"
                      style={{ marginBottom: 8 }}
                    >
                      {n.concept || "暂无描述"}
                    </Paragraph>

                    <Progress
                      percent={pct}
                      size="small"
                      status={pct === 100 ? "success" : "active"}
                      format={() => `${approved}/${total} 章`}
                    />

                    <Row justify="space-between">
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        当前第 {n.current_chapter || 1} 章
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {n.character_count || 0} 角色
                      </Text>
                    </Row>
                  </Space>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      {/* 创建新小说弹窗 */}
      <Modal
        title="创建新小说"
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateNovel}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="novel_id"
            label="小说ID"
            rules={[
              { required: true, message: "请输入小说ID" },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: "只能使用字母、数字、下划线和横线" },
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
            <Input placeholder="请输入小说标题" />
          </Form.Item>

          <Form.Item
            name="genre"
            label="类型"
            initialValue="未分类"
          >
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

          <Form.Item
            name="concept"
            label="一句话概念"
          >
            <Input.TextArea
              rows={3}
              placeholder="用一句话描述你的小说核心概念"
            />
          </Form.Item>

          <Form.Item
            name="target_word_count"
            label="目标字数"
            initialValue={3000}
          >
            <Input type="number" placeholder="目标字数" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: "right" }}>
            <Space>
              <Button
                onClick={() => {
                  setIsModalOpen(false);
                  form.resetFields();
                }}
              >
                取消
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={creating}
                icon={<EditOutlined />}
              >
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
