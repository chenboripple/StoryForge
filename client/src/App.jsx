import React from "react";
import { Routes, Route, Link } from "react-router-dom";
import NovelList from "./pages/NovelList";
import NovelDetail from "./pages/NovelDetail";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
          <h1>StoryForge</h1>
        </Link>
        <span className="tagline">多 Agent 小说创作平台</span>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<NovelList />} />
          <Route path="/novels/:novelId" element={<NovelDetail />} />
          <Route
            path="*"
            element={<div className="empty">页面不存在</div>}
          />
        </Routes>
      </main>
    </div>
  );
}
