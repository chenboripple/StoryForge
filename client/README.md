# StoryForge Web 客户端

基于 Create React App 的前端，展示小说清单和创作进展。

## 启动

```bash
cd client
npm install
npm start
```

开发模式默认在 http://localhost:3000，并通过 `package.json` 中的 `proxy` 把 `/api/v1/*` 请求转发到 FastAPI 网关 (http://localhost:5089)。

## 构建

```bash
npm run build
```

构建产物输出到 `client/build/`，统一由 FastAPI 网关 (`web_console/app.py`) 通过 `StaticFiles` 挂载在 `/` 路径。

## 文件结构

```
client/
├── public/
│   └── index.html
├── src/
│   ├── api/client.js     # API 调用封装
│   ├── pages/
│   │   ├── NovelList.jsx # 小说清单
│   │   └── NovelDetail.jsx # 小说详情/章节
│   ├── App.jsx
│   ├── index.css
│   └── index.js
└── package.json
```
