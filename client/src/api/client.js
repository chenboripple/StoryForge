// API 客户端
//
// 开发模式下 CRA 通过 package.json 中的 "proxy" 字段把 /api/* 转发到 Flask。
// 生产模式下，Flask 直接服务 client/build。

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

async function request(path) {
  const res = await fetch(path);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listNovels: () => request("/api/novels"),
  getNovel: (novelId) => request(`/api/novels/${encodeURIComponent(novelId)}`),
  listChapters: (novelId) =>
    request(`/api/novels/${encodeURIComponent(novelId)}/chapters`),
  getChapter: (novelId, chapterNum) =>
    request(
      `/api/novels/${encodeURIComponent(novelId)}/chapters/${chapterNum}`
    ),
};

export const labels = {
  stage: (s) => STAGE_LABELS[s] || s,
  status: (s) => STATUS_LABELS[s] || s,
  statusTone: (s) => STATUS_TONE[s] || "gray",
};
