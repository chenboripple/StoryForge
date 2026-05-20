"""角色形象资料服务：主形象、艺术照、视频立体图。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from agents.character_visual_agent import CharacterVisualAgent
from core.storage import StorageManager
from web_console.utils import _now
from web_console.services.visual_common import attach_local_url, build_prompt_optimizer_client
from web_console.services.visual_prompting import generate_character_main_prompt

VISUALS_FILENAME = "character_visuals.json"


def _hydrate_profile_local_urls(profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        return profile

    profile["main_image"] = attach_local_url(profile.get("main_image"))

    for key in ("gallery_images", "video_images"):
        images = profile.get(key)
        if isinstance(images, list):
            profile[key] = [attach_local_url(img) for img in images]

    return profile


def _visuals_path(sm: StorageManager, novel_id: str) -> str:
    return sm.config.path_for(novel_id, VISUALS_FILENAME)


def _load_all_visuals(sm: StorageManager, novel_id: str) -> Dict[str, Any]:
    path = _visuals_path(sm, novel_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _save_all_visuals(sm: StorageManager, novel_id: str, payload: Dict[str, Any]) -> None:
    path = _visuals_path(sm, novel_id)
    novel_dir = sm.config.novel_dir(novel_id)
    os.makedirs(novel_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _find_character_name(sm: StorageManager, novel_id: str, character_id: str) -> str:
    graph = sm.load_characters(novel_id)
    if not graph or not getattr(graph, "characters", None):
        return character_id

    cid = character_id.strip()
    for char in graph.characters:
        c_id = str(getattr(char, "character_id", "") or "").strip()
        c_name = str(getattr(char, "name", "") or "").strip()
        if cid and (cid == c_id or cid == c_name):
            return c_name or c_id or cid
    return cid


def _ensure_profile(sm: StorageManager, novel_id: str, character_id: str) -> Dict[str, Any]:
    all_profiles = _load_all_visuals(sm, novel_id)
    if character_id in all_profiles and isinstance(all_profiles[character_id], dict):
        return all_profiles[character_id]

    profile = {
        "character_id": character_id,
        "character_name": _find_character_name(sm, novel_id, character_id),
        "base_prompt": "",
        "main_image": None,
        "gallery_images": [],
        "video_images": [],
        "finalized": False,
        "finalized_at": None,
        "created_at": _now(),
        "updated_at": _now(),
        "history": [],
    }
    all_profiles[character_id] = profile
    _save_all_visuals(sm, novel_id, all_profiles)
    return profile


def get_character_visuals(sm: StorageManager, novel_id: str, character_id: str) -> Dict[str, Any]:
    profile = _ensure_profile(sm, novel_id, character_id)
    profile = _hydrate_profile_local_urls(profile)
    return {
        "novel_id": novel_id,
        "character_id": character_id,
        "profile": profile,
    }


def generate_character_visual(
    sm: StorageManager,
    novel_id: str,
    character_id: str,
    prompt: str,
    slot_type: str,
    index: Optional[int] = None,
    style: str = "",
    image_preset: str = "720p",
    aspect_ratio: str = "16:9",
    regenerate_all: bool = False,
) -> Dict[str, Any]:
    """
    生成角色形象。
    
    Args:
        slot_type: "main" | "gallery" | "video"
        index: 指定要替换的图片索引（仅 gallery/video）
        regenerate_all: 若为 True 且 slot_type="video"，清空所有视频图并重生成固定张数
    """
    # 【一致性保证机制】
    # 1. main 形象：独立生成，是后续所有形象的参考基准
    # 2. gallery/video：传入 main_image 的本地路径给 Vision LLM
    #    - Agent 通过 Claude Vision / GPT-4 Vision 读取图片
    #    - 提取人物核心特征（身体、面部、服装、气质）
    #    - 将特征融合进用户提示词，进行文生图
    #    - 结果：同一角色，不同场景/装束/角度
    #
    # 【未来优化】
    # - 直接集成图生图模型（Stable Diffusion Image-to-Image）
    # - 跳过文本提取步骤，直接传图 + 提示词
    # - 更好地保留原图细节和构图
    slot = (slot_type or "main").strip().lower()
    if slot not in {"main", "gallery", "video"}:
        raise ValueError("slot_type 必须为 main/gallery/video")

    all_profiles = _load_all_visuals(sm, novel_id)
    profile = _ensure_profile(sm, novel_id, character_id)

    # gallery 和 video 必须有 main_image 作为一致性参考
    if slot in {"gallery", "video"} and not profile.get("main_image"):
        raise ValueError(f"{slot} 生成前必须先生成主形象")

    character_name = profile.get("character_name") or _find_character_name(sm, novel_id, character_id)
    
    # main 时先基于小说/角色信息自动生成提示词；gallery/video 保持当前行为。
    prompt_client = build_prompt_optimizer_client()
    final_prompt = prompt
    if slot == "main":
        final_prompt = generate_character_main_prompt(
            sm=sm,
            novel_id=novel_id,
            character_id=character_id,
            user_prompt=prompt,
            style=style,
            llm_client=prompt_client,
        )

    agent = CharacterVisualAgent(llm_client=prompt_client)
    
    # 若为 gallery/video，传入 main_image 的本地路径作为参考
    agent_payload = {
        "novel_id": novel_id,
        "character_id": character_id,
        "character_name": character_name,
        "slot_type": slot,
        "prompt": final_prompt,
        "style": style,
        "image_preset": image_preset,
        "aspect_ratio": aspect_ratio,
    }
    if slot in {"gallery", "video"} and profile.get("main_image"):
        main_local_path = profile["main_image"].get("local_path", "")
        if main_local_path:
            agent_payload["reference_image_path"] = main_local_path
    
    generated = attach_local_url(agent.invoke(agent_payload))

    if slot == "main":
        profile["main_image"] = generated
    elif slot == "gallery":
        gallery = profile.setdefault("gallery_images", [])
        if index is not None and 0 <= index < len(gallery):
            gallery[index] = generated
        else:
            gallery.append(generated)
    else:  # video
        video_images = profile.setdefault("video_images", [])
        if regenerate_all:
            # 全量重生成：清空所有，生成 5 张全方位的视频立体图
            video_images.clear()
            angles = ["正面 全身", "侧面 全身", "背面 全身", "斜45°角 全身", "脸部特写"]
            main_local_path = profile["main_image"].get("local_path", "")
            for i, angle in enumerate(angles):
                angle_prompt = f"{final_prompt}；视角：{angle}"
                angle_payload = {
                    "novel_id": novel_id,
                    "character_id": character_id,
                    "character_name": character_name,
                    "slot_type": slot,
                    "prompt": angle_prompt,
                    "style": style,
                    "image_preset": image_preset,
                    "aspect_ratio": aspect_ratio,
                }
                if main_local_path:
                    angle_payload["reference_image_path"] = main_local_path
                angle_generated = attach_local_url(agent.invoke(angle_payload))
                video_images.append(angle_generated)
        elif index is not None and 0 <= index < len(video_images):
            # 替换指定位置
            video_images[index] = generated
        else:
            # 新增一张
            video_images.append(generated)

    profile["base_prompt"] = prompt or profile.get("base_prompt", "")
    profile["updated_at"] = _now()
    profile["finalized"] = False
    profile["finalized_at"] = None
    profile.setdefault("history", []).append(
        {
            "action": "generate",
            "slot_type": slot,
            "index": index,
            "prompt": prompt,
            "style": style,
            "image_preset": image_preset,
            "aspect_ratio": aspect_ratio,
            "regenerate_all": regenerate_all,
            "generated_id": generated.get("id"),
            "at": _now(),
        }
    )

    all_profiles[character_id] = profile
    _save_all_visuals(sm, novel_id, all_profiles)

    profile = _hydrate_profile_local_urls(profile)

    return {
        "novel_id": novel_id,
        "character_id": character_id,
        "generated": generated,
        "profile": profile,
    }


def finalize_character_visuals(
    sm: StorageManager,
    novel_id: str,
    character_id: str,
    finalized: bool = True,
) -> Dict[str, Any]:
    all_profiles = _load_all_visuals(sm, novel_id)
    profile = _ensure_profile(sm, novel_id, character_id)

    profile["finalized"] = bool(finalized)
    profile["finalized_at"] = _now() if finalized else None
    profile["updated_at"] = _now()
    profile.setdefault("history", []).append(
        {
            "action": "finalize" if finalized else "unfinalize",
            "at": _now(),
        }
    )

    all_profiles[character_id] = profile
    _save_all_visuals(sm, novel_id, all_profiles)

    return {
        "novel_id": novel_id,
        "character_id": character_id,
        "profile": profile,
    }
