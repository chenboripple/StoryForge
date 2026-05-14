// API 客户端
//
// 开发模式下 CRA 通过 package.json 中的 "proxy" 字段把 /api/* 转发到后端。
// 生产模式下，后端直接服务 client/build。

const API_BASE = "/api/v1";

const STAGE_LABELS = {
  creation: "创作中",
  extraction: "萃取中",
  ip_generation: "IP生成中",
};

const STATUS_LABELS = {
  pending: "待写作",
  draft: "初稿",
  in_review: "审稿中",
  revising: "修改中",
  proofreading: "校对中",
  approved: "已通过",
  rejected: "被驳回",
};

const STATUS_TONE = {
  approved: "green",
  draft: "yellow",
  in_review: "yellow",
  revising: "yellow",
  proofreading: "yellow",
  rejected: "red",
  pending: "gray",
};

async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listNovels: () => request(`${API_BASE}/novels`),
  createNovel: (data) =>
    request(`${API_BASE}/novels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  getNovel: (novelId) =>
    request(`${API_BASE}/novels/${encodeURIComponent(novelId)}`),
  listChapters: (novelId) =>
    request(`${API_BASE}/novels/${encodeURIComponent(novelId)}/chapters`),
  getChapter: (novelId, chapterNum) =>
    request(
      `${API_BASE}/novels/${encodeURIComponent(novelId)}/chapters/${chapterNum}`
    ),
  listImportFormats: () => request(`${API_BASE}/import/formats`),
  uploadFile: (formData) =>
    fetch(`${API_BASE}/import/upload`, {
      method: "POST",
      body: formData,
    }).then((res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    }),
  saveImported: (data) =>
    fetch(`${API_BASE}/import/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    }),
};

export const labels = {
  stage: (s) => STAGE_LABELS[s] || s,
  status: (s) => STATUS_LABELS[s] || s,
  statusTone: (s) => STATUS_TONE[s] || "gray",
};
