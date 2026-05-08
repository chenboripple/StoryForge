import React from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import { Layout, Menu, Typography } from "antd";
import {
  BookOutlined,
  ImportOutlined,
  FileSearchOutlined,
  RocketOutlined,
  HomeOutlined,
} from "@ant-design/icons";

import NovelList from "./pages/NovelList";
import NovelDetail from "./pages/NovelDetail";
import NovelImport from "./pages/NovelImport";
import Extraction from "./pages/Extraction";
import IPGeneration from "./pages/IPGeneration";

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  {
    key: "/",
    icon: <HomeOutlined />,
    label: <Link to="/">首页</Link>,
  },
  {
    key: "/novels",
    icon: <BookOutlined />,
    label: <Link to="/">小说管理</Link>,
  },
  {
    key: "/import",
    icon: <ImportOutlined />,
    label: <Link to="/import">导入小说</Link>,
  },
  {
    key: "/extraction",
    icon: <FileSearchOutlined />,
    label: <Link to="/extraction">萃取</Link>,
  },
  {
    key: "/ip-generation",
    icon: <RocketOutlined />,
    label: <Link to="/ip-generation">IP 生成</Link>,
  },
];

export default function App() {
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ display: "flex", alignItems: "center", background: "#001529" }}>
        <Title level={4} style={{ color: "white", margin: 0, marginRight: 48 }}>
          StoryForge
        </Title>
        <span style={{ color: "rgba(255,255,255,0.65)", fontSize: 14 }}>
          多 Agent 小说创作平台
        </span>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: "#fff" }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: "100%", borderRight: 0 }}
            items={menuItems}
          />
        </Sider>
        <Layout style={{ padding: "24px" }}>
          <Content
            style={{
              background: "#fff",
              padding: 24,
              margin: 0,
              minHeight: 280,
              borderRadius: 8,
            }}
          >
            <Routes>
              <Route path="/" element={<NovelList />} />
              <Route path="/novels/:novelId" element={<NovelDetail />} />
              <Route path="/import" element={<NovelImport />} />
              <Route path="/extraction" element={<Extraction />} />
              <Route path="/ip-generation" element={<IPGeneration />} />
              <Route path="*" element={<div>页面不存在</div>} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}
