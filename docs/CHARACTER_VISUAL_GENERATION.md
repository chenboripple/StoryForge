# 角色形象生成系统

## 概述

角色形象生成系统支持生成多种角色形象素材：
- **主形象（main）**：角色的标准设定图，作为后续所有衍生形象的参考基准
- **艺术照（gallery）**：基于主形象生成的不同场景/装束/光影的图片，可多张叠加
- **视频立体图（video）**：全方位 5 张参考图（正面、侧面、背面、斜 45°、脸部特写）

## 工作流程

### 1. 主形象生成（main）
```
用户提示词 → CharacterVisualAgent（文本提示） → 文生图（千问 Token Plan）
     ↓
获得参考图片 → 本地存储 local_path
     ↓
后续 gallery/video 的参考基准
```

### 2. 一致性保证机制（gallery/video）

```
main_image 本地图片 → Vision LLM 读取
     ↓
提取视觉特征（身体、面部、服装、气质等）
     ↓
融合用户提示词 → 文生图
     ↓
同一角色，不同场景/装束/角度
```

**支持的 Vision LLM 客户端：**
- Claude 3.5 Sonnet（via Anthropic）
- GPT-4 Vision（via OpenAI）

### 3. 视频立体图多角度生成（video）

**全量重生成时，自动生成 5 张视图：**
1. **正面 全身** - 标准设定图
2. **侧面 全身** - 人物侧轮廓
3. **背面 全身** - 背部设计细节
4. **斜 45° 全身** - 动态三维感
5. **脸部特写** - 面部细节展示

## 流程约束

### 生成顺序
1. **必须先生成主形象**，gallery/video 才能生成
2. gallery/video 时会自动读取 main_image 的本地图片路径

### 图片管理
- **main** 形象：覆盖式替换，只保留最新一张
- **gallery** 形象：追加式新增，也可重生成某一张
- **video** 形象：
  - "新增"模式：追加一张新图片
  - "重生成"模式：替换某一张已有的图片
  - "全量重生成"模式：清空所有，重新生成 5 张

## 参数说明

### 图片尺寸（image_preset）
| 预设 | 分辨率 | 适用场景 |
|-----|--------|---------|
| 360p | 最小 360px | 手机预览 |
| 540p | 中等 540px | 手机高清 |
| 720p | 标准 720px | 网页/手机/轻量平板 |
| 1080p | 高清 1080px | 显示器/平板 |
| 2K | 极高 2K | 高分屏/高精度 |
| 4K | 超高 4K | 大屏/海报 |

补充说明：

- 配置文件中的 `models[].max_image_size` 表示最大尺寸上限（max cap），不是默认生成尺寸。
- 实际生成尺寸优先由前端选择的 `image_preset + aspect_ratio` 决定，再按 `max_image_size` 上限等比缩放约束。

### 长宽比例（aspect_ratio）
| 比例 | 设备 | 用途 |
|-----|------|------|
| 16:9 | 电脑显示器/电视 | 宽屏 |
| 16:10 | MacBook/安卓平板 | 苹果设备 |
| 21:9 | 带鱼屏显示器 | 超宽屏 |
| 4:3 | iPad | 平板 |
| 3:2 | Surface | 生产力平板 |
| 1:1 | 方形 | 社媒头像/封面 |
| 4:5 | 竖图 | 社媒竖图 |
| 3:4 | 竖版 | 海报/竖屏 |
| 2:3 | 竖屏 | 手机壁纸 |
| 5:4 | 老式显示器 | 工控屏 |
| 9:16 | 安卓手机竖屏 | 短视频 |
| 9:19.5 | iPhone 14+ | 全面屏安卓 |

## 前端交互（当前实现）

### 页面入口

- 小说详情页角色卡片支持点击跳转：
  - 路径：`/novels/{novel_id}/characters/{character_id}`
- 若该角色已生成主形象，角色卡片会显示主图缩略图（否则显示默认头像）。

### 图片展示规则

- 主形象、艺术照、视频立体图使用固定展示位比例（当前为 `3:4`）。
- 真实图片在固定展示位中使用 `contain` 缩放，确保完整显示、不裁切主体。
- 生成参数里的 `image_preset` / `aspect_ratio` 影响生成像素与内容构图，不改变展示位框体大小。

### 艺术照区域

- 采用平铺卡片展示。
- 网格末尾有“新增艺术照”卡片位。
- 新增与重生成都通过弹框编辑参数（提示词、风格、尺寸、比例）。

### 视频立体图区域

- 支持“新增单张”“重生成单张”“全量重生成”三种操作。
- 全量重生成会一次生成固定视角组图。

## API 接口

### 生成角色形象
```http
POST /api/v1/novels/{novel_id}/characters/{character_id}/visuals/generate

Content-Type: application/json
{
  "prompt": "用户自定义提示词",
  "slot_type": "main|gallery|video",
  "style": "风格补充（可选）",
  "index": 1,  // 仅 gallery/video 有效，指定要替换的索引
  "image_preset": "720p",
  "aspect_ratio": "16:9",
  "regenerate_all": false  // 仅 video 有效，若 true 则全量重生成
}
```

