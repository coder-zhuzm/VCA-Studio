import { Layout, Menu, Typography } from 'antd'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Create } from './pages/Create'
import { Home } from './pages/Home'
import { Models } from './pages/Models'
import { Runtime } from './pages/Runtime'
import { Works } from './pages/Works'

const items = [
  { key: '/', label: <Link to="/">首页</Link> },
  { key: '/runtime', label: <Link to="/runtime">运行环境</Link> },
  { key: '/models', label: <Link to="/models">模型管理</Link> },
  { key: '/create', label: <Link to="/create">新建翻唱</Link> },
  { key: '/works', label: <Link to="/works">作品库</Link> },
]

export function App() {
  const location = useLocation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider width={220} theme="dark">
        <Typography.Title level={4} style={{ color: 'white', padding: '20px 20px 8px', margin: 0 }}>
          VCA-Studio
        </Typography.Title>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={items} />
      </Layout.Sider>
      <Layout>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/runtime" element={<Runtime />} />
            <Route path="/models" element={<Models />} />
            <Route path="/create" element={<Create />} />
            <Route path="/works" element={<Works />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
