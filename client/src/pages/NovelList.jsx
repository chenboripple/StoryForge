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
} from "antd";
import {
  BookOutlined,
  ImportOutlined,
  EyeOutlined,
  EditOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";
import { extractSummary, extractWordCount } from "../utils/novelSummary";

const { Title, Text, Paragraph } = Typography;

export default function NovelList() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listNovels()
      .then(setNovels)
      .catch((err) => setError(err.message));
  }, []);

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
              icon={<EditOutlined />}
              onClick={() => navigate("/wizard")}
            >
              创作新小说
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
            <Button type="primary" size="large" onClick={() => navigate("/wizard")} icon={<EditOutlined />}>
              创作新小说
            </Button>
            <Button onClick={() => navigate("/import")} icon={<ImportOutlined />}>
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

                    {/* 摘要 */}
                    <Paragraph
                      ellipsis={{ rows: 2 }}
                      type="secondary"
                      style={{ marginBottom: 4 }}
                    >
                      {extractSummary(n.concept)}
                    </Paragraph>

                    {/* 字数信息 */}
                    {extractWordCount(n.concept) && (
                      <Text type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
                        规划字数：{extractWordCount(n.concept)}
                      </Text>
                    )}

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
    </Space>
  );
}
