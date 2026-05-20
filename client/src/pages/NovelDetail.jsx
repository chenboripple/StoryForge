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
  Statistic,
  Divider,
  Tooltip,
  Image,
  Modal,
  message,
  Select,
  InputNumber,
} from "antd";
import {
  ArrowLeftOutlined,
  PlayCircleOutlined,
  UserOutlined,
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  PictureOutlined,
  SyncOutlined,
  EditOutlined,
  SafetyOutlined,
} from "@ant-design/icons";

import { api, labels } from "../api/client";
import VisualGenerationForm from "../components/VisualGenerationForm";

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;
const DEFAULT_PROMPT = "小说封面，电影海报风格，高细节";
const DEFAULT_IMAGE_PRESET = "1080p";
const DEFAULT_ASPECT_RATIO = "3:4";
const TASK_POLL_INTERVAL_MS = 1200;
const TASK_MAX_POLLS = 150;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForTask(taskId) {
  for (let i = 0; i < TASK_MAX_POLLS; i += 1) {
    const task = await api.getTask(taskId);
    if (["success", "failed", "cancelled", "stopped"].includes(task.status)) {
      return task;
    }
    await sleep(TASK_POLL_INTERVAL_MS);
  }
  throw new Error("任务执行超时，请稍后重试");
}

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
  const [novelContext, setNovelContext] = useState(null);
  const [characterThumbs, setCharacterThumbs] = useState({});
  const [error, setError] = useState(null);
  const [activeChapter, setActiveChapter] = useState(null);
  const [cover, setCover] = useState(null);
  const [coverModalOpen, setCoverModalOpen] = useState(false);
  const [coverSaving, setCoverSaving] = useState(false);
  const [coverDrafting, setCoverDrafting] = useState(false);
  const [coverDraftFeedback, setCoverDraftFeedback] = useState(null);
  const [coverDraftCollaboration, setCoverDraftCollaboration] = useState(null);
  const [coverPrompt, setCoverPrompt] = useState(DEFAULT_PROMPT);
  const [coverStyle, setCoverStyle] = useState("");
  const [coverImagePreset, setCoverImagePreset] = useState(DEFAULT_IMAGE_PRESET);
  const [coverAspectRatio, setCoverAspectRatio] = useState(DEFAULT_ASPECT_RATIO);
  const [chapterActionLoading, setChapterActionLoading] = useState(false);
  const [proofreadScope, setProofreadScope] = useState("chapter");
  const [proofreadChapterNum, setProofreadChapterNum] = useState(null);
  const [proofreadVolumeNum, setProofreadVolumeNum] = useState(null);

  const refreshNovelData = async () => {
    const [n, c, ctx] = await Promise.all([
      api.getNovel(novelId),
      api.listChapters(novelId),
      api.getNovelContext(novelId).catch(() => null),
    ]);
    setNovel(n);
    setChapters(c.chapters || []);
    setNovelContext(ctx);
  };

  useEffect(() => {
    setNovel(null);
    setChapters(null);
    setNovelContext(null);
    setCharacterThumbs({});
    setError(null);
    refreshNovelData()
      .catch((err) => setError(err.message));
  }, [novelId]);

  useEffect(() => {
    let disposed = false;
    api
      .getNovelCover(novelId)
      .then((res) => {
        if (disposed) return;
        setCover(res || null);
        if (res?.cover_image?.prompt) {
          setCoverPrompt(res.cover_image.prompt);
        }
        if (res?.cover_image?.style) {
          setCoverStyle(res.cover_image.style);
        }
        if (res?.cover_image?.image_preset) {
          setCoverImagePreset(res.cover_image.image_preset);
        }
        if (res?.cover_image?.aspect_ratio) {
          setCoverAspectRatio(res.cover_image.aspect_ratio);
        }
      })
      .catch(() => {
        if (disposed) return;
        setCover(null);
      });

    return () => {
      disposed = true;
    };
  }, [novelId]);

  const doGenerateCover = async () => {
    setCoverSaving(true);
    try {
      const submit = await api.generateNovelCover(novelId, {
        prompt: (coverPrompt || "").trim() || `${novel?.novel_title || novelId} ${DEFAULT_PROMPT}`,
        style: coverStyle || "",
        image_preset: coverImagePreset || DEFAULT_IMAGE_PRESET,
        aspect_ratio: coverAspectRatio || DEFAULT_ASPECT_RATIO,
      });

      const taskId = submit?.task_id;
      if (!taskId) {
        throw new Error("后端未返回任务ID");
      }

      const task = await waitForTask(taskId);
      if (task.status !== "success") {
        throw new Error(task.error || "封面任务执行失败");
      }

      const latest = await api.getNovelCover(novelId);
      setCover(latest || null);
      setCoverModalOpen(false);
      message.success("封面生成成功");
    } catch (err) {
      message.error(`封面生成失败: ${err.message}`);
    } finally {
      setCoverSaving(false);
    }
  };

  const doSuggestCoverPrompt = async () => {
    setCoverDrafting(true);
    try {
      const res = await api.suggestNovelCoverPrompt(novelId, {
        prompt: (coverPrompt || "").trim(),
        style: coverStyle || "",
      });
      const suggested = String(res?.suggested_prompt || "").trim();
      if (!suggested) {
        throw new Error("后端未返回提示词草稿");
      }
      setCoverPrompt(suggested);
      setCoverDraftFeedback(res?.structured_feedback || null);
      setCoverDraftCollaboration(res?.collaboration || null);
      message.success("已生成封面提示词草稿，请确认后提交生成");
    } catch (err) {
      message.error(`生成封面提示词草稿失败: ${err.message}`);
    } finally {
      setCoverDrafting(false);
    }
  };

  const runChapterTask = async (submitter, successText) => {
    if (!novelId) return;
    setChapterActionLoading(true);
    try {
      const submit = await submitter();
      const taskId = submit?.task_id;
      if (!taskId) {
        throw new Error("后端未返回任务ID");
      }

      const task = await waitForTask(taskId);
      if (task.status !== "success") {
        throw new Error(task.error || "章节生成失败");
      }

      await refreshNovelData();
      message.success(successText || "章节任务完成");
    } catch (err) {
      message.error(`章节任务失败: ${err.message}`);
    } finally {
      setChapterActionLoading(false);
    }
  };

  const doGenerateNextChapter = async () => {
    await runChapterTask(
      () => api.generateNextChapter(novelId),
      `已提交并完成第 ${novel?.current_chapter || 1} 章生成`
    );
  };

  const doReviseCurrentChapter = async () => {
    const latestChapterNum = (chapters || []).reduce(
      (acc, x) => Math.max(acc, Number(x.chapter_num || 0)),
      0
    );
    if (!latestChapterNum) {
      message.warning("暂无可修改章节，请先生成章节");
      return;
    }

    await runChapterTask(
      () => api.reviseChapter(novelId, latestChapterNum),
      `第 ${latestChapterNum} 章已按当前设定重新生成`
    );
  };

  const doProofreadRange = async () => {
    const payload = { scope: proofreadScope };
    if (proofreadScope === "chapter") {
      const latestChapterNum = (chapters || []).reduce(
        (acc, x) => Math.max(acc, Number(x.chapter_num || 0)),
        0
      );
      payload.chapter_num = Number(proofreadChapterNum || latestChapterNum || 0);
      if (!payload.chapter_num) {
        message.warning("没有可校对章节");
        return;
      }
    }
    if (proofreadScope === "volume") {
      const latestChapterNum = (chapters || []).reduce(
        (acc, x) => Math.max(acc, Number(x.chapter_num || 0)),
        0
      );
      const defaultVolume = latestChapterNum ? Math.floor((latestChapterNum - 1) / 10) + 1 : 1;
      payload.volume_num = Number(proofreadVolumeNum || defaultVolume || 1);
    }

    await runChapterTask(
      () => api.proofreadChapters(novelId, payload),
      "指定范围校对完成"
    );
  };

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
          return [cid, main?.local_url || main?.thumb_url || main?.url || ""];
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
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/novels")}>
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

  const toCharacterId = (c) => {
    const raw = c?.character_id || c?.id || c?.name || "unknown";
    return String(raw).trim() || "unknown";
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 返回按钮 */}
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/novels")}>
        返回清单
      </Button>

      <Card>
        <Row gutter={[20, 20]} align="top">
          <Col xs={24} sm={10} md={8} lg={6}>
            <div style={{ maxWidth: 220, width: "100%" }}>
              {cover?.cover_image ? (
                <>
                  <div
                    style={{
                      width: "100%",
                      aspectRatio: "3 / 4",
                      background: "#f7f7f7",
                      borderRadius: 8,
                      overflow: "hidden",
                    }}
                  >
                    <Image
                      src={cover.cover_image.local_url || cover.cover_image.url}
                      alt="novel-cover"
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      preview={{ mask: "预览" }}
                    />
                  </div>
                  <Space wrap size={[6, 6]} style={{ marginTop: 8 }}>
                    <Tag>{cover.cover_image.image_preset || DEFAULT_IMAGE_PRESET}</Tag>
                    <Tag>{cover.cover_image.aspect_ratio || DEFAULT_ASPECT_RATIO}</Tag>
                  </Space>
                </>
              ) : (
                <div
                  style={{
                    width: "100%",
                    aspectRatio: "3 / 4",
                    border: "1px dashed #d9d9d9",
                    borderRadius: 8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "#fafafa",
                  }}
                >
                  <Text type="secondary">暂无封面</Text>
                </div>
              )}
            </div>
          </Col>
          <Col xs={24} sm={14} md={16} lg={18}>
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
              <Row justify="space-between" align="top" gutter={[12, 12]}>
                <Col flex="auto">
                  <Space>
                    <Tag color="blue">{novel.genre || "未分类"}</Tag>
                    <Tag>{labels.stage(novel.current_stage)}</Tag>
                  </Space>
                  <Title level={3} style={{ margin: "8px 0 0 0" }}>
                    {novel.novel_title || "未命名"}
                  </Title>
                </Col>
                <Col>
                  <Button
                    type={cover?.cover_image ? "default" : "primary"}
                    icon={cover?.cover_image ? <SyncOutlined /> : <PictureOutlined />}
                    onClick={() => setCoverModalOpen(true)}
                  >
                    {cover?.cover_image ? "重生成封面" : "生成封面"}
                  </Button>
                </Col>
              </Row>

              <Paragraph type="secondary" ellipsis={{ rows: 4 }}>
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

              <Collapse ghost>
                <Panel header="novel.json（全书总纲）" key="novel-doc">
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Space wrap>
                      <Tag color="blue">类型：{novelContext?.novel_doc?.genre || novel.genre || "未分类"}</Tag>
                      <Tag>目标字数：{novelContext?.novel_doc?.target_word_count || novel.target_word_count || 0}</Tag>
                      <Tag>卷数：{novelContext?.novel_doc?.volume_count || 0}</Tag>
                      <Tag>阶段：{labels.stage(novelContext?.novel_doc?.current_stage || novel.current_stage)}</Tag>
                    </Space>
                    {novelContext?.novel_doc?.logline ? (
                      <>
                        <Text strong>一句话梗概</Text>
                        <Paragraph style={{ whiteSpace: "pre-wrap" }}>
                          {novelContext.novel_doc.logline}
                        </Paragraph>
                      </>
                    ) : null}
                    <Text strong>核心概念</Text>
                    <Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {novelContext?.novel_doc?.concept || novel.concept || "暂无核心概念"}
                    </Paragraph>
                    <Text strong>全书总纲</Text>
                    <Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {novelContext?.novel_doc?.overall_outline || novelContext?.outline?.overall_outline || "暂无总纲"}
                    </Paragraph>
                    {(novelContext?.novel_doc?.themes || []).length > 0 ? (
                      <Space wrap>
                        {(novelContext?.novel_doc?.themes || []).map((t, idx) => (
                          <Tag key={`theme-${idx}`}>{t}</Tag>
                        ))}
                      </Space>
                    ) : null}
                  </Space>
                </Panel>

                <Panel header="world.json（世界观）" key="world-doc">
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Text strong>世界观</Text>
                    <Paragraph style={{ whiteSpace: "pre-wrap" }}>
                      {novelContext?.world_doc?.overview || novelContext?.world?.overview || "暂无世界观信息"}
                    </Paragraph>
                    {Array.isArray(novelContext?.world_doc?.rules) && novelContext.world_doc.rules.length > 0 ? (
                      <Space wrap>
                        {novelContext.world_doc.rules.map((rule, idx) => (
                          <Tag key={`rule-${idx}`}>{rule}</Tag>
                        ))}
                      </Space>
                    ) : null}
                    <Space wrap>
                      <Tag>地点数：{novelContext?.world_doc?.location_count || 0}</Tag>
                      <Tag>势力数：{novelContext?.world_doc?.faction_count || 0}</Tag>
                      {novelContext?.world_doc?.technology_level ? (
                        <Tag>科技：{novelContext.world_doc.technology_level}</Tag>
                      ) : null}
                      {novelContext?.world_doc?.magic_system ? (
                        <Tag>体系：{novelContext.world_doc.magic_system}</Tag>
                      ) : null}
                    </Space>
                  </Space>
                </Panel>

                <Panel header="foreshadowing.json（伏笔体系）" key="foreshadowing-doc">
                  <Space direction="vertical" style={{ width: "100%" }}>
                    <Space wrap>
                      <Tag color="blue">总数：{novelContext?.foreshadowing_doc?.total || 0}</Tag>
                      <Tag color="green">已回收：{novelContext?.foreshadowing_doc?.resolved || 0}</Tag>
                      <Tag color="orange">未回收：{novelContext?.foreshadowing_doc?.open || 0}</Tag>
                    </Space>
                    {(novelContext?.foreshadowing_doc?.items || []).length > 0 ? (
                      <List
                        size="small"
                        dataSource={novelContext.foreshadowing_doc.items}
                        renderItem={(item) => (
                          <List.Item>
                            <Space direction="vertical" size={2} style={{ width: "100%" }}>
                              <Space>
                                <Text strong>{item.foreshadowing_id}</Text>
                                <Tag color={item.status === "resolved" ? "green" : "orange"}>
                                  {item.status === "resolved" ? "已回收" : "未回收"}
                                </Tag>
                              </Space>
                              <Text>{item.content}</Text>
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                埋设章节：{(item.set_in_chapters || []).join(",") || "-"}；
                                回收章节：{(item.resolved_in_chapters || []).join(",") || "-"}
                              </Text>
                            </Space>
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无伏笔数据" />
                    )}
                  </Space>
                </Panel>

                <Panel header="volX.json（卷纲）" key="volumes-doc">
                  {(novelContext?.volumes_doc?.volumes || []).length > 0 ? (
                    <Collapse accordion>
                      {novelContext.volumes_doc.volumes.map((vol) => (
                        <Panel
                          key={`vol-plan-${vol.volume_num}`}
                          header={`第 ${vol.volume_num} 卷 · ${vol.title || "未命名卷"}`}
                        >
                          <Space direction="vertical" style={{ width: "100%" }}>
                            {vol.theme ? <Text>主题：{vol.theme}</Text> : null}
                            {vol.chapter_range ? <Text>章节范围：{vol.chapter_range}</Text> : null}
                            {vol.summary ? (
                              <Paragraph style={{ whiteSpace: "pre-wrap" }}>{vol.summary}</Paragraph>
                            ) : null}
                            {(vol.key_events || []).length > 0 ? (
                              <>
                                <Text strong>关键事件</Text>
                                <List
                                  size="small"
                                  dataSource={vol.key_events}
                                  renderItem={(evt, idx) => <List.Item key={`vol-${vol.volume_num}-evt-${idx}`}>{evt}</List.Item>}
                                />
                              </>
                            ) : null}
                          </Space>
                        </Panel>
                      ))}
                    </Collapse>
                  ) : (
                    <Empty description="暂无卷纲数据" />
                  )}
                </Panel>

                <Panel header="时间线" key="timeline">
                  {Array.isArray(novelContext?.timeline) && novelContext.timeline.length > 0 ? (
                    <List
                      size="small"
                      dataSource={novelContext.timeline}
                      renderItem={(evt, idx) => (
                        <List.Item key={`tl-${idx}`}>
                          <Space direction="vertical" size={0}>
                            <Text strong>
                              第 {evt.chapter || "-"} 章 {evt.timestamp ? `· ${evt.timestamp}` : ""}
                            </Text>
                            <Text type="secondary">{evt.description || "(无描述)"}</Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="暂无时间线" />
                  )}
                </Panel>
              </Collapse>
            </Space>
          </Col>
        </Row>
      </Card>

      <Modal
        title={cover?.cover_image ? "重生成小说封面" : "生成小说封面"}
        open={coverModalOpen}
        onCancel={() => setCoverModalOpen(false)}
        destroyOnClose
        footer={null}
      >
        <VisualGenerationForm
          prompt={coverPrompt}
          setPrompt={setCoverPrompt}
          style={coverStyle}
          setStyle={setCoverStyle}
          imagePreset={coverImagePreset}
          setImagePreset={setCoverImagePreset}
          aspectRatio={coverAspectRatio}
          setAspectRatio={setCoverAspectRatio}
          promptLabel="封面提示词"
          promptPlaceholder={`${novel?.novel_title || "小说"} ${DEFAULT_PROMPT}`}
          stylePlaceholder="例如：暗黑奇幻 / 水彩插画 / 赛博朋克"
          loading={coverSaving}
          extraTop={coverDraftFeedback ? (
            <Alert
              type="info"
              showIcon
              message="AI 草稿已融合 writer/校对反馈"
              description={
                <div>
                  {(coverDraftFeedback.narrative_conflicts || []).slice(0, 1).map((x, i) => <div key={`n-${i}`}>叙事冲突: {x}</div>)}
                  {(coverDraftFeedback.consistency_constraints || []).slice(0, 1).map((x, i) => <div key={`c-${i}`}>一致性约束: {x}</div>)}
                  {(coverDraftFeedback.taboo_elements || []).slice(0, 1).map((x, i) => <div key={`t-${i}`}>禁忌元素: {x}</div>)}
                  {(coverDraftFeedback.style_notes || []).slice(0, 1).map((x, i) => <div key={`s-${i}`}>风格备注: {x}</div>)}
                  {coverDraftCollaboration?.writer ? <div>作者意见: {coverDraftCollaboration.writer}</div> : null}
                  {coverDraftCollaboration?.editor ? <div>编辑意见: {coverDraftCollaboration.editor}</div> : null}
                  {coverDraftCollaboration?.art_director ? <div>原画结论: {coverDraftCollaboration.art_director}</div> : null}
                  {coverDraftCollaboration?.weights ? <div>协商权重: {coverDraftCollaboration.weights}</div> : null}
                </div>
              }
              style={{ marginBottom: 12 }}
            />
          ) : null}
          showActions
          extraActions={(
            <Button onClick={doSuggestCoverPrompt} loading={coverDrafting}>
              AI生成提示词草稿
            </Button>
          )}
          submitText={cover?.cover_image ? "确认重生成" : "生成封面"}
          onSubmit={doGenerateCover}
          onCancel={() => setCoverModalOpen(false)}
        />
      </Modal>

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
      <Card
        title={`章节 (${total})`}
        extra={
          <Space wrap>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={chapterActionLoading}
              onClick={doGenerateNextChapter}
            >
              生成下一章
            </Button>
            <Button
              icon={<EditOutlined />}
              loading={chapterActionLoading}
              onClick={doReviseCurrentChapter}
            >
              修改当前章节
            </Button>
            <Select
              size="middle"
              value={proofreadScope}
              onChange={setProofreadScope}
              style={{ width: 120 }}
              options={[
                { label: "按章节校对", value: "chapter" },
                { label: "按卷校对", value: "volume" },
                { label: "全书校对", value: "book" },
              ]}
            />
            {proofreadScope === "chapter" ? (
              <InputNumber
                min={1}
                placeholder="章节号"
                value={proofreadChapterNum}
                onChange={setProofreadChapterNum}
              />
            ) : null}
            {proofreadScope === "volume" ? (
              <InputNumber
                min={1}
                placeholder="卷号"
                value={proofreadVolumeNum}
                onChange={setProofreadVolumeNum}
              />
            ) : null}
            <Button
              icon={<SafetyOutlined />}
              loading={chapterActionLoading}
              onClick={doProofreadRange}
            >
              校对指定范围
            </Button>
          </Space>
        }
      >
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
