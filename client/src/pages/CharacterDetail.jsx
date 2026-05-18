import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  Image,
  Modal,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";

import { api } from "../api/client";
import VisualGenerationForm from "../components/VisualGenerationForm";

const { Title, Text } = Typography;
const DEFAULT_PROMPT = "角色人像，高细节，电影级光影";
const DEFAULT_IMAGE_PRESET = "720p";
const DEFAULT_ASPECT_RATIO = "16:9";
const DESKTOP_DISPLAY_HEIGHT = "clamp(220px, 22vw, 360px)";
const MAIN_DISPLAY_HEIGHT = "clamp(300px, 34vw, 560px)";
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

// 主形象编辑面板
function MainImageSection({ profile, loading, onGenerate }) {
  const [showForm, setShowForm] = useState(false);
  const [prompt, setPrompt] = useState(profile?.main_image?.prompt || DEFAULT_PROMPT);
  const [style, setStyle] = useState(profile?.main_image?.style || "");
  const [imagePreset, setImagePreset] = useState(profile?.main_image?.image_preset || DEFAULT_IMAGE_PRESET);
  const [aspectRatio, setAspectRatio] = useState(profile?.main_image?.aspect_ratio || DEFAULT_ASPECT_RATIO);

  const handleGenerate = async () => {
    const success = await onGenerate("main", {
      prompt: prompt || DEFAULT_PROMPT,
      style,
      image_preset: imagePreset,
      aspect_ratio: aspectRatio,
    });
    if (success) {
      setShowForm(false);
    }
  };

  return (
    <Card title="主形象">
      {profile?.main_image ? (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={10}>
              <div
                style={{
                  width: "100%",
                  height: MAIN_DISPLAY_HEIGHT,
                  background: "#f7f7f7",
                  borderRadius: 8,
                  overflow: "hidden",
                }}
              >
                <Image
                  src={profile.main_image.url}
                  alt="main"
                  style={{
                    objectFit: "contain",
                    width: "100%",
                    height: "100%",
                  }}
                  preview={{ mask: "预览" }}
                />
              </div>
            </Col>
            <Col xs={24} md={14}>
              <Space direction="vertical" style={{ width: "100%" }}>
                <div>
                  <Text strong>提示词</Text>
                  <br />
                  <Text>{profile.main_image.prompt || "-"}</Text>
                </div>
                <Space wrap size={[6, 6]}>
                  <Tag>{profile.main_image.image_preset || DEFAULT_IMAGE_PRESET}</Tag>
                  <Tag>{profile.main_image.aspect_ratio || DEFAULT_ASPECT_RATIO}</Tag>
                  {profile.main_image.size ? <Tag>{profile.main_image.size}</Tag> : null}
                </Space>
                <Text type="secondary">生成时间：{profile.main_image.generated_at || "-"}</Text>
                {!showForm && (
                  <Button
                    icon={<SyncOutlined />}
                    onClick={() => setShowForm(true)}
                    loading={loading}
                  >
                    重生成主形象
                  </Button>
                )}
              </Space>
            </Col>
          </Row>

          {showForm && (
            <Divider style={{ margin: "16px 0" }} />
          )}

          {showForm && (
            <Space direction="vertical" style={{ width: "100%" }}>
              <VisualGenerationForm
                prompt={prompt}
                setPrompt={setPrompt}
                style={style}
                setStyle={setStyle}
                imagePreset={imagePreset}
                setImagePreset={setImagePreset}
                aspectRatio={aspectRatio}
                setAspectRatio={setAspectRatio}
                loading={loading}
                showActions
                submitText="确认重生成"
                onSubmit={handleGenerate}
                onCancel={() => setShowForm(false)}
              />
            </Space>
          )}
        </Space>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Empty description="尚未生成主形象" />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowForm(true)}
          >
            生成主形象
          </Button>

          {showForm && (
            <VisualGenerationForm
              prompt={prompt}
              setPrompt={setPrompt}
              style={style}
              setStyle={setStyle}
              imagePreset={imagePreset}
              setImagePreset={setImagePreset}
              aspectRatio={aspectRatio}
              setAspectRatio={setAspectRatio}
              loading={loading}
              showActions
              submitText="生成主形象"
              onSubmit={handleGenerate}
              onCancel={() => setShowForm(false)}
            />
          )}
        </Space>
      )}
    </Card>
  );
}

