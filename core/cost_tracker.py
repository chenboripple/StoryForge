"""
StoryForge - 成本监控与缓存系统
追踪 LLM 调用成本，实现 Prompt 缓存
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import json
import hashlib
import os


@dataclass
class LLMCallRecord:
    """单次 LLM 调用记录"""
    agent_name: str
    task_type: str          # writer / reviewer / reviser / proofreader / outline
    prompt_hash: str        # prompt 的哈希值（用于缓存匹配）
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    cached: bool = False    # 是否命中缓存
    duration_ms: float = 0.0
    success: bool = True


class PromptCache:
    """
    Prompt 缓存系统
    
    缓存策略：
    1. 基于 prompt 内容哈希匹配
    2. 缓存有效期：24小时（可配置）
    3. 按任务类型分桶缓存
    """
    
    def __init__(self, cache_dir: str = ".prompt_cache", ttl_hours: float = 24.0):
        self.cache_dir = cache_dir
        self.ttl_hours = ttl_hours
        self._memory_cache: Dict[str, Dict] = {}  # 内存缓存
        self._hit_count = 0
        self._miss_count = 0
        
        os.makedirs(cache_dir, exist_ok=True)
        self._load_cache()
    
    def _get_cache_path(self, task_type: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{task_type}_cache.json")
    
    def _load_cache(self):
        """从磁盘加载缓存"""
        for fname in os.listdir(self.cache_dir):
            if fname.endswith('_cache.json'):
                task_type = fname.replace('_cache.json', '')
                path = os.path.join(self.cache_dir, fname)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        self._memory_cache[task_type] = json.load(f)
                except:
                    self._memory_cache[task_type] = {}
    
    def _save_cache(self, task_type: str):
        """保存缓存到磁盘"""
        path = self._get_cache_path(task_type)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._memory_cache.get(task_type, {}), f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ 缓存保存失败: {e}")
    
    def _compute_hash(self, prompt: str) -> str:
        """计算 prompt 哈希"""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]
    
    def _is_expired(self, timestamp: str) -> bool:
        """检查缓存是否过期"""
        try:
            cached_time = datetime.fromisoformat(timestamp)
            elapsed = (datetime.now() - cached_time).total_seconds() / 3600
            return elapsed > self.ttl_hours
        except:
            return True
    
    def get(self, prompt: str, task_type: str) -> Optional[str]:
        """
        获取缓存结果
        
        Returns:
            缓存的 LLM 输出，未命中返回 None
        """
        prompt_hash = self._compute_hash(prompt)
        cache_bucket = self._memory_cache.get(task_type, {})
        
        if prompt_hash not in cache_bucket:
            self._miss_count += 1
            return None
        
        entry = cache_bucket[prompt_hash]
        
        # 检查是否过期
        if self._is_expired(entry.get("timestamp", "")):
            del cache_bucket[prompt_hash]
            self._miss_count += 1
            return None
        
        self._hit_count += 1
        return entry.get("result")
    
    def put(self, prompt: str, task_type: str, result: str):
        """存入缓存"""
        prompt_hash = self._compute_hash(prompt)
        
        if task_type not in self._memory_cache:
            self._memory_cache[task_type] = {}
        
        self._memory_cache[task_type][prompt_hash] = {
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "prompt_length": len(prompt)
        }
        
        # 异步保存（不阻塞主流程）
        self._save_cache(task_type)
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        return {
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": f"{hit_rate:.1%}",
            "memory_entries": sum(len(v) for v in self._memory_cache.values()),
            "ttl_hours": self.ttl_hours
        }
    
    def clear(self, task_type: Optional[str] = None):
        """清除缓存"""
        if task_type:
            self._memory_cache.pop(task_type, None)
            path = self._get_cache_path(task_type)
            if os.path.exists(path):
                os.remove(path)
        else:
            self._memory_cache.clear()
            for fname in os.listdir(self.cache_dir):
                if fname.endswith('_cache.json'):
                    os.remove(os.path.join(self.cache_dir, fname))


class CostTracker:
    """
    成本追踪器
    
    功能：
    1. 统计每次 LLM 调用的 Token 消耗和成本
    2. 按 Agent / 任务类型汇总
    3. 成本阈值告警
    4. 生成成本报告
    """
    
    # 默认价格（USD per 1K tokens）- 可根据实际模型调整
    DEFAULT_PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "default": {"input": 0.01, "output": 0.03}
    }
    
    def __init__(
        self,
        model_name: str = "default",
        cost_threshold_usd: float = 10.0,  # 成本告警阈值
        prompt_cache: Optional[PromptCache] = None
    ):
        self.model_name = model_name
        self.pricing = self.DEFAULT_PRICING.get(model_name, self.DEFAULT_PRICING["default"])
        self.cost_threshold = cost_threshold_usd
        self.prompt_cache = prompt_cache or PromptCache()
        self.records: List[LLMCallRecord] = []
        self._total_cost = 0.0
        self._total_tokens = 0
        self._alert_triggered = False
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本的 Token 数（粗略估计：1 token ≈ 4 字符）"""
        return len(text) // 4
    
    def record_call(
        self,
        agent_name: str,
        task_type: str,
        prompt: str,
        result: str,
        cached: bool = False,
        duration_ms: float = 0.0,
        success: bool = True
    ) -> LLMCallRecord:
        """记录一次 LLM 调用"""
        prompt_tokens = self.estimate_tokens(prompt)
        completion_tokens = self.estimate_tokens(result)
        total_tokens = prompt_tokens + completion_tokens
        
        # 计算成本
        if cached:
            cost = 0.0  # 缓存命中无成本
        else:
            input_cost = (prompt_tokens / 1000) * self.pricing["input"]
            output_cost = (completion_tokens / 1000) * self.pricing["output"]
            cost = input_cost + output_cost
        
        record = LLMCallRecord(
            agent_name=agent_name,
            task_type=task_type,
            prompt_hash=self.prompt_cache._compute_hash(prompt),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            cached=cached,
            duration_ms=duration_ms,
            success=success
        )
        
        self.records.append(record)
        self._total_cost += cost
        self._total_tokens += total_tokens
        
        # 检查成本阈值
        if not self._alert_triggered and self._total_cost >= self.cost_threshold:
            self._alert_triggered = True
            print(f"🚨 成本告警：累计成本 ${self._total_cost:.4f} 已超过阈值 ${self.cost_threshold:.2f}")
        
        return record
    
    def should_pause(self) -> bool:
        """检查是否应该暂停（成本超限）"""
        return self._total_cost >= self.cost_threshold * 2  # 2倍阈值时强制暂停
    
    def get_summary(self) -> Dict:
        """获取成本汇总"""
        by_agent = {}
        by_task = {}
        
        for r in self.records:
            by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + r.cost_usd
            by_task[r.task_type] = by_task.get(r.task_type, 0) + r.cost_usd
        
        return {
            "total_cost_usd": round(self._total_cost, 4),
            "total_tokens": self._total_tokens,
            "total_calls": len(self.records),
            "cached_calls": sum(1 for r in self.records if r.cached),
            "by_agent": {k: round(v, 4) for k, v in by_agent.items()},
            "by_task": {k: round(v, 4) for k, v in by_task.items()},
            "cost_threshold": self.cost_threshold,
            "threshold_exceeded": self._total_cost >= self.cost_threshold,
            "cache_stats": self.prompt_cache.get_stats()
        }
    
    def get_chapter_report(self, chapter_num: int) -> Dict:
        """获取指定章节的成本报告"""
        chapter_records = [r for r in self.records if r.task_type.endswith(f"_ch{chapter_num}")]
        
        return {
            "chapter": chapter_num,
            "calls": len(chapter_records),
            "tokens": sum(r.total_tokens for r in chapter_records),
            "cost_usd": round(sum(r.cost_usd for r in chapter_records), 4),
            "by_agent": {
                r.agent_name: round(r.cost_usd, 4)
                for r in chapter_records
            }
        }
    
    def export_report(self, filepath: str):
        """导出完整成本报告到文件"""
        report = {
            "model": self.model_name,
            "pricing": self.pricing,
            "summary": self.get_summary(),
            "records": [
                {
                    "agent": r.agent_name,
                    "task": r.task_type,
                    "tokens": r.total_tokens,
                    "cost": r.cost_usd,
                    "cached": r.cached,
                    "duration_ms": r.duration_ms,
                    "timestamp": r.timestamp
                }
                for r in self.records
            ]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"📊 成本报告已导出: {filepath}")