### 响应结果
```json
{
  "novel_id": "...",
  "character_id": "...",
  "generated": {
    "id": "img_xxxxx",
    "type": "main|gallery|video",
    "url": "https://...",
    "local_path": "/Users/ripple/novels/.../image.png",
    "prompt": "完整提示词（包含特征提取结果）",
    "style": "风格",
    "size": "1440x1080",
    "aspect_ratio": "16:9",
    "image_preset": "720p",
    "generated_at": "2026-05-16T...",
    "agent": "镜相",
    "provider": "qwen-image"
  },
  "profile": {
    "main_image": {...},
    "gallery_images": [...],
    "video_images": [...]
  }
}
```

## 当前实现方案

### 一致性保证

**方案：Vision LLM 特征提取 + 文本融合**

1. 读取 main_image 本地图片
2. 用 Claude Vision/GPT-4 Vision 分析图片
3. 提取关键视觉特征（以文本形式）
4. 融合进用户提示词
5. 调用文生图 API 生成新图片

**优点：**
- ✅ 完全独立于图生图模型，兼容性强
- ✅ 可精细控制提示词组合
- ✅ 支持多种文生图后端（千问、Stable Diffusion 等）
- ✅ Vision LLM 已广泛可用（Claude、GPT-4）

**缺点：**
- ⚠️ 多一次 API 调用（Vision 提取 + 文生图）
- ⚠️ 文本特征可能丢失细节
- ⚠️ 后续特征融合依赖 LLM 的理解能力

## 未来优化方向

### 方案：Image-to-Image 生成

**替代方案：集成 Stable Diffusion Image-to-Image**

```
main_image 图片 → Image-to-Image 模型（直接传图）
     ↓
结合用户提示词和 strength 参数
     ↓
生成保留原图构图的新图片
```

**优点：**
- ✅ **直接传图片，无需文本提取**
- ✅ **保留原图构图和人物细节最佳**
- ✅ 一次 API 调用完成
- ✅ 参数化 strength 控制原图保留程度（0-1）
- ✅ 天然支持 style transfer（服装、场景、光影）

**缺点：**
- ❌ 需要集成新的模型提供商（如 Replicate、RunwayML）
- ❌ 依赖图生图模型的质量
- ❌ 可能需要付费 API

### 实现步骤

1. **在配置中添加 Image-to-Image 模型提供商**
   ```yaml
   model_providers:
     - name: stable_diffusion
       provider: sd
       api_key: "..."
       models:
         - model: "stable-diffusion-v3"
           strength: 0.75  # 保留原图程度
   ```

2. **扩展 image_generation.py**
   ```python
   def _generate_sd_image_to_image(model_cfg, reference_image_path, prompt, ...):
       # 实现 Stable Diffusion Image-to-Image
   ```

3. **在 CharacterVisualAgent 中使用**
   ```python
   if reference_image_path and use_image_to_image:
       return self._generate_image_to_image(reference_image_path, prompt)
   else:
       return self._generate_remote_image(prompt)  # 回退方案
   ```

## 故障排查

### 常见问题

**Q: gallery/video 生成失败，提示"必须先生成主形象"**
- A: main_image 必须先生成。请先在"主形象"区域点击"生成主形象"。

**Q: 生成的 gallery/video 人物不一致**
- A: 确保已配置 LLM 客户端（anthropic 或 openai），Vision 模型需要正常工作。

**Q: 图片尺寸超过 2K（千问限制）**
- A: 自动降级处理。像素超过 2K 时会按比例缩小。

**Q: 本地图片路径为空**
- A: 检查图片下载是否成功，查看 `generated_images` 目录是否有文件。

## 代码结构

```
agents/
  character_visual_agent.py
    ├── invoke()                      # 主入口
    ├── _extract_reference_features() # Vision 特征提取
    ├── _extract_with_anthropic()     # Claude Vision
    ├── _extract_with_openai()        # GPT-4 Vision
    ├── _generate_remote_image()      # 文生图调用
    └── _build_prompt()               # 提示词构建
    
core/
  image_generation.py
    ├── generate_image_from_model_config()  # 统一分发接口
    ├── _generate_qwen_image()              # 千问 Token Plan
    └── _generate_openai_compatible_image() # OpenAI Images API
    
web_console/
  services/character_visuals.py
    ├── generate_character_visual()   # 核心逻辑
    ├── _build_prompt_optimizer_client() # LLM 客户端
    └── finalize_character_visuals()  # 定稿
```

## 参考资源

- [Claude Vision 文档](https://docs.anthropic.com/en/api/vision)
- [GPT-4 Vision 文档](https://platform.openai.com/docs/guides/vision)
- [千问官方 Token Plan 文档](https://help.aliyun.com/)
- [Stable Diffusion Image-to-Image](https://huggingface.co/runwayml/stable-diffusion-v1-5)
