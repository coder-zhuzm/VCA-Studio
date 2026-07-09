import { Card, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { WorkRecord } from '../api/types'

export function EditorPicker() {
  const [works, setWorks] = useState<WorkRecord[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.listWorks()
      .then((result) => {
        if (result.ok) setWorks(result.works ?? [])
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <Card title="时间轴编辑">
      <Typography.Paragraph type="secondary">
        请从作品库选择带时间轴或多模型编排的作品进入编辑；也可在作品库点击「编辑」。
      </Typography.Paragraph>
      <Table<WorkRecord>
        rowKey="id"
        loading={loading}
        dataSource={works}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: '名称', dataIndex: 'name' },
          { title: '状态', dataIndex: 'status', width: 100 },
          {
            title: '片段',
            render: (_, row) => (row.segments?.length ? `${row.segments.length} 段` : '—'),
            width: 80,
          },
          {
            title: '操作',
            width: 120,
            render: (_, row) => <Link to={`/editor/${row.id}`}>打开编辑</Link>,
          },
        ]}
      />
      <Link to="/works">前往作品库</Link>
    </Card>
  )
}