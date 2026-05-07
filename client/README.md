# StoryForge Web 客户端

基于 Create React App 的前端，展示小说清单和创作进展。

## 启动

```bash
cd client
npm install
npm start
```

开发模式默认在 http://localhost:3000，并通过 `package.json` 中的 `proxy` 把 `/api/*` 请求转发到 Flask 后端 (http://localhost:5000)。

## 构建

```bash
npm run build
```

构建产物输出到 `client/build/`，Flask (`backend/app.py`) 会自动作为静态资源服务它。

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
