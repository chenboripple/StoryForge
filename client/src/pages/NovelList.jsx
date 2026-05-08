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
  Statistic,
} from "antd";
import {
  BookOutlined,
  ImportOutlined,
  FileSearchOutlined,
  PlusOutlined,
  EyeOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";

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

  const totalNovels = novels.length;
  const totalChapters = novels.reduce((sum, n) => sum + (n.total_chapters || 0), 0);
  const totalApproved = novels.reduce((sum, n) => sum + (n.approved_chapters || 0), 0);

  return (
    <div>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {/* 顶部统计 */}
        <Row gutter={16}>
          <Col span={8}>
            <Card>
              <Statistic
                title="小说总数"
                value={totalNovels}
                prefix={<BookOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="总章节数"
                value={totalChapters}
                prefix={<FileSearchOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="已完成章节"
                value={totalApproved}
                prefix={<ImportOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* 操作栏 */}
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={4} style={{ margin: 0 }}>
              小说清单
            </Title>
          </Col>
          <Col>
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
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
            <Button type="primary" onClick={() => navigate("/import")}>
              导入小说
            </Button>
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
                      <EyeOutlined key="view" />,
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
      </Space>
    </div>
  );
}