// 艺术照编辑面板
function GalleryImagesSection({ profile, loading, onGenerate }) {
  const [showForm, setShowForm] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("");
  const [imagePreset, setImagePreset] = useState(DEFAULT_IMAGE_PRESET);
  const [aspectRatio, setAspectRatio] = useState(DEFAULT_ASPECT_RATIO);

  const handleGenerate = async () => {
    const success = await onGenerate("gallery", {
      prompt: prompt || DEFAULT_PROMPT,
      style,
      image_preset: imagePreset,
      aspect_ratio: aspectRatio,
      index: editIndex,
    });
    if (success) {
      resetForm();
    }
  };

  const resetForm = () => {
    setShowForm(false);
    setEditIndex(null);
    setPrompt("");
    setStyle("");
    setImagePreset(DEFAULT_IMAGE_PRESET);
    setAspectRatio(DEFAULT_ASPECT_RATIO);
  };

  const images = profile?.gallery_images || [];

  return (
    <Card
      title={`艺术照 (${images.length})`}
      extra={
        <Text type="secondary">平铺展示，点击卡片按钮可编辑</Text>
      }
    >
      {images.length === 0 ? (
        <Empty description="尚未生成艺术照" />
      ) : null}

      <Row gutter={[16, 16]}>
        {images.map((img, idx) => (
          <Col xs={24} sm={12} lg={8} key={img.id || idx}>
            <Card
              size="small"
              cover={
                <div
                  style={{
                    width: "100%",
                    height: DESKTOP_DISPLAY_HEIGHT,
                    background: "#f7f7f7",
                    overflow: "hidden",
                  }}
                >
                  <Image
                    src={img.url}
                    alt={img.prompt || "gallery-image"}
                    style={{
                      objectFit: "contain",
                      width: "100%",
                      height: "100%",
                    }}
                    preview={{ mask: "预览" }}
                  />
                </div>
              }
            >
              <Space direction="vertical" size={6} style={{ width: "100%" }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {img.generated_at || ""}
                </Text>
                <Text ellipsis={{ tooltip: img.prompt }}>
                  {img.prompt || "-"}
                </Text>
                <Space wrap size={[6, 6]}>
                  <Tag>{img.image_preset || DEFAULT_IMAGE_PRESET}</Tag>
                  <Tag>{img.aspect_ratio || DEFAULT_ASPECT_RATIO}</Tag>
                </Space>
                <Button
                  icon={<SyncOutlined />}
                  onClick={() => {
                    setEditIndex(idx);
                    setPrompt(img.prompt || "");
                    setStyle(img.style || "");
                    setImagePreset(img.image_preset || DEFAULT_IMAGE_PRESET);
                    setAspectRatio(img.aspect_ratio || DEFAULT_ASPECT_RATIO);
                    setShowForm(true);
                  }}
                  block
                  size="small"
                >
                  重生成
                </Button>
              </Space>
            </Card>
          </Col>
        ))}

        <Col xs={24} sm={12} lg={8}>
          <Card
            size="small"
            hoverable
            style={{ height: "100%" }}
            bodyStyle={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 240 }}
            onClick={() => {
              setEditIndex(null);
              setPrompt("");
              setStyle("");
              setImagePreset(DEFAULT_IMAGE_PRESET);
              setAspectRatio(DEFAULT_ASPECT_RATIO);
              setShowForm(true);
            }}
          >
            <Space direction="vertical" align="center" size={8}>
              <PlusOutlined style={{ fontSize: 24 }} />
              <Text>新增艺术照</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Modal
        title={editIndex !== null ? `编辑艺术照 #${editIndex + 1}` : "新增艺术照"}
        open={showForm}
        onCancel={resetForm}
        onOk={handleGenerate}
        confirmLoading={loading}
        okText={editIndex !== null ? "确认重生成" : "新增艺术照"}
        cancelText="取消"
        destroyOnClose
      >
        <VisualGenerationForm
          prompt={prompt}
          setPrompt={setPrompt}
          style={style}
          setStyle={setStyle}
          imagePreset={imagePreset}
          setImagePreset={setImagePreset}
          aspectRatio={aspectRatio}
          setAspectRatio={setAspectRatio}
          promptLabel="提示词（若为空则基于主形象自动生成）"
          promptPlaceholder="留空表示继承主形象特征"
          stylePlaceholder="例如：特定场景 / 衣着风格"
        />
      </Modal>
    </Card>
  );
}

