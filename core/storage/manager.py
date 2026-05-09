"""
Storage Manager - 统一存储管理器

管理所有模型的 IO 操作，提供统一入口。
"""
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.config import get_config as get_core_config

from core.models import (
    NovelMeta, PipelineStage,
    Outline, CharacterGraph, WorldSetting,
    Chapter, Review, Proofread,
    ChapterAnalysis, StoryBible,
    AgentMessage, RoutingSuggestion,
    VideoState, VideoScript, VisualBible,
    AssetManifest, VideoRenderPlan,
    ConsistencyReport, VideoOutput,
)

from .base import StorageConfig, ModelStorage, DictModelStorage, ListModelStorage


class StorageManager:
    """
    统一存储管理器

    职责：
    1. 初始化各个模型的存储器
    2. 提供 CRUD 接口
    3. 维护索引文件
    """

    # 各模型对应文件命名
    FILENAMES = {
        'novel_meta': 'novel_meta.json',
        'outline': 'outline.json',
        'characters': 'characters.json',
        'world_setting': 'world_setting.json',
        'chapters': 'chapters.json',
        'reviews': 'reviews.json',
        'proofreads': 'proofreads.json',
        'chapter_analyses': 'chapter_analyses.json',
        'story_bible': 'story_bible.json',
        'agent_messages': 'agent_messages.json',
        'routing_suggestions': 'routing_suggestions.json',
        'video_state': 'video_state.json',
        'video_script': 'video_script.json',
        'visual_bible': 'visual_bible.json',
        'video_manifest': 'video_manifest.json',
        'video_render_plan': 'video_render_plan.json',
        'video_consistency_report': 'video_consistency_report.json',
        'video_output': 'video_output.json',
    }

    def __init__(self, config: Optional[StorageConfig] = None):
        if config is None:
            core_config = get_core_config()
            config = StorageConfig(data_dir=core_config.data_dir_abs)

        self.config = config

        # 初始化各模型的存储器
        self._novel_meta_store = ModelStorage(config, NovelMeta, self.FILENAMES['novel_meta'])
        self._outline_store = ModelStorage(config, Outline, self.FILENAMES['outline'])
        self._characters_store = ModelStorage(config, CharacterGraph, self.FILENAMES['characters'])
        self._world_store = ModelStorage(config, WorldSetting, self.FILENAMES['world_setting'])
        self._chapters_store = DictModelStorage(config, Chapter, self.FILENAMES['chapters'])
        self._reviews_store = DictModelStorage(config, Review, self.FILENAMES['reviews'])
        self._proofreads_store = DictModelStorage(config, Proofread, self.FILENAMES['proofreads'])
        self._analyses_store = DictModelStorage(config, ChapterAnalysis, self.FILENAMES['chapter_analyses'])
        self._story_bible_store = ModelStorage(config, StoryBible, self.FILENAMES['story_bible'])
        self._messages_store = ListModelStorage(config, AgentMessage, self.FILENAMES['agent_messages'])
        self._routing_store = ListModelStorage(config, RoutingSuggestion, self.FILENAMES['routing_suggestions'])
        self._video_state_store = ModelStorage(config, VideoState, self.FILENAMES['video_state'])
        self._video_script_store = ModelStorage(config, VideoScript, self.FILENAMES['video_script'])
        self._visual_bible_store = ModelStorage(config, VisualBible, self.FILENAMES['visual_bible'])
        self._video_manifest_store = ModelStorage(config, AssetManifest, self.FILENAMES['video_manifest'])
        self._video_render_plan_store = ModelStorage(config, VideoRenderPlan, self.FILENAMES['video_render_plan'])
        self._video_consistency_report_store = ModelStorage(config, ConsistencyReport, self.FILENAMES['video_consistency_report'])
        self._video_output_store = ModelStorage(config, VideoOutput, self.FILENAMES['video_output'])

        # 内存缓存
        self._cache: Dict[str, Dict[str, Any]] = {}  # novel_id -> {model_key: data}

        # 变更追踪
        self._dirty: Dict[str, List[str]] = {}  # novel_id -> [model_keys]

        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.config.novels_dir, exist_ok=True)

    def _mark_dirty(self, novel_id: str, model_key: str):
        """标记某个模型已变更（用于增量写入）"""
        if novel_id not in self._dirty:
            self._dirty[novel_id] = []
        if model_key not in self._dirty[novel_id]:
            self._dirty[novel_id].append(model_key)

    def _cache_get(self, novel_id: str, model_key: str) -> Any:
        if novel_id in self._cache:
            return self._cache[novel_id].get(model_key)
        return None

    def _cache_set(self, novel_id: str, model_key: str, data: Any):
        if novel_id not in self._cache:
            self._cache[novel_id] = {}
        self._cache[novel_id][model_key] = data
        self._mark_dirty(novel_id, model_key)

    # ========== Novel Meta (元数据，索引) ==========

    def create_novel(self, novel_id: str, title: str = "", genre: str = "",
                     concept: str = "", target_word_count: int = 3000) -> NovelMeta:
        """创建新小说"""
        meta = NovelMeta(
            novel_id=novel_id,
            novel_title=title,
            genre=genre,
            concept=concept,
            target_word_count=target_word_count,
            current_stage=PipelineStage.CREATION,
            current_chapter=1,
            total_chapters=0,
        )
        self._novel_meta_store.save(novel_id, meta)
        self._cache_set(novel_id, 'novel_meta', meta)
        self.update_index(meta)
        return meta

    def save_novel_meta(self, novel_id: str, meta: NovelMeta):
        """保存小说元数据"""
        self._novel_meta_store.save(novel_id, meta)
        self._cache_set(novel_id, 'novel_meta', meta)
        self.update_index(meta)

    def load_novel_meta(self, novel_id: str) -> Optional[NovelMeta]:
        """加载小说元数据"""
        cached = self._cache_get(novel_id, 'novel_meta')
        if cached:
            return cached
        meta = self._novel_meta_store.load(novel_id)
        if meta:
            self._cache_set(novel_id, 'novel_meta', meta)
        return meta

    def novel_exists(self, novel_id: str) -> bool:
        """检查小说是否存在"""
        return self._novel_meta_store.exists(novel_id)

    def list_novels(self) -> List[Dict[str, Any]]:
        """获取小说列表（从 index.json）"""
        if not os.path.exists(self.config.index_file):
            return []
        with open(self.config.index_file, "r", encoding=self.config.encoding) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def update_index(self, meta: NovelMeta):
        """更新索引文件"""
        entries = self.list_novels()
        entry = meta.to_index_entry()
        found = False
        for i, e in enumerate(entries):
            if e.get('novel_id') == meta.novel_id:
                entries[i] = entry
                found = True
                break
        if not found:
            entries.append(entry)
        with open(self.config.index_file, "w", encoding=self.config.encoding) as f:
            json.dump(entries, f, ensure_ascii=self.config.ensure_ascii, indent=self.config.indent)

    def rebuild_index(self) -> int:
        """重建索引（扫描 novels 目录）"""
        entries = []
        if os.path.isdir(self.config.novels_dir):
            for dirname in sorted(os.listdir(self.config.novels_dir)):
                if dirname.startswith('.'):
                    continue
                novel_dir = os.path.join(self.config.novels_dir, dirname)
                if not os.path.isdir(novel_dir):
                    continue
                meta_file = os.path.join(novel_dir, self.FILENAMES['novel_meta'])
                if os.path.exists(meta_file):
                    try:
                        meta = self.load_novel_meta(dirname)
                        if meta:
                            entries.append(meta.to_index_entry())
                    except Exception:
                        continue
        with open(self.config.index_file, "w", encoding=self.config.encoding) as f:
            json.dump(entries, f, ensure_ascii=self.config.ensure_ascii, indent=self.config.indent)
        return len(entries)

    def delete_novel(self, novel_id: str) -> bool:
        """删除小说（删除整个目录）"""
        import shutil
        novel_dir = self.config.novel_dir(novel_id)
        if os.path.isdir(novel_dir):
            shutil.rmtree(novel_dir)
        # 清理缓存
        if novel_id in self._cache:
            del self._cache[novel_id]
        if novel_id in self._dirty:
            del self._dirty[novel_id]
        # 更新索引
        entries = self.list_novels()
        entries = [e for e in entries if e.get('novel_id') != novel_id]
        with open(self.config.index_file, "w", encoding=self.config.encoding) as f:
            json.dump(entries, f, ensure_ascii=self.config.ensure_ascii, indent=self.config.indent)
        return True

    # ========== Outline (大纲) ==========

    def save_outline(self, novel_id: str, outline: Outline):
        """保存大纲"""
        self._outline_store.save(novel_id, outline)
        self._cache_set(novel_id, 'outline', outline)

    def load_outline(self, novel_id: str) -> Optional[Outline]:
        """加载大纲"""
        cached = self._cache_get(novel_id, 'outline')
        if cached:
            return cached
        outline = self._outline_store.load(novel_id)
        if outline:
            self._cache_set(novel_id, 'outline', outline)
        return outline

    # ========== Characters (人物关系) ==========

    def save_characters(self, novel_id: str, chars: CharacterGraph):
        """保存人物关系图"""
        self._characters_store.save(novel_id, chars)
        self._cache_set(novel_id, 'characters', chars)

    def load_characters(self, novel_id: str) -> Optional[CharacterGraph]:
        """加载人物关系图"""
        cached = self._cache_get(novel_id, 'characters')
        if cached:
            return cached
        chars = self._characters_store.load(novel_id)
        if chars:
            self._cache_set(novel_id, 'characters', chars)
        return chars

    # ========== World Setting (世界观) ==========

    def save_world(self, novel_id: str, world: WorldSetting):
        """保存世界观"""
        self._world_store.save(novel_id, world)
        self._cache_set(novel_id, 'world_setting', world)

    def load_world(self, novel_id: str) -> Optional[WorldSetting]:
        """加载世界观"""
        cached = self._cache_get(novel_id, 'world_setting')
        if cached:
            return cached
        world = self._world_store.load(novel_id)
        if world:
            self._cache_set(novel_id, 'world_setting', world)
        return world

    # ========== Chapters (章节) ==========

    def save_chapters(self, novel_id: str, chapters: Dict[int, Chapter]):
        """保存所有章节"""
        self._chapters_store.save_dict(novel_id, chapters)
        self._cache_set(novel_id, 'chapters', chapters)

    def load_chapters(self, novel_id: str) -> Dict[int, Chapter]:
        """加载所有章节"""
        cached = self._cache_get(novel_id, 'chapters')
        if cached:
            return cached
        chapters = self._chapters_store.load_dict(novel_id)
        self._cache_set(novel_id, 'chapters', chapters)
        return chapters

    def save_chapter(self, novel_id: str, chapter: Chapter):
        """保存单个章节（增量式）"""
        chapters = self.load_chapters(novel_id)
        chapters[chapter.chapter_num] = chapter
        self.save_chapters(novel_id, chapters)

    def load_chapter(self, novel_id: str, chapter_num: int) -> Optional[Chapter]:
        """加载单个章节"""
        chapters = self.load_chapters(novel_id)
        return chapters.get(chapter_num)

    # ========== Reviews (审稿) ==========

    def save_reviews(self, novel_id: str, reviews: Dict[int, Review]):
        """保存所有审稿记录"""
        self._reviews_store.save_dict(novel_id, reviews)
        self._cache_set(novel_id, 'reviews', reviews)

    def load_reviews(self, novel_id: str) -> Dict[int, Review]:
        """加载所有审稿记录"""
        cached = self._cache_get(novel_id, 'reviews')
        if cached:
            return cached
        reviews = self._reviews_store.load_dict(novel_id)
        self._cache_set(novel_id, 'reviews', reviews)
        return reviews

    def save_review(self, novel_id: str, review: Review):
        """保存单个章节审稿"""
        reviews = self.load_reviews(novel_id)
        reviews[review.chapter_num] = review
        self.save_reviews(novel_id, reviews)

    # ========== Proofreads (校对) ==========

    def save_proofreads(self, novel_id: str, proofreads: Dict[int, Proofread]):
        """保存所有校对记录"""
        self._proofreads_store.save_dict(novel_id, proofreads)
        self._cache_set(novel_id, 'proofreads', proofreads)

    def load_proofreads(self, novel_id: str) -> Dict[int, Proofread]:
        """加载所有校对记录"""
        cached = self._cache_get(novel_id, 'proofreads')
        if cached:
            return cached
        proofreads = self._proofreads_store.load_dict(novel_id)
        self._cache_set(novel_id, 'proofreads', proofreads)
        return proofreads

    # ========== Chapter Analyses (章节分析) ==========

    def save_analyses(self, novel_id: str, analyses: Dict[int, ChapterAnalysis]):
        """保存所有章节分析"""
        self._analyses_store.save_dict(novel_id, analyses)
        self._cache_set(novel_id, 'chapter_analyses', analyses)

    def load_analyses(self, novel_id: str) -> Dict[int, ChapterAnalysis]:
        """加载所有章节分析"""
        cached = self._cache_get(novel_id, 'chapter_analyses')
        if cached:
            return cached
        analyses = self._analyses_store.load_dict(novel_id)
        self._cache_set(novel_id, 'chapter_analyses', analyses)
        return analyses

    # ========== Story Bible (IP) ==========

    def save_story_bible(self, novel_id: str, bible: StoryBible):
        """保存 Story Bible"""
        self._story_bible_store.save(novel_id, bible)
        self._cache_set(novel_id, 'story_bible', bible)

    def load_story_bible(self, novel_id: str) -> Optional[StoryBible]:
        """加载 Story Bible"""
        cached = self._cache_get(novel_id, 'story_bible')
        if cached:
            return cached
        bible = self._story_bible_store.load(novel_id)
        if bible:
            self._cache_set(novel_id, 'story_bible', bible)
        return bible

    # ========== Agent Messages (Agent 通信) ==========

    def save_messages(self, novel_id: str, messages: List[AgentMessage]):
        """保存 Agent 消息"""
        self._messages_store.save_list(novel_id, messages)
        self._cache_set(novel_id, 'agent_messages', messages)

    def load_messages(self, novel_id: str) -> List[AgentMessage]:
        """加载 Agent 消息"""
        cached = self._cache_get(novel_id, 'agent_messages')
        if cached:
            return cached
        messages = self._messages_store.load_list(novel_id)
        self._cache_set(novel_id, 'agent_messages', messages)
        return messages

    def add_message(self, novel_id: str, message: AgentMessage):
        """追加一条消息"""
        messages = self.load_messages(novel_id)
        messages.append(message)
        self.save_messages(novel_id, messages)

    def save_routing_suggestions(self, novel_id: str, suggestions: List[RoutingSuggestion]):
        """保存路由建议"""
        self._routing_store.save_list(novel_id, suggestions)
        self._cache_set(novel_id, 'routing_suggestions', suggestions)

    def load_routing_suggestions(self, novel_id: str) -> List[RoutingSuggestion]:
        """加载路由建议"""
        cached = self._cache_get(novel_id, 'routing_suggestions')
        if cached:
            return cached
        suggestions = self._routing_store.load_list(novel_id)
        self._cache_set(novel_id, 'routing_suggestions', suggestions)
        return suggestions

    # ========== Video (视频生成) ==========

    def save_video_state(self, novel_id: str, video_state: VideoState):
        """保存视频状态"""
        self._video_state_store.save(novel_id, video_state)
        self._cache_set(novel_id, 'video_state', video_state)

    def load_video_state(self, novel_id: str) -> Optional[VideoState]:
        """加载视频状态"""
        cached = self._cache_get(novel_id, 'video_state')
        if cached:
            return cached
        video_state = self._video_state_store.load(novel_id)
        if video_state:
            self._cache_set(novel_id, 'video_state', video_state)
        return video_state

    def save_video_script(self, novel_id: str, script: VideoScript):
        """保存视频剧本"""
        self._video_script_store.save(novel_id, script)
        self._cache_set(novel_id, 'video_script', script)

    def load_video_script(self, novel_id: str) -> Optional[VideoScript]:
        """加载视频剧本"""
        cached = self._cache_get(novel_id, 'video_script')
        if cached:
            return cached
        script = self._video_script_store.load(novel_id)
        if script:
            self._cache_set(novel_id, 'video_script', script)
        return script

    def save_visual_bible(self, novel_id: str, bible: VisualBible):
        """保存视觉圣经"""
        self._visual_bible_store.save(novel_id, bible)
        self._cache_set(novel_id, 'visual_bible', bible)

    def load_visual_bible(self, novel_id: str) -> Optional[VisualBible]:
        """加载视觉圣经"""
        cached = self._cache_get(novel_id, 'visual_bible')
        if cached:
            return cached
        bible = self._visual_bible_store.load(novel_id)
        if bible:
            self._cache_set(novel_id, 'visual_bible', bible)
        return bible

    def save_video_manifest(self, novel_id: str, manifest: AssetManifest):
        """保存视频资产索引"""
        self._video_manifest_store.save(novel_id, manifest)
        self._cache_set(novel_id, 'video_manifest', manifest)

    def load_video_manifest(self, novel_id: str) -> Optional[AssetManifest]:
        """加载视频资产索引"""
        cached = self._cache_get(novel_id, 'video_manifest')
        if cached:
            return cached
        manifest = self._video_manifest_store.load(novel_id)
        if manifest:
            self._cache_set(novel_id, 'video_manifest', manifest)
        return manifest

    def save_video_render_plan(self, novel_id: str, plan: VideoRenderPlan):
        """保存视频渲染计划"""
        self._video_render_plan_store.save(novel_id, plan)
        self._cache_set(novel_id, 'video_render_plan', plan)

    def load_video_render_plan(self, novel_id: str) -> Optional[VideoRenderPlan]:
        """加载视频渲染计划"""
        cached = self._cache_get(novel_id, 'video_render_plan')
        if cached:
            return cached
        plan = self._video_render_plan_store.load(novel_id)
        if plan:
            self._cache_set(novel_id, 'video_render_plan', plan)
        return plan

    def save_video_consistency_report(self, novel_id: str, report: ConsistencyReport):
        """保存一致性报告"""
        self._video_consistency_report_store.save(novel_id, report)
        self._cache_set(novel_id, 'video_consistency_report', report)

    def load_video_consistency_report(self, novel_id: str) -> Optional[ConsistencyReport]:
        """加载一致性报告"""
        cached = self._cache_get(novel_id, 'video_consistency_report')
        if cached:
            return cached
        report = self._video_consistency_report_store.load(novel_id)
        if report:
            self._cache_set(novel_id, 'video_consistency_report', report)
        return report

    def save_video_output(self, novel_id: str, output: VideoOutput):
        """保存视频输出"""
        self._video_output_store.save(novel_id, output)
        self._cache_set(novel_id, 'video_output', output)

    def load_video_output(self, novel_id: str) -> Optional[VideoOutput]:
        """加载视频输出"""
        cached = self._cache_get(novel_id, 'video_output')
        if cached:
            return cached
        output = self._video_output_store.load(novel_id)
        if output:
            self._cache_set(novel_id, 'video_output', output)
        return output


    # ========== Bulk Operations ==========

    def flush(self, novel_id: Optional[str] = None):
        """将缓存中的变更写入磁盘"""
        pass  # 当前实现是即时写入，不需要 flush

    def clear_cache(self, novel_id: Optional[str] = None):
        """清空缓存"""
        if novel_id:
            if novel_id in self._cache:
                del self._cache[novel_id]
        else:
            self._cache.clear()


# 全局单例
_global_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """获取全局存储管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = StorageManager()
    return _global_manager
