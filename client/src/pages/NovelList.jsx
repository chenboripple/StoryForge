import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, labels } from "../api/client";

export default function NovelList() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listNovels()
      .then(setNovels)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div>
        <h2 className="page-title">小说清单</h2>
        <div className="error">加载失败：{error}</div>
      </div>
    );
  }

  if (novels === null) {
    return <div className="empty">加载中…</div>;
  }

  return (
    <div>
      <h2 className="page-title">小说清单</h2>
      <p className="page-subtitle">
        共 {novels.length} 部作品。点击卡片查看创作进展。
      </p>

      {novels.length === 0 ? (
        <div className="empty">还没有任何小说。运行 demo 生成示例数据。</div>
      ) : (
        <div className="card-grid">
          {novels.map((n) => {
            const total = n.total_chapters || 0;
            const approved = n.approved_chapters || 0;
            const pct = total === 0 ? 0 : Math.round((approved / total) * 100);
            return (
              <div
                key={n.novel_id}
                className="novel-card"
                onClick={() => navigate(`/novels/${n.novel_id}`)}
              >
                <div>
                  <span className="tag">{n.genre || "未分类"}</span>
                  <span className="tag gray">{labels.stage(n.current_stage)}</span>
                </div>
                <h3 className="title">{n.novel_title || "未命名"}</h3>
                <div className="concept">{n.concept || "—"}</div>
                <div className="footer">
                  <span>
                    第 {n.current_chapter || 1} 章 · {n.character_count || 0} 角色
                  </span>
                  <span>
                    {approved}/{total} 已通过 ({pct}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
