import React, { useState } from "react";
import {
  Card,
  Typography,
  Upload,
  Button,
  Space,
  Alert,
  Form,
  Input,
  Select,
  Row,
  Col,
  Statistic,
  List,
  Tag,
  Checkbox,
  message,
} from "antd";
import {
  InboxOutlined,
  SaveOutlined,
  ReloadOutlined,
  BookOutlined,
  UserOutlined,
  FileTextOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;
const { Dragger } = Upload;

export default function NovelImport() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form] = Form.useForm();

  const [novelData, setNovelData] = useState({
    title: "",
    author: "",
    genre: "未分类",
    concept: "",
    chapters: [],
  });

  const supportedExts = [
    "txt", "md", "markdown", "html", "htm", "rst", "org",
    "epub", "pdf",
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp",
  ];

  const draggerProps = {
    name: "file",
    multiple: false,
    showUploadList: false,
    beforeUpload: (f) => {
      const ext = f.name.toLowerCase().substring(f.name.lastIndexOf(".") + 1);
      if (!supportedExts.includes(ext)) {
        message.error(`不支持的文件格式: .${ext}`);
        return Upload.LIST_IGNORE;
      }
      setFile(f);
      setResult(null);
      return false;
    },
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const data = await api.uploadFile(formData);

      if (!data.success) {
        message.error(data.errors?.join("\n") || "解析失败");
        setLoading(false);
        return;
      }

      setResult(data);
      setNovelData({
        title: data.preview.title,
        author: data.preview.author,
        genre: data.preview.genre || "未分类",
        concept: "",
        chapters: data.full_result.chapters.map((ch) => ({
          chapter_num: ch.chapter_num,
          title: ch.title,
          content: ch.content,
          word_count: ch.word_count,
        })),
      });

      // 初始化表单
      form.setFieldsValue({
        title: data.preview.title,
        author: data.preview.author,
        genre: data.preview.genre || "未分类",
        concept: "",
      });

      if (data.warnings?.length > 0) {
        message.warning(data.warnings.join("\n"));
      }

      message.success("解析成功！");
    } catch (e) {
      message.error(`上传失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const values = await form.validateFields();
      const data = await api.saveImported({
        ...values,
        chapters: novelData.chapters,
      });

      if (data.success) {
        message.success(`导入成功！共 ${data.chapter_count} 章`);
        // 跳转到小说列表
        window.location.href = "/";
      } else {
        message.error(data.error || "保存失败");
      }
    } catch (e) {
      message.error(`保存失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleChapterChange = (idx, field, value) => {
    const newChapters = [...novelData.chapters];
    newChapters[idx] = { ...newChapters[idx], [field]: value };
    setNovelData({ ...novelData, chapters: newChapters });
  };

  const handleRemoveChapter = (idx) => {
    const newChapters = novelData.chapters.filter((_, i) => i !== idx);
    setNovelData({ ...novelData, chapters: newChapters });
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Title level={4}>导入小说</Title>

      <Paragraph type="secondary">
        支持格式：txt, md, html, epub, pdf, 图片（jpg/png 等）
      </Paragraph>

      {/* 上传区域 */}
      {!result && (
        <Card>
          <Dragger {...draggerProps} fileList={file ? [{ uid: "1", name: file.name }] : []}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined style={{ fontSize: 48, color: "#1890ff" }} />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持 {supportedExts.slice(0, 8).join(", ")} 等格式
            </p>
          </Dragger>

          {file && (
            <Row justify="center" style={{ marginTop: 24 }}>
              <Space>
                <Button
                  type="primary"
                  size="large"
                  icon={<FileTextOutlined />}
                  onClick={handleUpload}
                  loading={loading}
                >
                  开始解析
                </Button>
                <Button
                  size="large"
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    setFile(null);
                    setResult(null);
                  }}
                  disabled={loading}
                >
                  重新选择
                </Button>
              </Space>
            </Row>
          )}
        </Card>
      )}

      {/* 解析结果预览 */}
      {result && result.preview && (
        <>
          {/* 基本信息 */}
          <Card title="小说信息">
            <Form form={form} layout="vertical">
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item
                    name="title"
                    label="书名"
                    rules={[{ required: true, message: "请输入书名" }]}
                  >
                    <Input placeholder="请输入书名" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="author" label="作者">
                    <Input placeholder="请输入作者" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item name="genre" label="类型">
                    <Select placeholder="请选择类型">
                      <Option value="未分类">未分类</Option>
                      <Option value="科幻">科幻</Option>
                      <Option value="玄幻">玄幻</Option>
                      <Option value="都市">都市</Option>
                      <Option value="历史">历史</Option>
                      <Option value="悬疑">悬疑</Option>
                      <Option value="言情">言情</Option>
                      <Option value="其他">其他</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col xs={24} sm={24}>
                  <Form.Item name="concept" label="简介">
                    <TextArea rows={3} placeholder="可选，填写小说简介" />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Card>

          {/* 统计 */}
          <Card>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="章节数"
                  value={result.preview.total_chapters}
                  prefix={<BookOutlined />}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="总字数"
                  value={result.preview.total_word_count}
                  prefix={<UserOutlined />}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="状态"
                  value="解析完成"
                  valueStyle={{ color: "#3f8600" }}
                  prefix={<FileTextOutlined />}
                />
              </Col>
            </Row>
            {result.warnings?.length > 0 && (
              <Alert
                message="解析警告"
                description={result.warnings.join("\n")}
                type="warning"
                showIcon
                style={{ marginTop: 16 }}
              />
            )}
          </Card>

          {/* 章节列表 */}
          <Card
            title={
              <Space>
                <span>章节列表</span>
                <Checkbox
                  checked={editing}
                  onChange={(e) => setEditing(e.target.checked)}
                >
                  编辑模式
                </Checkbox>
              </Space>
            }
          >
            <List
              dataSource={novelData.chapters}
              renderItem={(ch, idx) => (
                <List.Item
                  actions={
                    editing
                      ? [
                          <Button
                            type="link"
                            danger
                            key="delete"
                            onClick={() => handleRemoveChapter(idx)}
                          >
                            删除
                          </Button>,
                        ]
                      : []
                  }
                >
                  {editing ? (
                    <Space direction="vertical" style={{ width: "100%" }}>
                      <Input
                        value={ch.title}
                        onChange={(e) =>
                          handleChapterChange(idx, "title", e.target.value)
                        }
                        placeholder="章节标题"
                      />
                      <TextArea
                        value={ch.content}
                        onChange={(e) =>
                          handleChapterChange(idx, "content", e.target.value)
                        }
                        rows={6}
                        placeholder="章节内容"
                      />
                      <Text type="secondary">
                        字数: {ch.word_count?.toLocaleString() || ch.content.length}
                      </Text>
                    </Space>
                  ) : (
                    <List.Item.Meta
                      title={
                        <Space>
                          <Tag color="blue">第{ch.chapter_num}章</Tag>
                          <span>{ch.title}</span>
                          <Text type="secondary">
                            {ch.word_count?.toLocaleString() || ch.content.length} 字
                          </Text>
                        </Space>
                      }
                      description={
                        <Text ellipsis={{ rows: 3, expandable: true }}>
                          {ch.content}
                        </Text>
                      }
                    />
                  )}
                </List.Item>
              )}
            />
          </Card>

          {/* 保存按钮 */}
          <Row justify="center">
            <Space>
              <Button
                type="primary"
                size="large"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={loading}
              >
                保存到小说库
              </Button>
              <Button
                size="large"
                icon={<ReloadOutlined />}
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  setNovelData({
                    title: "",
                    author: "",
                    genre: "未分类",
                    concept: "",
                    chapters: [],
                  });
                }}
                disabled={loading}
              >
                重新导入
              </Button>
            </Space>
          </Row>
        </>
      )}
    </Space>
  );
}
