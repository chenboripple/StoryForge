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
  message,
} from "antd";
import {
  BookOutlined,
  ImportOutlined,
  EyeOutlined,
  EditOutlined,
  SaveOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";

const { Title, Text, Paragraph } = Typography;

export default function NovelList() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState(null);
  const [originalOrder, setOriginalOrder] = useState([]);
  const [error, setError] = useState(null);
  const [draggingId, setDraggingId] = useState(null);
  const [savingOrder, setSavingOrder] = useState(false);

  useEffect(() => {
    api
      .listNovels()
      .then((data) => {
        setNovels(data);
        setOriginalOrder((data || []).map((n) => n.novel_id));
      })
      .catch((err) => setError(err.message));
  }, []);

  const isOrderDirty = Array.isArray(novels)
    && novels.length > 0
    && JSON.stringify(novels.map((n) => n.novel_id)) !== JSON.stringify(originalOrder);

  const moveNovel = (fromId, toId) => {
    if (!fromId || !toId || fromId === toId) return;
    setNovels((prev) => {
      if (!Array.isArray(prev)) return prev;
      const fromIndex = prev.findIndex((n) => n.novel_id === fromId);
      const toIndex = prev.findIndex((n) => n.novel_id === toId);
      if (fromIndex < 0 || toIndex < 0) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  };

  const saveOrder = async () => {
    if (!Array.isArray(novels) || novels.length === 0) return;
    setSavingOrder(true);
    try {
      const ids = novels.map((n) => n.novel_id);
      await api.reorderNovels(ids);
      setOriginalOrder(ids);
      message.success("小说顺序已保存");
    } catch (err) {
      message.error(`保存顺序失败: ${err.message}`);
    } finally {
      setSavingOrder(false);
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
              icon={<SaveOutlined />}
              type="primary"
              ghost
              disabled={!isOrderDirty}
              loading={savingOrder}
              onClick={saveOrder}
            >
              保存排序
            </Button>
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
              <Col
                xs={24}
                sm={12}
                lg={8}
                key={n.novel_id}
                draggable
                onDragStart={(e) => {
                  setDraggingId(n.novel_id);
                  e.dataTransfer.effectAllowed = "move";
                  e.dataTransfer.setData("text/plain", n.novel_id);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const fromId = e.dataTransfer.getData("text/plain") || draggingId;
                  moveNovel(fromId, n.novel_id);
                  setDraggingId(null);
                }}
                onDragEnd={() => setDraggingId(null)}
              >
                <Card
                  hoverable
                  onClick={() => navigate(`/novels/${n.novel_id}`)}
                  style={draggingId === n.novel_id ? { opacity: 0.6 } : undefined}
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
    </Space>
  );
}
