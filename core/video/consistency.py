"""
Video consistency 校验服务（规则 + embedding 骨架）
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List

from core.models.video import (
    AssetManifest,
    ConsistencyIssue,
    ConsistencyMetrics,
    ConsistencyReport,
    ConsistencyThresholds,
    VisualBible,
)
from .providers import EmbeddingProvider


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    if size == 0:
        return 0.0
    va = a[:size]
    vb = b[:size]
    dot = sum(x * y for x, y in zip(va, vb))
    norm_a = math.sqrt(sum(x * x for x in va))
    norm_b = math.sqrt(sum(y * y for y in vb))
    denom = norm_a * norm_b
    if denom == 0:
        return 0.0
    return max(0.0, min(1.0, dot / denom))


def _avg(values: List[float], default: float = 1.0) -> float:
    if not values:
        return default
    return sum(values) / len(values)


@dataclass
class _ResolvedThresholds:
    face_consistency_min: float
    age_transition_min: float
    scene_structure_min: float

    def to_model(self) -> ConsistencyThresholds:
        return ConsistencyThresholds(
            face_consistency_min=self.face_consistency_min,
            age_transition_min=self.age_transition_min,
            scene_structure_min=self.scene_structure_min,
        )


class VideoConsistencyService:
    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedding_provider = embedding_provider

    def _resolve_thresholds(self, overrides: dict | None) -> _ResolvedThresholds:
        base = ConsistencyThresholds()
        if not overrides:
            return _ResolvedThresholds(
                face_consistency_min=base.face_consistency_min,
                age_transition_min=base.age_transition_min,
                scene_structure_min=base.scene_structure_min,
            )

        def _pick(name: str, default_value: float) -> float:
            raw = overrides.get(name, default_value)
            try:
                val = float(raw)
            except (TypeError, ValueError):
                val = default_value
            return max(0.0, min(1.0, val))

        return _ResolvedThresholds(
            face_consistency_min=_pick("face_consistency_min", base.face_consistency_min),
            age_transition_min=_pick("age_transition_min", base.age_transition_min),
            scene_structure_min=_pick("scene_structure_min", base.scene_structure_min),
        )

    def validate(
        self,
        novel_id: str,
        bible: VisualBible,
        manifest: AssetManifest,
        threshold_overrides: dict | None = None,
    ) -> ConsistencyReport:
        issues: List[ConsistencyIssue] = []
        fallback_reasons: List[str] = []
        thresholds = self._resolve_thresholds(threshold_overrides)

        embedding_cache: dict[str, List[float]] = {}
        for asset in manifest.assets:
            if asset.uri:
                embedding_cache[asset.asset_id] = self.embedding_provider.embed_image(asset.uri)

        # 指标1：人脸一致性（同一角色跨年龄定妆图 + 镜头角色参考）
        face_scores: List[float] = []
        for char_id in bible.character_profiles.keys():
            char_assets = [
                a for a in manifest.assets
                if a.asset_type == "character_portrait" and a.character_id == char_id
            ]
            embeds = [embedding_cache.get(a.asset_id, []) for a in char_assets if a.asset_id in embedding_cache]
            pairwise: List[float] = []
            for i in range(len(embeds)):
                for j in range(i + 1, len(embeds)):
                    pairwise.append(_cosine_similarity(embeds[i], embeds[j]))
            char_score = _avg(pairwise, default=1.0)
            face_scores.append(char_score)

            if char_score < thresholds.face_consistency_min:
                desc = f"角色 {char_id} 跨定妆图一致性不足"
                issues.append(
                    ConsistencyIssue(
                        issue_id=f"face-{char_id}",
                        level="error",
                        issue_type="character_identity",
                        target_id=char_id,
                        description=desc,
                        score=round(char_score, 4),
                        threshold=thresholds.face_consistency_min,
                        measured=round(char_score, 4),
                    )
                )
                fallback_reasons.append(
                    f"face_consistency<{thresholds.face_consistency_min:.2f}: {char_id}={char_score:.3f}"
                )

        # 指标2：年龄迁移一致性（young->adult->old 变化应平滑且有方向）
        age_scores: List[float] = []
        for char_id in bible.character_profiles.keys():
            by_stage = {}
            for a in manifest.assets:
                if a.asset_type == "character_portrait" and a.character_id == char_id and a.age_stage:
                    by_stage[a.age_stage] = embedding_cache.get(a.asset_id, [])

            young = by_stage.get("young")
            adult = by_stage.get("adult")
            old = by_stage.get("old")
            if not young or not adult or not old:
                continue

            sim_ya = _cosine_similarity(young, adult)
            sim_ao = _cosine_similarity(adult, old)
            sim_yo = _cosine_similarity(young, old)

            # 期望 young-old 更分离；young-adult 与 adult-old 保持较高连续性。
            continuity = (sim_ya + sim_ao) / 2.0
            directional_gap = max(0.0, continuity - sim_yo)
            age_score = max(0.0, min(1.0, 0.65 * continuity + 0.35 * directional_gap))
            age_scores.append(age_score)

            if age_score < thresholds.age_transition_min:
                desc = (
                    f"角色 {char_id} 年龄迁移不稳定: "
                    f"YA={sim_ya:.3f}, AO={sim_ao:.3f}, YO={sim_yo:.3f}"
                )
                issues.append(
                    ConsistencyIssue(
                        issue_id=f"age-{char_id}",
                        level="error",
                        issue_type="age_progression",
                        target_id=char_id,
                        description=desc,
                        score=round(age_score, 4),
                        threshold=thresholds.age_transition_min,
                        measured=round(age_score, 4),
                    )
                )
                fallback_reasons.append(
                    f"age_transition<{thresholds.age_transition_min:.2f}: {char_id}={age_score:.3f}"
                )

        # 指标3：场景结构相似度（场景定场图 vs 同场景镜头参考图）
        scene_scores: List[float] = []
        for scene_id in bible.scene_profiles.keys():
            ref_assets = [
                a for a in manifest.assets
                if a.asset_type == "scene_reference" and a.scene_id == scene_id
            ]
            shot_assets = [
                a for a in manifest.assets
                if a.asset_type == "shot_reference" and a.scene_id == scene_id
            ]

            if not ref_assets or not shot_assets:
                continue

            ref_embed = embedding_cache.get(ref_assets[0].asset_id, [])
            sims = [
                _cosine_similarity(ref_embed, embedding_cache.get(sa.asset_id, []))
                for sa in shot_assets
                if sa.asset_id in embedding_cache
            ]
            scene_score = _avg(sims, default=1.0)
            scene_scores.append(scene_score)

            if scene_score < thresholds.scene_structure_min:
                desc = f"场景 {scene_id} 结构相似度不足"
                issues.append(
                    ConsistencyIssue(
                        issue_id=f"scene-{scene_id}",
                        level="error",
                        issue_type="scene_structure",
                        target_id=scene_id,
                        description=desc,
                        score=round(scene_score, 4),
                        threshold=thresholds.scene_structure_min,
                        measured=round(scene_score, 4),
                    )
                )
                fallback_reasons.append(
                    f"scene_structure<{thresholds.scene_structure_min:.2f}: {scene_id}={scene_score:.3f}"
                )
        # 基础规则校验
        for char_id, profile in bible.character_profiles.items():
            if not profile.reference_image_ids:
                issues.append(
                    ConsistencyIssue(
                        issue_id=f"char-ref-{char_id}",
                        level="warning",
                        issue_type="character_identity",
                        target_id=char_id,
                        description="角色缺少参考图，可能导致跨镜头形象漂移",
                        score=0.0,
                    )
                )

        for scene_id, profile in bible.scene_profiles.items():
            if not profile.reference_image_ids:
                issues.append(
                    ConsistencyIssue(
                        issue_id=f"scene-ref-{scene_id}",
                        level="warning",
                        issue_type="scene_structure",
                        target_id=scene_id,
                        description="场景缺少参考图，可能导致建筑/景观漂移",
                        score=0.0,
                    )
                )

        metrics = ConsistencyMetrics(
            face_consistency=round(_avg(face_scores, default=1.0), 4),
            age_transition=round(_avg(age_scores, default=1.0), 4),
            scene_structure=round(_avg(scene_scores, default=1.0), 4),
        )
        passed = not any(i.level == "error" for i in issues)
        return ConsistencyReport(
            novel_id=novel_id,
            passed=passed,
            metrics=metrics,
            thresholds=thresholds.to_model(),
            issues=issues,
            fallback_reasons=fallback_reasons,
        )
