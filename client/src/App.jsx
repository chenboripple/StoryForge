import React from "react";
import { Routes, Route, Link } from "react-router-dom";
import NovelList from "./pages/NovelList";
import NovelDetail from "./pages/NovelDetail";
import NovelImport from "./pages/NovelImport";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
          <h1>StoryForge</h1>
        </Link>
        <span className="tagline">多 Agent 小说创作平台</span>
        <nav className="app-nav">
          <Link to="/" className="nav-link">小说列表</Link>
          <Link to="/import" className="nav-link">导入小说</Link>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<NovelList />} />
          <Route path="/novels/:novelId" element={<NovelDetail />} />
          <Route path="/import" element={<NovelImport />} />
          <Route
            path="*"
            element={<div className="empty">页面不存在</div>}
          />
        </Routes>
      </main>
    </div>
  );
}
