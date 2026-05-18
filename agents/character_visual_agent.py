"""角色形象生成 Agent（多 Agent 体系中的独立 Agent）。"""

from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from core.agent import AgentPersona, BaseAgent
from core.config import get_config
from core.image_generation import generate_image_from_model_config, resolve_image_size


class CharacterVisualPersona(AgentPersona):
    """角色形象设计师人设。"""

    def __init__(self) -> None:
        super().__init__(
            name="镜相",
            role="角色视觉设计师",
            goal="为小说角色生成稳定、可迭代的视觉形象提示词和图片候选",
            backstory="擅长把文字角色设定拆解为可执行的视觉语言，强调角色一致性与镜头可复用性。",
            expertise=["角色形象提示词设计", "主视觉一致性", "艺术照风格探索", "视频立体图参考"],
            tone="专业、简洁、可执行",
            principles=[
                "主形象优先保持身份一致",
                "艺术照允许风格探索但不偏离角色核心特征",
                "视频立体图优先清晰轮廓与可动画化表现",
            ],
            constraints=[
                "输出必须可用于下游图像生成接口",
                "尽量复用并强化用户提供的提示词",
            ],
        )


class CharacterVisualAgent(BaseAgent):
    """角色形象生成 Agent。

    说明：
    - 当配置了 llm_client 时，可用于提示词润色。
    - 未配置 llm_client 时，仍可稳定输出可复用的生成结果（占位图 URL + 结构化元数据）。
    """

    def __init__(self, llm_client=None, memory=None, error_handler=None, message_bus=None, state=None):
        super().__init__(
            persona=CharacterVisualPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False,
            message_bus=message_bus,
            state=state,
        )

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        novel_id = str(payload.get("novel_id") or "").strip()
        character_id = str(payload.get("character_id") or "").strip()
        character_name = str(payload.get("character_name") or character_id or "角色").strip()
        slot_type = str(payload.get("slot_type") or "main").strip().lower()
        style = str(payload.get("style") or "").strip()
        image_preset = str(payload.get("image_preset") or "720p").strip().lower()
        aspect_ratio = str(payload.get("aspect_ratio") or "16:9").strip()
        reference_image_path = str(payload.get("reference_image_path") or "").strip()

        base_prompt = str(payload.get("prompt") or "").strip()
        
        # 若有参考图片，先从图片中提取视觉特征，融合进提示词
        reference_context = ""
        if reference_image_path and os.path.isfile(reference_image_path):
            reference_context = self._extract_reference_features(reference_image_path, character_name)
        
        prompt_used = self._build_prompt(character_name, slot_type, base_prompt, style, reference_context)

        ts = datetime.now().isoformat()
        remote, remote_error = self._generate_remote_image(
            prompt_used,
            image_preset=image_preset,
            aspect_ratio=aspect_ratio,
        )

        image_id = self._build_image_id(novel_id, character_id, slot_type, prompt_used, ts)
        if remote:
            result = {
                "id": image_id,
                "type": slot_type,
                "url": remote.get("url", ""),
                "thumb_url": remote.get("thumb_url", remote.get("url", "")),
                "local_path": remote.get("local_path", ""),
                "prompt": prompt_used,
                "style": style,
                "size": remote.get("size", ""),
                "aspect_ratio": remote.get("aspect_ratio", aspect_ratio),
                "image_preset": remote.get("image_preset", image_preset),
                "generated_at": ts,
                "agent": self.persona.name,
                "provider": remote.get("provider", "configured-image-provider"),
                "model": remote.get("model", ""),
            }
        else:
            # 仅在真实生图失败时回退占位图，避免接口不可用导致流程中断。
            seed = hashlib.md5(image_id.encode("utf-8")).hexdigest()[:16]
            result = {
                "id": image_id,
                "type": slot_type,
                "url": f"https://picsum.photos/seed/{seed}/768/1024",
                "thumb_url": f"https://picsum.photos/seed/{seed}/320/426",
                "prompt": prompt_used,
                "style": style,
                "size": resolve_image_size("", image_preset=image_preset, aspect_ratio=aspect_ratio),
                "aspect_ratio": aspect_ratio,
                "image_preset": image_preset,
                "generated_at": ts,
                "agent": self.persona.name,
                "provider": "picsum-fallback",
                "fallback_reason": remote_error or "image generation failed",
            }

        self.publish_message(
            msg_type="info",
            content=f"已生成角色形象：{character_name} / {slot_type}",
            target=None,
            priority="normal",
        )
        return result

    def _generate_remote_image(
        self,
        prompt: str,
        image_preset: str = "720p",
        aspect_ratio: str = "16:9",
    ) -> Tuple[Optional[Dict[str, str]], str]:
        cfg = get_config()
        model_cfg = self._resolve_image_model(cfg)
        if not model_cfg:
            return None, "no image model configured"

        requested_cfg = dict(model_cfg)
        requested_cfg["image_preset"] = image_preset
        requested_cfg["aspect_ratio"] = aspect_ratio
        # 生图尺寸策略：
        # 1) 先按前端 image_preset + aspect_ratio 计算目标尺寸
        # 2) 再用 model_cfg.max_image_size 作为最大尺寸上限进行等比约束
        requested_cfg["image_size"] = resolve_image_size(
            provider=str(model_cfg.get("provider") or ""),
            requested_size=str(model_cfg.get("max_image_size") or ""),
            image_preset=image_preset,
            aspect_ratio=aspect_ratio,
        )

        download_dir = os.path.join(cfg.data_dir_abs, "generated_images")
        return generate_image_from_model_config(requested_cfg, prompt, download_dir=download_dir)

    def _extract_reference_features(self, image_path: str, character_name: str) -> str:
        """
        用 Vision LLM 读取参考图片，提取关键视觉特征。
        返回特征描述文本，用于融合进提示词。
        
        【当前方案说明】
        - 通过 Claude Vision 或 GPT-4 Vision 的多模态能力，直接分析图片本身
        - 提取的特征包括：身体特征、面部特征、服装风格、整体气氛等
        - 融合进后续 gallery/video 的提示词，确保人物一致性
        
        【未来优化方向】
        - 集成 Stable Diffusion Image-to-Image 或其他图生图模型
        - 直接传递参考图片 + 提示词，而不是先提取文本特征
        - 优势：保留原图构图和人物细节，只改变场景/装束/角度
        - 参数化支持 strength（保留原图 vs 应用提示词的平衡）
        """
        if not self.llm_client:
            return ""
        
        try:
            # 尝试用 Anthropic Claude Vision 或 OpenAI GPT-4 Vision 读取图片
            # 支持多模态视觉理解，自动检测客户端类型
            if hasattr(self.llm_client, '__self__') and hasattr(self.llm_client.__self__, 'messages'):
                # 这是 Anthropic client 的绑定方法
                return self._extract_with_anthropic(image_path, character_name)
            elif hasattr(self.llm_client, 'messages'):
                # 这是 OpenAI client 的绑定方法
                return self._extract_with_openai(image_path, character_name)
        except Exception as e:
            # Vision 读取失败，返回空字符串，回退到文本提示
            return ""
        
        return ""

    def _extract_with_anthropic(self, image_path: str, character_name: str) -> str:
        """用 Anthropic Claude Vision 读取参考图片。"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            
            # 判断图片格式
            ext = os.path.splitext(image_path)[1].lower()
            media_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }
            media_type = media_type_map.get(ext, "image/jpeg")
            
            message = self.llm_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": f"请分析这张图片中 {character_name} 的关键视觉特征。包括：身体特征（身材、气质）、面部特征（轮廓、气质）、服装风格、整体气氛等。回答要简洁、具体、便于作为 AI 生成图片的参考描述。"
                            }
                        ]
                    }
                ]
            )
            return str(message.content[0].text).strip()
        except Exception as e:
            return ""

    def _extract_with_openai(self, image_path: str, character_name: str) -> str:
        """用 OpenAI GPT-4 Vision 读取参考图片。"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")
            
            # 判断图片格式
            ext = os.path.splitext(image_path)[1].lower()
            media_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }
            media_type = media_type_map.get(ext, "image/jpeg")
            
            response = self.llm_client.chat.completions.create(
                model="gpt-4-vision-preview",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": f"请分析这张图片中 {character_name} 的关键视觉特征。包括：身体特征（身材、气质）、面部特征（轮廓、气质）、服装风格、整体气氛等。回答要简洁、具体、便于作为 AI 生成图片的参考描述。"
                            }
                        ]
                    }
                ]
            )
            return str(response.choices[0].message.content).strip()
        except Exception as e:
            return ""

    def _resolve_image_model(self, cfg) -> Optional[Dict[str, Any]]:
        routing = getattr(cfg, "model_routing", None)
        agent_prefs = getattr(routing, "agent_preferences", {}) or {}
        alias = (
            agent_prefs.get("visual_designer")
            or agent_prefs.get("镜相")
            or "image_wan27_pro"
        )

        providers = getattr(cfg, "model_providers", None) or []
        all_models: list[Dict[str, Any]] = []
        for p in providers:
            p_name = str(getattr(p, "name", "") or "")
            p_provider = str(getattr(p, "provider", "") or "")
            p_key = str(getattr(p, "api_key", "") or "")
            p_base = str(getattr(p, "base_url", "") or "")
            raw_models = getattr(p, "models", []) or []
            if not isinstance(raw_models, list):
                continue
            for m in raw_models:
                if not isinstance(m, dict):
                    continue
                entry = dict(m)
                entry["provider_name"] = p_name
                entry["provider"] = p_provider
                entry["api_key"] = p_key
                entry["base_url"] = p_base
                all_models.append(entry)

        for m in all_models:
            if str(m.get("name") or "") == alias:
                return m

        for m in all_models:
            model_id = str(m.get("model") or "").lower()
            if "image" in model_id or "wan" in model_id or "qwen-image" in model_id:
                return m

        return None

    def _build_prompt(self, character_name: str, slot_type: str, prompt: str, style: str, reference_context: str = "") -> str:
        slot_hint = {
            "main": "主形象设定图，正面半身，身份识别强",
            "gallery": "艺术照风格图，允许构图和光影变化",
            "video": "视频立体参考图，轮廓清晰，便于三维建模",
        }.get(slot_type, "角色形象图")

        if self.llm_client:
            task = (
                "请把用户提示词润色为适合文生图的高质量提示词。"
                "要求：保留角色核心特征，补充镜头、光线、材质细节，中文输出。"
            )
            context = (
                f"角色名：{character_name}\n"
                f"图片类型：{slot_type}\n"
                f"类型目标：{slot_hint}\n"
                f"风格：{style or '默认'}\n"
            )
            # 如果有参考图特征，加入上下文
            if reference_context:
                context += f"参考图特征（保持一致）：{reference_context}\n"
            context += f"用户提示词：{prompt or '未提供'}"
            
            try:
                polished = str(self._call_llm(task=task, context=context, json_schema=None)).strip()
                if polished:
                    return polished
            except Exception:
                # LLM 润色失败时回退到规则拼接。
                pass

        parts = [character_name, slot_hint]
        if reference_context:
            parts.append(reference_context)
        if style:
            parts.append(f"风格：{style}")
        if prompt:
            parts.append(prompt)
        else:
            parts.append("高细节，电影级光影，人物一致性")
        return "，".join(parts)

    @staticmethod
    def _build_image_id(
        novel_id: str,
        character_id: str,
        slot_type: str,
        prompt_used: str,
        generated_at: str,
    ) -> str:
        raw = f"{novel_id}:{character_id}:{slot_type}:{prompt_used}:{generated_at}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        return f"img_{digest}"
