"""
StoryForge - 批量生成模块

职责：
1. 支持多章并行生成（无剧情依赖的章节）
2. 支持批量审核
3. 支持批量校对
4. 依赖关系分析和执行顺序调度
5. 进度追踪和任务管理
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
import threading
import time
import json
import os
from datetime import datetime


class JobStatus(Enum):
    """批处理任务状态"""
    PENDING = "pending"
    WAITING_DEPENDENCY = "waiting_dependency"
    RUNNING = "running"
    REVIEWING = "reviewing"
    PROOFREADING = "proofreading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchJobType(Enum):
    """批处理任务类型"""
    WRITING = "writing"
    REVIEW = "review"
    PROOFREAD = "proofread"
    FULL_PIPELINE = "full_pipeline"


@dataclass
class BatchJob:
    """批处理任务"""
    job_id: str
    novel_id: str
    chapter: int
    job_type: BatchJobType
    status: JobStatus = JobStatus.PENDING
    dependencies: List[int] = field(default_factory=list)  # 依赖的章节
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchProgress:
    """批处理进度"""
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    estimated_remaining: Optional[int] = None  # 预计剩余秒数
    current_chapter: Optional[int] = None


class BatchGenerator:
    """
    批量生成器

    使用示例：
    ```python
    from pipeline.novel_pipeline import NovelPipeline
    from core.state import NovelState
    
    # 创建 Pipeline 和 Generator
    pipeline = NovelPipeline(...)
    generator = BatchGenerator(pipeline, max_workers=3)
    
    # 定义依赖关系（第2章依赖第1章，其他独立）
    dependencies = {
        2: [1]
    }
    
    # 批量生成
    initial_state = NovelState(novel_id="my_novel", ...)
    results = generator.generate_chapters(
        initial_state=initial_state,
        chapters=[1, 2, 3, 4, 5],
        dependencies=dependencies
    )
    
    # 查看进度
    progress = generator.get_progress()
    ```
    """

    def __init__(
        self,
        pipeline: Any,  # NovelPipeline 实例
        max_workers: int = 3,
        checkpoint_dir: Optional[str] = None
    ):
        self.pipeline = pipeline
        self.max_workers = max_workers
        self.checkpoint_dir = checkpoint_dir or "./batch_checkpoints"
        
        # 任务存储
        self.jobs: Dict[str, BatchJob] = {}
        self.job_results: Dict[int, Any] = {}
        
        # 状态锁
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running = False
        
        # 确保目录存在
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def generate_chapters(
        self,
        initial_state: Any,  # NovelState
        chapters: List[int],
        dependencies: Optional[Dict[int, List[int]]] = None,
        job_type: BatchJobType = BatchJobType.FULL_PIPELINE
    ) -> Dict[int, Any]:
        """
        批量生成章节
        
        Args:
            initial_state: 初始状态
            chapters: 要生成的章节列表
            dependencies: 依赖关系 {章节: [依赖的章节]}
            job_type: 任务类型
        
        Returns:
            Dict[int, Any]: 章节结果
        """
        dependencies = dependencies or {}
        
        # 创建任务
        for chapter in chapters:
            job_id = f"{initial_state.novel_id}_ch{chapter}_{int(time.time())}"
            job = BatchJob(
                job_id=job_id,
                novel_id=initial_state.novel_id,
                chapter=chapter,
                job_type=job_type,
                dependencies=dependencies.get(chapter, []),
                created_at=datetime.now().isoformat()
            )
            self.jobs[job_id] = job
        
        # 排序任务（基于依赖关系）
        sorted_chapters = self._sort_by_dependencies(chapters, dependencies)
        print(f"📋 执行顺序: {sorted_chapters}")
        
        # 开始执行
        self._running = True
        
        try:
            # 创建执行器
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._executor = executor
                
                # 跟踪每个章节的 future
                futures: Dict[int, Future] = {}
                
                # 等待队列（章节：所有依赖的 future）
                waiting_queue: Dict[int, List[int]] = {}
                
                # 初始队列（没有依赖的章节）
                ready_queue = []
                
                for chapter in sorted_chapters:
                    deps = dependencies.get(chapter, [])
                    if not deps:
                        ready_queue.append(chapter)
                    else:
                        waiting_queue[chapter] = deps
                
                # 提交初始任务
                for chapter in ready_queue:
                    futures[chapter] = executor.submit(
                        self._run_chapter_job,
                        initial_state,
                        chapter,
                        job_type
                    )
                
                # 监控完成的任务，触发依赖任务
                completed = set()
                
                while futures and self._running:
                    # 等待任一任务完成
                    done_futures = []
                    for chapter, future in list(futures.items()):
                        if future.done():
                            done_futures.append((chapter, future))
                    
                    for chapter, future in done_futures:
                        # 移除已完成
                        del futures[chapter]
                        completed.add(chapter)
                        
                        # 获取结果
                        try:
                            result = future.result()
                            self.job_results[chapter] = result
                            self._update_job_status(chapter, JobStatus.COMPLETED)
                        except Exception as e:
                            self._update_job_status(chapter, JobStatus.FAILED, str(e))
                            print(f"❌ 第 {chapter} 章失败: {e}")
                        
                        # 检查是否有依赖于该章节的任务可以开始
                        for waiting_chapter, waiting_deps in list(waiting_queue.items()):
                            # 移除已完成的依赖
                            waiting_deps = [d for d in waiting_deps if d not in completed]
                            
                            if not waiting_deps:
                                # 所有依赖完成，开始任务
                                print(f"▶️ 第 {waiting_chapter} 章所有依赖完成，开始执行...")
                                del waiting_queue[waiting_chapter]
                                futures[waiting_chapter] = executor.submit(
                                    self._run_chapter_job,
                                    initial_state,
                                    waiting_chapter,
                                    job_type
                                )
                            else:
                                waiting_queue[waiting_chapter] = waiting_deps
                    
                    # 短暂休眠避免 CPU 空转
                    time.sleep(0.5)
                
        finally:
            self._running = False
            self._executor = None
        
        return self.job_results
    
    def batch_review(
        self,
        chapters: Dict[int, Any],  # 章节内容
        parallel: bool = True
    ) -> Dict[int, Any]:
        """
        批量审核
        
        Args:
            chapters: 章节内容 {章节: 内容}
            parallel: 是否并行执行
        
        Returns:
            Dict[int, Any]: 审核结果
        """
        print(f"🔍 开始批量审核 {len(chapters)} 个章节...")
        
        results = {}
        
        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._review_single, chapter, content): chapter
                    for chapter, content in chapters.items()
                }
                
                for future in as_completed(futures):
                    chapter = futures[future]
                    try:
                        results[chapter] = future.result()
                    except Exception as e:
                        print(f"❌ 第 {chapter} 章审核失败: {e}")
        else:
            for chapter, content in chapters.items():
                results[chapter] = self._review_single(chapter, content)
        
        print(f"✅ 批量审核完成: {len(results)} / {len(chapters)}")
        return results
    
    def batch_proofread(
        self,
        chapters: Dict[int, Any],
        parallel: bool = True
    ) -> Dict[int, Any]:
        """
        批量校对
        
        Args:
            chapters: 章节内容
            parallel: 是否并行执行
        
        Returns:
            Dict[int, Any]: 校对结果
        """
        print(f"📝 开始批量校对 {len(chapters)} 个章节...")
        
        results = {}
        
        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._proofread_single, chapter, content): chapter
                    for chapter, content in chapters.items()
                }
                
                for future in as_completed(futures):
                    chapter = futures[future]
                    try:
                        results[chapter] = future.result()
                    except Exception as e:
                        print(f"❌ 第 {chapter} 章校对失败: {e}")
        else:
            for chapter, content in chapters.items():
                results[chapter] = self._proofread_single(chapter, content)
        
        print(f"✅ 批量校对完成: {len(results)} / {len(chapters)}")
        return results
    
    def get_progress(self) -> BatchProgress:
        """获取当前进度"""
        with self._lock:
            progress = BatchProgress(total=len(self.jobs))
            
            for job in self.jobs.values():
                if job.status == JobStatus.PENDING:
                    progress.pending += 1
                elif job.status == JobStatus.WAITING_DEPENDENCY:
                    progress.pending += 1
                elif job.status == JobStatus.RUNNING:
                    progress.running += 1
                    progress.current_chapter = job.chapter
                elif job.status == JobStatus.COMPLETED:
                    progress.completed += 1
                elif job.status == JobStatus.FAILED:
                    progress.failed += 1
                elif job.status == JobStatus.CANCELLED:
                    progress.cancelled += 1
            
            # 简单的 ETA 估算（如果有已完成的）
            if progress.completed > 0:
                created_times = []
                for job in self.jobs.values():
                    if not job.created_at:
                        continue
                    try:
                        created_times.append(datetime.fromisoformat(job.created_at).timestamp())
                    except ValueError:
                        continue

                if created_times:
                    elapsed = time.time() - min(created_times)
                    avg_per_chapter = elapsed / progress.completed
                    progress.estimated_remaining = int(
                        avg_per_chapter * (progress.total - progress.completed)
                    )
            
            return progress
    
    def cancel_all(self):
        """取消所有未完成的任务"""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        
        with self._lock:
            for job in self.jobs.values():
                if job.status in [JobStatus.PENDING, JobStatus.WAITING_DEPENDENCY, JobStatus.RUNNING]:
                    job.status = JobStatus.CANCELLED
        
        print("🛑 所有任务已取消")
    
    def save_checkpoint(self):
        """保存检查点"""
        checkpoint_file = os.path.join(self.checkpoint_dir, f"batch_checkpoint_{int(time.time())}.json")
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "jobs": [self._job_to_dict(job) for job in self.jobs.values()],
            "results": {str(chap): res for chap, res in self.job_results.items()}
        }
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 检查点已保存: {checkpoint_file}")
    
    def _run_chapter_job(
        self,
        initial_state: Any,
        chapter: int,
        job_type: BatchJobType
    ) -> Any:
        """运行单个章节任务"""
        print(f"▶️ 开始执行第 {chapter} 章...")
        self._update_job_status(chapter, JobStatus.RUNNING)
        
        try:
            # 复制初始状态，设置当前章节
            state = initial_state.__class__(**initial_state.__dict__)
            state.current_chapter = chapter
            state.chapter_status = {}
            
            # 根据任务类型执行
            if job_type == BatchJobType.FULL_PIPELINE:
                result = self.pipeline.run(state)
            elif job_type == BatchJobType.WRITING:
                # 只写作（需要调整 pipeline）
                result = self.pipeline.run(state)
            else:
                result = self.pipeline.run(state)
            
            self._update_job_status(chapter, JobStatus.COMPLETED)
            print(f"✅ 第 {chapter} 章完成")
            return result
            
        except Exception as e:
            self._update_job_status(chapter, JobStatus.FAILED, str(e))
            raise
    
    def _review_single(self, chapter: int, content: Any) -> Any:
        """审核单个章节"""
        print(f"🔍 审核第 {chapter} 章...")
        # 这里调用 pipeline 的 reviewer
        # 简化实现
        return {"chapter": chapter, "status": "reviewed"}
    
    def _proofread_single(self, chapter: int, content: Any) -> Any:
        """校对单个章节"""
        print(f"📝 校对第 {chapter} 章...")
        # 这里调用 pipeline 的 proofreader
        # 简化实现
        return {"chapter": chapter, "status": "proofread"}
    
    def _update_job_status(
        self,
        chapter: int,
        status: JobStatus,
        error_message: Optional[str] = None
    ):
        """更新任务状态"""
        with self._lock:
            for job in self.jobs.values():
                if job.chapter == chapter:
                    job.status = status
                    if status == JobStatus.RUNNING:
                        job.started_at = datetime.now().isoformat()
                    if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                        job.completed_at = datetime.now().isoformat()
                    if error_message:
                        job.error_message = error_message
                    break
    
    def _sort_by_dependencies(
        self,
        chapters: List[int],
        dependencies: Dict[int, List[int]]
    ) -> List[int]:
        """根据依赖关系排序章节（拓扑排序）"""
        # 构建邻接表
        graph = {chapter: [] for chapter in chapters}
        for chapter, deps in dependencies.items():
            if chapter in graph:
                for dep in deps:
                    if dep in graph:
                        graph[dep].append(chapter)
        
        # 计算入度
        in_degree = {chapter: 0 for chapter in chapters}
        for chapter, deps in dependencies.items():
            if chapter in in_degree:
                in_degree[chapter] = len(deps)
        
        # 拓扑排序
        queue = [chapter for chapter in chapters if in_degree[chapter] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 如果有循环依赖，剩下的按原顺序追加
        if len(result) < len(chapters):
            remaining = [ch for ch in chapters if ch not in result]
            result.extend(remaining)
            print(f"⚠️ 检测到循环依赖: {remaining}")
        
        return result
    
    def _job_to_dict(self, job: BatchJob) -> Dict:
        """BatchJob 转 dict"""
        return {
            "job_id": job.job_id,
            "novel_id": job.novel_id,
            "chapter": job.chapter,
            "job_type": job.job_type.value,
            "status": job.status.value,
            "dependencies": job.dependencies,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "metadata": job.metadata
        }
