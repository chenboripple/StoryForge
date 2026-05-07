import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, labels } from "../api/client";

const PIPELINE_STEPS = [
  { key: "creation", label: "创作层" },
  { key: "extraction", label: "萃取层" },
  { key: "ip_generation", label: "IP 生成层" },
];

function Pipeline({ stage }) {
  return (
    <div className="pipeline">
      {PIPELINE_STEPS.map((step, i) => (
        <React.Fragment key={step.key}>
          <span className={`step ${stage === step.key ? "active" : ""}`}>
            {step.label}
          </span>
          {i < PIPELINE_STEPS.length - 1 && <span className="arrow">→</span>}
        </React.Fragment>
      ))}
    </div>
  );
}

function ChapterDetail({ novelId, chapterNum, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api
      .getChapter(novelId, chapterNum)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [novelId, chapterNum]);

  if (error) return <div className="error">章节加载失败：{error}</div>;
  if (!data) return <div className="empty">加载章节中…</div>;

  return (
    <div className="detail-section">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h3 style={{ marginBottom: 0 }}>
          第 {data.chapter_num} 章 · {labels.status(data.status)} ·{" "}
          {data.word_count} 字
        </h3>
        <button onClick={onClose}>收起</button>
      </div>

      <div style={{ marginTop: 12 }}>
        <div className="chapter-content">{data.content}</div>
      </div>

      {data.reviews.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3>审稿记录</h3>
          {data.reviews.map((r) => (
            <div className="review-card" key={`r-${r.round}`}>
              <div className="head">
                <strong>
                  第 {r.round} 轮 · {r.reviewer} · {r.score} 分
                </strong>
                <span
                  className={`tag ${r.passed ? "green" : "yellow"}`}
                  style={{ marginRight: 0 }}
                >
                  {r.passed ? "通过" : "未通过"}
                </span>
              </div>
              <pre>{r.comments}</pre>
            </div>
          ))}
        </div>
      )}

      {data.proofread_records.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3>校对记录</h3>
          {data.proofread_records.map((p) => (
            <div className="review-card" key={`p-${p.round}`}>
              <div className="head">
                <strong>
                  第 {p.round} 轮 · {p.proofreader}
                </strong>
                <span
                  className={`tag ${p.passed ? "green" : "yellow"}`}
                  style={{ marginRight: 0 }}
                >
                  {p.passed ? "通过" : "需返工"}
                </span>
              </div>
              <pre>{p.comments}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NovelDetail() {
  const { novelId } = useParams();
  const [novel, setNovel] = useState(null);
  const [chapters, setChapters] = useState(null);
  const [error, setError] = useState(null);
  const [activeChapter, setActiveChapter] = useState(null);

  useEffect(() => {
    setNovel(null);
    setChapters(null);
    setError(null);
    Promise.all([api.getNovel(novelId), api.listChapters(novelId)])
      .then(([n, c]) => {
        setNovel(n);
        setChapters(c.chapters);
      })
      .catch((err) => setError(err.message));
  }, [novelId]);

  if (error) {
    return (
      <div>
        <Link to="/" className="back-link">
          ← 返回清单
        </Link>
        <div className="error">加载失败：{error}</div>
      </div>
    );
  }

  if (!novel || !chapters) {
    return <div className="empty">加载中…</div>;
  }

  const total = chapters.length;
  const approved = chapters.filter((c) => c.status === "approved").length;
  const pct = total === 0 ? 0 : Math.round((approved / total) * 100);

  return (
    <div>
      <Link to="/" className="back-link">
        ← 返回清单
      </Link>

      <div className="detail-header">
        <h2>{novel.novel_title || "未命名"}</h2>
        <span className="tag">{novel.genre || "未分类"}</span>
        <span className="tag gray">{labels.stage(novel.current_stage)}</span>
      </div>
      <p style={{ color: "var(--text-muted)", marginTop: 0 }}>
        {novel.concept || "—"}
      </p>

      <div className="detail-section">
        <h3>Pipeline 阶段</h3>
        <Pipeline stage={novel.current_stage} />
      </div>

      <div className="detail-section">
        <h3>创作进度</h3>
        <div style={{ marginBottom: 8, fontSize: 13 }}>
          {approved}/{total} 章已通过 · 当前推进至第 {novel.current_chapter} 章
        </div>
        <div className="progress">
          <span style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="detail-section">
        <h3>角色 ({novel.characters.length})</h3>
        {novel.characters.length === 0 ? (
          <div className="empty">尚未定义角色</div>
        ) : (
          <div className="character-list">
            {novel.characters.map((c) => (
              <div className="character" key={c.name}>
                <div className="name">
                  {c.name}
                  {c.age ? ` · ${c.age}岁` : ""}
                </div>
                <div className="small">{c.personality || "—"}</div>
                {c.background && (
                  <div className="small" style={{ marginTop: 4 }}>
                    {c.background}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-section">
        <h3>章节 ({total})</h3>
        {total === 0 ? (
          <div className="empty">还没有章节</div>
        ) : (
          chapters.map((c) => (
            <div
              key={c.chapter_num}
              className="chapter-row"
              onClick={() =>
                setActiveChapter(
                  activeChapter === c.chapter_num ? null : c.chapter_num
                )
              }
            >
              <span className="num">第 {c.chapter_num} 章</span>
              <span className="preview">{c.preview || "—"}</span>
              <span>
                <span className={`tag ${labels.statusTone(c.status)}`}>
                  {labels.status(c.status)}
                </span>
              </span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {c.latest_score != null ? `${c.latest_score}分` : "—"} ·{" "}
                {c.word_count}字
              </span>
            </div>
          ))
        )}
      </div>

      {activeChapter !== null && (
        <ChapterDetail
          novelId={novelId}
          chapterNum={activeChapter}
          onClose={() => setActiveChapter(null)}
        />
      )}
    </div>
  );
}
