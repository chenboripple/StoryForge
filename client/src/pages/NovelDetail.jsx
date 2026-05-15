import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  Typography,
  Tag,
  Progress,
  Button,
  Empty,
  Spin,
  Alert,
  Space,
  Row,
  Col,
  List,
  Avatar,
  Collapse,
  Badge,
  Steps,
  Statistic,
  Divider,
  Tooltip,
} from "antd";
import {
  ArrowLeftOutlined,
  FileSearchOutlined,
  RocketOutlined,
  UserOutlined,
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;
const { Step } = Steps;

const PIPELINE_STEPS = [
  { key: "creation", label: "创作层", description: "小说编写与管理" },
  { key: "extraction", label: "萃取层", description: "提取关键信息" },
  { key: "ip_generation", label: "IP 生成层", description: "生成衍生内容" },
];

function ChapterDetail({ novelId, chapterNum, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api
      .getChapter(novelId, chapterNum)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [novelId, chapterNum]);

  if (error)
    return (
      <Alert message="章节加载失败" description={error} type="error" />
    );
  if (!data) return <Spin tip="加载章节中…" />;

  return (
    <Card
      title={
        <Space>
          <span>
            第 {data.chapter_num} 章 · {labels.status(data.status)} ·{" "}
            {data.word_count} 字
          </span>
        </Space>
      }
      extra={<Button onClick={onClose}>收起</Button>}
    >
      <Paragraph style={{ whiteSpace: "pre-wrap" }}>
        {data.content}
      </Paragraph>

      {data.reviews.length > 0 && (
        <>
          <Divider />
          <Title level={5}>审稿记录</Title>
          <List
            dataSource={data.reviews}
            renderItem={(r) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <span>
                        第 {r.round} 轮 · {r.reviewer} · {r.score} 分
                      </span>
                      <Tag color={r.passed ? "success" : "warning"}>
                        {r.passed ? "通过" : "未通过"}
                      </Tag>
                    </Space>
                  }
                  description={<pre>{r.comments}</pre>}
                />
              </List.Item>
            )}
          />
        </>
      )}

      {data.proofread_records.length > 0 && (
        <>
          <Divider />
          <Title level={5}>校对记录</Title>
          <List
            dataSource={data.proofread_records}
            renderItem={(p) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <span>第 {p.round} 轮 · {p.proofreader}</span>
                      <Tag color={p.passed ? "success" : "warning"}>
                        {p.passed ? "通过" : "需返工"}
                      </Tag>
                    </Space>
                  }
                  description={<pre>{p.comments}</pre>}
                />
              </List.Item>
            )}
          />
        </>
      )}
    </Card>
  );
}

