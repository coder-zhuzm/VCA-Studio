import { Button, Card, Descriptions, Space, Spin, Table, Tag, Typography, message } from 'antd'
import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AppStatus, WorkRecord, WorkStatus } from '../api/types'

const STATUS_COLOR: Record<WorkStatus, string> = {
  pending: 'blue',
  running: 'processing',
  done: 'green',
  failed: 'red',
}

export function Home() {
  const [status, setStatus] = useState<AppStatus | null>(null)
  const [works, setWorks] = useState<WorkRecord[]>([])

  useEffect(() => {
    api.getAppStatus().then(setStatus)
    api.listWorks().then((result) => setWorks(result.works?.slice(0, 5) ?? []))
  }, [])

  if (!status) return <Spin />

  async function openDataDir() {
    const result = await api.openDataDir()
    if (!result.ok) message.error(result.error ?? '打开失败')
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="首页" extra={<Button onClick={openDataDir}>打开数据目录</Button>}>
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="应用">{status.title}</Descriptions.Item>
          <Descriptions.Item label="版本">{status.version}</Descriptions.Item>
          <Descriptions.Item label="数据目录">
            <Typography.Text copyable>{status.data_dir}</Typography.Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="最近作品" extra={<Link to="/works">查看全部</Link>}>
        <Table<WorkRecord>
          rowKey="id"
          dataSource={works}
          pagination={false}
          columns={[
            { title: '名称', dataIndex: 'name' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: WorkStatus) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at' },
          ]}
        />
      </Card>
    </Space>
  )
}