// 视频立体图编辑面板
function VideoImagesSection({ profile, loading, onGenerate }) {
  const [showForm, setShowForm] = useState(false);
  const [editIndex, setEditIndex] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("");
  const [imagePreset, setImagePreset] = useState(DEFAULT_IMAGE_PRESET);
  const [aspectRatio, setAspectRatio] = useState(DEFAULT_ASPECT_RATIO);
  const [regenerateAll, setRegenerateAll] = useState(false);

  const handleGenerate = async () => {
    const success = await onGenerate("video", {
      prompt: prompt || DEFAULT_PROMPT,
      style,
      image_preset: imagePreset,
      aspect_ratio: aspectRatio,
      index: regenerateAll ? null : editIndex,
      regenerate_all: regenerateAll,
    });
    if (success) {
      resetForm();
    }
  };

  const resetForm = () => {
    setShowForm(false);
    setEditIndex(null);
    setPrompt("");
    setStyle("");
    setImagePreset(DEFAULT_IMAGE_PRESET);
    setAspectRatio(DEFAULT_ASPECT_RATIO);
    setRegenerateAll(false);
  };

  const images = profile?.video_images || [];

  return (
    <Card
      title={`视频立体图 (${images.length})`}
      extra={
        !showForm && (
          <Space size={8}>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                setRegenerateAll(true);
                setShowForm(true);
              }}
              size="small"
            >
              全量重生成
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={() => {
                setRegenerateAll(false);
                setEditIndex(null);
                setShowForm(true);
              }}
              size="small"
            >
              新增
            </Button>
          </Space>
        )
      }
    >
      {showForm && (
        <Card
          type="inner"
          title={regenerateAll ? "全量重生成视频立体图" : editIndex !== null ? `编辑第 ${editIndex + 1} 张` : "新增视频立体图"}
          extra={<Button type="text" onClick={resetForm} size="small">关闭</Button>}
          style={{ marginBottom: 16 }}
        >
          <VisualGenerationForm
            prompt={prompt}
            setPrompt={setPrompt}
            style={style}
            setStyle={setStyle}
            imagePreset={imagePreset}
            setImagePreset={setImagePreset}
            aspectRatio={aspectRatio}
            setAspectRatio={setAspectRatio}
            promptLabel="提示词（若为空则基于主形象自动生成）"
            promptPlaceholder="留空表示继承主形象特征"
            stylePlaceholder="例如：特定镜头角度 / 光线条件"
            hidePrompt={regenerateAll}
            hideStyle={regenerateAll}
            extraTop={
              regenerateAll ? (
                <Alert
                  message="全量重生成将生成 5 张全方位立体图（正面、侧面、背面、斜45°、脸部特写），替换所有现有图片"
                  type="info"
                  style={{ marginBottom: 16 }}
                />
              ) : null
            }
            loading={loading}
            showActions
            submitText={regenerateAll ? "全量重生成" : editIndex !== null ? "确认重生成" : "新增"}
            onSubmit={handleGenerate}
            onCancel={resetForm}
          />
        </Card>
      )}

      {images.length === 0 ? (
        <Empty description="尚未生成视频立体图" />
      ) : (
        <Row gutter={[16, 16]}>
          {images.map((img, idx) => (
            <Col xs={24} sm={12} lg={8} key={img.id || idx}>
              <Card
                size="small"
                cover={
                  <div
                    style={{
                      width: "100%",
                      height: DESKTOP_DISPLAY_HEIGHT,
                      background: "#f7f7f7",
                      overflow: "hidden",
                    }}
                  >
                    <Image
                      src={img.url}
                      alt={`video-${idx}`}
                      style={{
                        objectFit: "contain",
                        width: "100%",
                        height: "100%",
                      }}
                      preview={{ mask: "预览" }}
                    />
                  </div>
                }
              >
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {img.generated_at || ""}
                  </Text>
                  <Text ellipsis={{ tooltip: img.prompt }}>
                    {img.prompt || "-"}
                  </Text>
                  <Space wrap size={[6, 6]}>
                    <Tag>{img.image_preset || DEFAULT_IMAGE_PRESET}</Tag>
                    <Tag>{img.aspect_ratio || DEFAULT_ASPECT_RATIO}</Tag>
                  </Space>
                  <Button
                    icon={<SyncOutlined />}
                    onClick={() => {
                      setEditIndex(idx);
                      setPrompt(img.prompt || "");
                      setStyle(img.style || "");
                      setImagePreset(img.image_preset || DEFAULT_IMAGE_PRESET);
                      setAspectRatio(img.aspect_ratio || DEFAULT_ASPECT_RATIO);
                      setRegenerateAll(false);
                      setShowForm(true);
                    }}
                    block
                    size="small"
                  >
                    重生成
                  </Button>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </Card>
  );
}

export default function CharacterDetail() {
  const { novelId, characterId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [novel, setNovel] = useState(null);
  const [character, setCharacter] = useState(location.state?.character || null);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      api.getNovel(novelId),
      api.getCharacterVisuals(novelId, characterId),
    ])
      .then(([n, visualRes]) => {
        setNovel(n);
        setProfile(visualRes.profile || null);

        const found = (n.characters || []).find((c) => {
          const cid = String(c.character_id || c.id || "").trim();
          const cname = String(c.name || "").trim();
          return cid === characterId || cname === characterId;
        });

        const nextCharacter = found || location.state?.character || null;
        setCharacter(nextCharacter);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [novelId, characterId, location.state]);

  const characterName = useMemo(() => {
    if (character?.name) return character.name;
    if (profile?.character_name) return profile.character_name;
    return characterId;
  }, [character, profile, characterId]);

  const doGenerate = async (slotType, params = {}) => {
    setSaving(true);
    try {
      const submit = await api.generateCharacterVisual(novelId, characterId, {
        prompt: params.prompt || "",
        slot_type: slotType,
        style: params.style || "",
        index: params.index,
        image_preset: params.image_preset || DEFAULT_IMAGE_PRESET,
        aspect_ratio: params.aspect_ratio || DEFAULT_ASPECT_RATIO,
        regenerate_all: params.regenerate_all || false,
      });

      const taskId = submit?.task_id;
      if (!taskId) {
        throw new Error("后端未返回任务ID");
      }

      const task = await waitForTask(taskId);
      if (task.status !== "success") {
        throw new Error(task.error || "图片任务执行失败");
      }

      const latest = await api.getCharacterVisuals(novelId, characterId);
      setProfile(latest.profile || null);
      message.success("生成成功");
      return true;
    } catch (err) {
      message.error(`生成失败: ${err.message}`);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const toggleFinalize = async () => {
    setSaving(true);
    try {
      const target = !profile?.finalized;
      const res = await api.finalizeCharacterVisuals(novelId, characterId, target);
      setProfile(res.profile || null);
      message.success(target ? "已设为定稿" : "已取消定稿");
    } catch (err) {
      message.error(`操作失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 40 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Space direction="vertical" style={{ width: "100%" }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Alert type="error" message="加载失败" description={error} />
      </Space>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
        返回小说详情
      </Button>

      <Card>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Space align="center" style={{ justifyContent: "space-between", width: "100%" }}>
            <Title level={3} style={{ margin: 0 }}>
              {characterName}
            </Title>
            {profile?.finalized ? (
              <Tag color="success" icon={<CheckCircleOutlined />}>
                已定稿
              </Tag>
            ) : (
              <Tag color="processing">草稿中</Tag>
            )}
          </Space>

          <Text type="secondary">
            {novel?.novel_title || location.state?.novelTitle || novelId}
          </Text>

          <Descriptions size="small" column={3}>
            <Descriptions.Item label="性别">{character?.gender || "-"}</Descriptions.Item>
            <Descriptions.Item label="年龄">
              {character?.age ? `${character.age}岁` : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="角色类型">{character?.role || "-"}</Descriptions.Item>
          </Descriptions>

          <Text>{character?.personality || character?.description || "暂无角色描述"}</Text>
        </Space>
      </Card>

      <MainImageSection
        profile={profile}
        loading={saving}
        onGenerate={doGenerate}
      />

      <GalleryImagesSection
        profile={profile}
        loading={saving}
        onGenerate={doGenerate}
      />

      <VideoImagesSection
        profile={profile}
        loading={saving}
        onGenerate={doGenerate}
      />

      <Card>
        <Space wrap>
          <Button
            type={profile?.finalized ? "default" : "dashed"}
            onClick={toggleFinalize}
            loading={saving}
          >
            {profile?.finalized ? "取消定稿" : "设为定稿"}
          </Button>
        </Space>
      </Card>

      <Divider />
    </Space>
  );
}
