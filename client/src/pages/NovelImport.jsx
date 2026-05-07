import React, { useState, useCallback } from "react";

/**
 * 小说导入页面
 * 支持 txt/md/epub/pdf/图片 格式上传、预览、保存
 */
export default function NovelImport() {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [editing, setEditing] = useState(false);
  const [novelData, setNovelData] = useState({
    title: "",
    author: "",
    genre: "未分类",
    concept: "",
    chapters: [],
  });

  const supportedExts = [
    ".txt", ".md", ".markdown", ".html", ".htm", ".rst", ".org",
    ".epub", ".pdf",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
  ];

  const onDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFile = (f) => {
    const ext = f.name.toLowerCase().substring(f.name.lastIndexOf("."));
    if (!supportedExts.includes(ext)) {
      setError(`不支持的文件格式: ${ext}。支持的格式: ${supportedExts.join(", ")}`);
      return;
    }
    setFile(f);
    setError("");
    setResult(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/import/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!data.success) {
        setError(data.errors?.join("\n") || "解析失败");
        setLoading(false);
        return;
      }

      setResult(data);
      setNovelData({
        title: data.preview.title,
        author: data.preview.author,
        genre: data.preview.genre || "未分类",
        concept: "",
        chapters: data.full_result.chapters.map((ch) => ({
          chapter_num: ch.chapter_num,
          title: ch.title,
          content: ch.content,
          word_count: ch.word_count,
        })),
      });

      if (data.warnings?.length > 0) {
        setError(data.warnings.join("\n"));
      }
    } catch (e) {
      setError(`上传失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/import/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: novelData.title,
          author: novelData.author,
          genre: novelData.genre,
          concept: novelData.concept,
          chapters: novelData.chapters,
        }),
      });
      const data = await res.json();

      if (data.success) {
        alert(`导入成功！小说ID: ${data.novel_id}\n共 ${data.chapter_count} 章`);
        // 跳转到小说列表
        window.location.href = "/";
      } else {
        setError(data.error || "保存失败");
      }
    } catch (e) {
      setError(`保存失败: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleChapterChange = (idx, field, value) => {
    const newChapters = [...novelData.chapters];
    newChapters[idx] = { ...newChapters[idx], [field]: value };
    setNovelData({ ...novelData, chapters: newChapters });
  };

  const handleRemoveChapter = (idx) => {
    const newChapters = novelData.chapters.filter((_, i) => i !== idx);
    setNovelData({ ...novelData, chapters: newChapters });
  };

  return (
    <div className="novel-import">
      <h2>导入小说</h2>
      <p className="hint">
        支持格式：txt, md, html, epub, pdf, 图片（jpg/png 等）
      </p>

      {/* 上传区域 */}
      <div
        className={`upload-zone ${dragActive ? "drag-active" : ""} ${file ? "has-file" : ""}`}
        onDragEnter={onDrag}
        onDragOver={onDrag}
        onDragLeave={onDrag}
        onDrop={onDrop}
      >
        <input
          type="file"
          id="file-input"
          accept={supportedExts.join(",")}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          hidden
        />
        <label htmlFor="file-input" className="upload-label">
          {file ? (
            <>
              <span className="file-name">{file.name}</span>
              <span className="file-size">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            </>
          ) : (
            <>
              <span className="upload-icon">📁</span>
              <span>点击选择文件，或拖拽文件到此处</span>
            </>
          )}
        </label>
      </div>

      {/* 操作按钮 */}
      {file && !result && (
        <div className="actions">
          <button onClick={handleUpload} disabled={loading} className="btn-primary">
            {loading ? "解析中..." : "开始解析"}
          </button>
          <button
            onClick={() => { setFile(null); setError(""); }}
            className="btn-secondary"
            disabled={loading}
          >
            重新选择
          </button>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="error-box">
          <pre>{error}</pre>
        </div>
      )}

      {/* 解析结果预览 */}
      {result && result.preview && (
        <div className="import-result">
          <h3>解析结果</h3>

          {/* 基本信息 */}
          <div className="meta-section">
            <div className="form-row">
              <label>书名</label>
              <input
                type="text"
                value={novelData.title}
                onChange={(e) => setNovelData({ ...novelData, title: e.target.value })}
              />
            </div>
            <div className="form-row">
              <label>作者</label>
              <input
                type="text"
                value={novelData.author}
                onChange={(e) => setNovelData({ ...novelData, author: e.target.value })}
              />
            </div>
            <div className="form-row">
              <label>类型</label>
              <select
                value={novelData.genre}
                onChange={(e) => setNovelData({ ...novelData, genre: e.target.value })}
              >
                <option>未分类</option>
                <option>科幻</option>
                <option>玄幻</option>
                <option>都市</option>
                <option>历史</option>
                <option>悬疑</option>
                <option>言情</option>
                <option>其他</option>
              </select>
            </div>
            <div className="form-row">
              <label>简介</label>
              <textarea
                rows={3}
                value={novelData.concept}
                onChange={(e) => setNovelData({ ...novelData, concept: e.target.value })}
                placeholder="可选，填写小说简介"
              />
            </div>
          </div>

          {/* 统计 */}
          <div className="stats-bar">
            <span>共 {result.preview.total_chapters} 章</span>
            <span>总字数: {result.preview.total_word_count.toLocaleString()}</span>
            {result.warnings?.length > 0 && (
              <span className="warning">⚠️ {result.warnings.length} 个警告</span>
            )}
          </div>

          {/* 章节列表 */}
          <div className="chapters-section">
            <div className="section-header">
              <h4>章节列表</h4>
              <label className="toggle-edit">
                <input
                  type="checkbox"
                  checked={editing}
                  onChange={(e) => setEditing(e.target.checked)}
                />
                编辑模式
              </label>
            </div>

            {novelData.chapters.map((ch, idx) => (
              <div key={idx} className="chapter-item">
                {editing ? (
                  <div className="chapter-edit">
                    <input
                      type="text"
                      value={ch.title}
                      onChange={(e) => handleChapterChange(idx, "title", e.target.value)}
                      className="chapter-title-input"
                    />
                    <textarea
                      value={ch.content}
                      onChange={(e) => handleChapterChange(idx, "content", e.target.value)}
                      rows={6}
                      className="chapter-content-input"
                    />
                    <div className="chapter-meta">
                      <span>字数: {ch.word_count?.toLocaleString() || ch.content.length}</span>
                      <button
                        className="btn-danger"
                        onClick={() => handleRemoveChapter(idx)}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="chapter-preview">
                    <div className="chapter-header">
                      <span className="chapter-num">第{ch.chapter_num}章</span>
                      <span className="chapter-title">{ch.title}</span>
                      <span className="chapter-count">
                        {ch.word_count?.toLocaleString() || ch.content.length} 字
                      </span>
                    </div>
                    <pre className="chapter-text">
                      {ch.content?.substring(0, 300)}
                      {ch.content?.length > 300 ? "..." : ""}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 保存按钮 */}
          <div className="actions save-actions">
            <button onClick={handleSave} disabled={loading} className="btn-primary btn-large">
              {loading ? "保存中..." : "保存到小说库"}
            </button>
            <button
              onClick={() => { setFile(null); setResult(null); setError(""); }}
              className="btn-secondary"
              disabled={loading}
            >
              重新导入
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