export default function NovelDetail() {
  const { novelId } = useParams();
  const navigate = useNavigate();
  const [novel, setNovel] = useState(null);
  const [chapters, setChapters] = useState(null);
  const [characterThumbs, setCharacterThumbs] = useState({});
  const [error, setError] = useState(null);
  const [activeChapter, setActiveChapter] = useState(null);

  useEffect(() => {
    setNovel(null);
    setChapters(null);
    setCharacterThumbs({});
    setError(null);
    Promise.all([api.getNovel(novelId), api.listChapters(novelId)])
      .then(([n, c]) => {
        setNovel(n);
        setChapters(c.chapters);
      })
      .catch((err) => setError(err.message));
  }, [novelId]);

  useEffect(() => {
    const chars = novel?.characters || [];
    if (!novel || chars.length === 0) return;

    let disposed = false;
    const toCharacterId = (c) => {
      const raw = c?.character_id || c?.id || c?.name || "unknown";
      return String(raw).trim() || "unknown";
    };

    Promise.all(
      chars.map(async (c) => {
        const cid = toCharacterId(c);
        try {
          const res = await api.getCharacterVisuals(novelId, cid);
          const main = res?.profile?.main_image;
          return [cid, main?.thumb_url || main?.url || ""];
        } catch (e) {
          return [cid, ""];
        }
      })
    ).then((entries) => {
      if (disposed) return;
      setCharacterThumbs(Object.fromEntries(entries));
    });

    return () => {
      disposed = true;
    };
  }, [novelId, novel]);

  if (error) {
    return (
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")}>
          返回清单
        </Button>
        <Alert message="加载失败" description={error} type="error" />
      </Space>
    );
  }

  if (!novel || !chapters) {
    return (
      <div style={{ textAlign: "center", padding: "40px" }}>
        <Spin size="large" />
        <p>加载中…</p>
      </div>
    );
  }

  const total = chapters.length;
  const approved = chapters.filter((c) => c.status === "approved").length;
  const pct = total === 0 ? 0 : Math.round((approved / total) * 100);

  const currentStepIndex = PIPELINE_STEPS.findIndex(
    (s) => s.key === novel.current_stage
  );

  const toCharacterId = (c) => {
    const raw = c?.character_id || c?.id || c?.name || "unknown";
    return String(raw).trim() || "unknown";
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 返回按钮 */}
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")}>
        返回清单
      </Button>

      {/* 头部信息 */}
      <Card>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Space>
            <Tag color="blue">{novel.genre || "未分类"}</Tag>
            <Tag>{labels.stage(novel.current_stage)}</Tag>
          </Space>

          <Title level={3} style={{ margin: 0 }}>
            {novel.novel_title || "未命名"}
          </Title>

          <Paragraph type="secondary" ellipsis={{ rows: 3 }}>
            {novel.concept || "暂无描述"}
          </Paragraph>

          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="总章节" value={total} prefix={<BookOutlined />} />
            </Col>
            <Col span={8}>
              <Statistic
                title="已完成"
                value={approved}
                prefix={<CheckCircleOutlined />}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="当前章节"
                value={novel.current_chapter || 1}
                prefix={<ClockCircleOutlined />}
              />
            </Col>
          </Row>

          <Progress
            percent={pct}
            status={pct === 100 ? "success" : "active"}
            format={() => `${approved}/${total} 章 (${pct}%)`}
          />
        </Space>
      </Card>

      {/* Pipeline 阶段 */}
      <Card title="Pipeline 阶段">
        <Steps current={currentStepIndex}>
          {PIPELINE_STEPS.map((step) => (
            <Step
              key={step.key}
              title={step.label}
              description={step.description}
            />
          ))}
        </Steps>
      </Card>

      {/* 操作按钮 */}
      <Card>
        <Space>
          <Button
            type="primary"
            icon={<FileSearchOutlined />}
            onClick={() => navigate("/extraction")}
          >
            萃取信息
          </Button>
          <Button
            icon={<RocketOutlined />}
            onClick={() => navigate("/ip-generation")}
          >
            生成 IP
          </Button>
        </Space>
      </Card>

      {/* 角色信息 */}
      <Card title={`角色 (${(novel.characters || []).length})`}>
        {(novel.characters || []).length === 0 ? (
          <Empty description="尚未定义角色" />
        ) : (
          <List
            grid={{ gutter: 16, xs: 1, sm: 1, md: 2, xl: 3 }}
            dataSource={novel.characters || []}
            renderItem={(c) => (
              <List.Item>
                <Card
                  size="small"
                  hoverable
                  onClick={() =>
                    navigate(
                      `/novels/${encodeURIComponent(novelId)}/characters/${encodeURIComponent(
                        toCharacterId(c)
                      )}`,
                      {
                        state: {
                          character: c,
                          novelTitle: novel.novel_title,
                        },
                      }
                    )
                  }
                >
                  <Space
                    align="start"
                    style={{
                      width: "100%",
                      justifyContent: "space-between",
                      gap: 16,
                    }}
                  >
                    <Space align="start" size={12}>
                      <Avatar
                        size={52}
                        src={characterThumbs[toCharacterId(c)] || undefined}
                        icon={<UserOutlined />}
                        shape="square"
                      />
                      <Space direction="vertical" size={2}>
                        <Text strong style={{ fontSize: 16 }}>
                          {c.name || c.id || c.character_id || "未知角色"}
                        </Text>
                        <Space size={6} wrap>
                          {c.gender ? <Tag>{c.gender}</Tag> : null}
                          {c.age ? <Tag>{c.age}岁</Tag> : null}
                          {c.role ? <Tag color="blue">{c.role}</Tag> : null}
                        </Space>
                        <Tooltip title={c.personality || c.description || "暂无描述"}>
                          <Text type="secondary" ellipsis style={{ maxWidth: 320 }}>
                            {c.personality || c.description || "暂无描述"}
                          </Text>
                        </Tooltip>
                      </Space>
                    </Space>
                    <Button type="link" onClick={(e) => e.preventDefault()}>
                      查看详情
                    </Button>
                  </Space>
                </Card>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 章节列表（按卷分组） */}
      <Card title={`章节 (${total})`}>
        {total === 0 ? (
          <Empty description="还没有章节" />
        ) : (
          (() => {
            // 按卷分组，每 10 章为一卷（与后端 pipeline 约定一致）
            const volumeMap = {};
            chapters.forEach((c) => {
              const vol = Math.floor((c.chapter_num - 1) / 10) + 1;
              if (!volumeMap[vol]) volumeMap[vol] = [];
              volumeMap[vol].push(c);
            });

            const volumeIds = Object.keys(volumeMap)
              .map((v) => parseInt(v, 10))
              .sort((a, b) => a - b);

            return (
              <Collapse accordion>
                {volumeIds.map((volId) => {
                  const vols = volumeMap[volId];
                  const first = vols[0].chapter_num;
                  const last = vols[vols.length - 1].chapter_num;
                  return (
                    <Panel
                      key={`vol-${volId}`}
                      header={
                        <Space style={{ width: "100%", justifyContent: "space-between" }}>
                          <Space>
                            <BookOutlined />
                            <span>第 {volId} 卷</span>
                            <Text type="secondary">
                              （第 {first} 章 - 第 {last} 章，共 {vols.length} 章）
                            </Text>
                          </Space>
                          <Space>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              卷进度: {Math.round((vols.filter((x) => x.status === 'approved').length / vols.length) * 100)}%
                            </Text>
                          </Space>
                        </Space>
                      }
                    >
                      {/* 每个卷内部的章节列表，使用内嵌 Collapse 保持行为一致 */}
                      <Collapse accordion>
                        {vols.map((c) => (
                          <Panel
                            key={`ch-${c.chapter_num}`}
                            header={
                              <Space style={{ width: "100%", justifyContent: "space-between" }}>
                                <Space>
                                  <Badge
                                    status={
                                      c.status === "approved"
                                        ? "success"
                                        : c.status === "draft"
                                        ? "processing"
                                        : "default"
                                    }
                                  />
                                  <span>第 {c.chapter_num} 章</span>
                                  <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
                                    {c.title || c.preview || "—"}
                                  </Text>
                                </Space>
                                <Space>
                                  <Tag color={labels.statusTone(c.status)}>
                                    {labels.status(c.status)}
                                  </Tag>
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    {c.word_count}字
                                  </Text>
                                </Space>
                              </Space>
                            }
                            onClick={() =>
                              setActiveChapter(
                                activeChapter === c.chapter_num ? null : c.chapter_num
                              )
                            }
                          >
                            {activeChapter === c.chapter_num && (
                              <ChapterDetail
                                novelId={novelId}
                                chapterNum={c.chapter_num}
                                onClose={() => setActiveChapter(null)}
                              />
                            )}
                          </Panel>
                        ))}
                      </Collapse>
                    </Panel>
                  );
                })}
              </Collapse>
            );
          })()
        )}
      </Card>
    </Space>
  );
}
