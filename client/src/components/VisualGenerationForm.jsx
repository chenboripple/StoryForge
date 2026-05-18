import React from "react";
import { Button, Col, Form, Input, Row, Select, Space } from "antd";

const DEFAULT_PROMPT = "角色人像，高细节，电影级光影";

const IMAGE_PRESET_OPTIONS = [
  { label: "360p - 手机预览", value: "360p" },
  { label: "540p - 手机高清预览", value: "540p" },
  { label: "720p - 默认网页/手机/轻量平板", value: "720p" },
  { label: "1080p - 常规显示器/平板高清", value: "1080p" },
  { label: "2K - 笔记本高分屏/平板高精", value: "2k" },
  { label: "4K - 大屏显示器/海报", value: "4k" },
];

const ASPECT_RATIO_OPTIONS = [
  { label: "16:9 - 电脑显示器 / 电视 / 多数笔记本", value: "16:9" },
  { label: "16:10 - MacBook Air/Pro / 部分安卓平板横屏", value: "16:10" },
  { label: "21:9 - 带鱼屏显示器", value: "21:9" },
  { label: "4:3 - iPad / iPad Air / iPad Pro", value: "4:3" },
  { label: "3:2 - Surface / 部分生产力平板", value: "3:2" },
  { label: "1:1 - 方图封面 / 社媒头像", value: "1:1" },
  { label: "4:5 - 社媒竖图 / 平板阅读图", value: "4:5" },
  { label: "3:4 - 竖版海报 / 平板竖屏", value: "3:4" },
  { label: "2:3 - 手机壁纸 / 角色立绘", value: "2:3" },
  { label: "5:4 - 老式显示器 / 工控屏", value: "5:4" },
  { label: "9:16 - 安卓手机竖屏 / 短视频封面", value: "9:16" },
  { label: "9:19.5 - iPhone 14/15/16 / 全面屏安卓", value: "9:19.5" },
];

export default function VisualGenerationForm({
  prompt,
  setPrompt,
  style,
  setStyle,
  imagePreset,
  setImagePreset,
  aspectRatio,
  setAspectRatio,
  loading = false,
  promptLabel = "提示词",
  promptPlaceholder = DEFAULT_PROMPT,
  styleLabel = "风格补充（可选）",
  stylePlaceholder = "例如：国风写实 / 赛博朋克",
  hidePrompt = false,
  hideStyle = false,
  extraTop = null,
  showActions = false,
  submitText = "确认",
  cancelText = "取消",
  onSubmit,
  onCancel,
}) {
  return (
    <Form layout="vertical" size="small">
      {extraTop}

      {!hidePrompt && (
        <Form.Item label={promptLabel}>
          <Input.TextArea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder={promptPlaceholder}
          />
        </Form.Item>
      )}

      {!hideStyle && (
        <Form.Item label={styleLabel}>
          <Input
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            placeholder={stylePlaceholder}
          />
        </Form.Item>
      )}

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Form.Item label="图片尺寸">
            <Select
              value={imagePreset}
              onChange={setImagePreset}
              options={IMAGE_PRESET_OPTIONS}
            />
          </Form.Item>
        </Col>
        <Col xs={24} md={12}>
          <Form.Item label="长宽比例">
            <Select
              value={aspectRatio}
              onChange={setAspectRatio}
              options={ASPECT_RATIO_OPTIONS}
            />
          </Form.Item>
        </Col>
      </Row>

      {showActions && (
        <Space wrap>
          <Button type="primary" loading={loading} onClick={onSubmit}>
            {submitText}
          </Button>
          <Button onClick={onCancel}>{cancelText}</Button>
        </Space>
      )}
    </Form>
  );
}