def create_cached_llm_wrapper(
    llm_client: Callable,
    cost_tracker: CostTracker,
    task_type: str = "default"
):
    """
    创建带缓存和成本追踪的 LLM 包装器
    
    Usage:
        cached_llm = create_cached_llm_wrapper(
            llm_client=openai_client,
            cost_tracker=cost_tracker,
            task_type="writer"
        )
        result = cached_llm("prompt text")
    """
    import time
    
    def wrapper(prompt: str, **kwargs) -> str:
        cache = cost_tracker.prompt_cache
        
        # 1. 尝试命中缓存
        cached_result = cache.get(prompt, task_type)
        if cached_result is not None:
            cost_tracker.record_call(
                agent_name=kwargs.get("agent_name", "unknown"),
                task_type=task_type,
                prompt=prompt,
                result=cached_result,
                cached=True
            )
            return cached_result
        
        # 2. 检查成本阈值
        if cost_tracker.should_pause():
            raise RuntimeError(
                f"成本已超限（累计 ${cost_tracker._total_cost:.4f}），"
                f"超过阈值 ${cost_tracker.cost_threshold:.2f} 的2倍，暂停执行"
            )
        
        # 3. 调用真实 LLM
        start = time.time()
        try:
            result = llm_client(prompt, **kwargs)
            duration = (time.time() - start) * 1000
            
            # 4. 记录成本
            cost_tracker.record_call(
                agent_name=kwargs.get("agent_name", "unknown"),
                task_type=task_type,
                prompt=prompt,
                result=result,
                cached=False,
                duration_ms=duration
            )
            
            # 5. 存入缓存
            cache.put(prompt, task_type, result)
            
            return result
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            cost_tracker.record_call(
                agent_name=kwargs.get("agent_name", "unknown"),
                task_type=task_type,
                prompt=prompt,
                result="",
                cached=False,
                duration_ms=duration,
                success=False
            )
            raise
    
    return wrapper
