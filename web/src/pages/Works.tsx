import { Button, Card, Descriptions, Drawer, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { WorkInputFile, WorkLog, WorkRecord, WorkStage, WorkStatus } from '../api/types'

const STATUS_COLOR: Record<WorkStatus, string> = {
  pending: 'blue',
  running: 'processing',
  done: 'green',
  failed: 'red',
}

const STAGE_COLOR: Record<WorkStage, string> = {
  prepared: 'green',
  queued: 'blue',
  inferencing: 'processing',
  mixing: 'purple',
  exported: 'cyan',
  failed: 'red',
}

export function Works() {
  const [works, setWorks] = useState<WorkRecord[]>([])
  const [selectedWork, setSelectedWork] = useState<WorkRecord>()
  const [loading, setLoading] = useState(false)
  const [detailLoadingId, setDetailLoadingId] = useState<string>()
  const [deletingId, setDeletingId] = useState<string>()
  const [logContent, setLogContent] = useState('')
  const [logLoading, setLogLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const result = await api.listWorks()
      if (!result.ok) {
        message.error(result.error ?? '加载失败')
        return
      }
      setWorks(result.works ?? [])
    } finally {
      setLoading(false)
    }
  }

  async function openDetails(workId: string) {
    setDetailLoadingId(workId)
    try {
      const result = await api.getWork(workId)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '加载详情失败')
        return
      }
      setSelectedWork(result.work)
      await loadLog(workId)
    } finally {
      setDetailLoadingId(undefined)
    }
  }

  async function loadLog(workId: string) {
    setLogLoading(true)
    try {
      const result = await api.readWorkLog(workId)
      setLogContent(result.ok ? result.content ?? '' : '')
      if (!result.ok) message.error(result.error ?? '读取日志失败')
    } finally {
      setLogLoading(false)
    }
  }

  async function deleteWork(workId: string) {
    setDeletingId(workId)
    try {
      const result = await api.deleteWork(workId)
      if (!result.ok) {
        message.error(result.error ?? '删除失败')
        return
      }
      setWorks(result.works ?? [])
      if (selectedWork?.id === workId) {
        setSelectedWork(undefined)
        setLogContent('')
      }
      message.success('作品已删除')
    } finally {
      setDeletingId(undefined)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <>
      <Card title="作品库" extra={<Button onClick={refresh} loading={loading}>刷新</Button>}>
        <Table<WorkRecord>
          rowKey="id"
          loading={loading}
          dataSource={works}
          pagination={false}
          columns={[
            {
              title: '名称',
              dataIndex: 'name',
              render: (value: string, row) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text>{value}</Typography.Text>
                  <Typography.Text type="secondary">{row.id}</Typography.Text>
                </Space>
              ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: WorkStatus) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
            },
            {
              title: '阶段',
              dataIndex: 'stage',
              render: (value: WorkStage) => <Tag color={STAGE_COLOR[value]}>{value}</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at' },
            {
              title: '操作',
              render: (_, row) => (
                <Space>
                  <Button size="small" onClick={() => openDetails(row.id)} loading={detailLoadingId === row.id}>
                    查看
                  </Button>
                  <Popconfirm title="删除这个作品？" onConfirm={() => deleteWork(row.id)}>
                    <Button size="small" danger loading={deletingId === row.id}>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title="作品详情"
        width={640}
        open={Boolean(selectedWork)}
        onClose={() => {
          setSelectedWork(undefined)
          setLogContent('')
        }}
      >
        {selectedWork ? (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Work ID">
                <Typography.Text copyable>{selectedWork.id}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="名称">{selectedWork.name}</Descriptions.Item>
              <Descriptions.Item label="模型">
                <Typography.Text copyable>{selectedWork.model_id || '-'}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="参数">
                {selectedWork.params ? `${selectedWork.params.transpose}, ${selectedWork.params.f0_method}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="输入模式">{selectedWork.input_mode}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLOR[selectedWork.status]}>{selectedWork.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="阶段">
                <Tag color={STAGE_COLOR[selectedWork.stage]}>{selectedWork.stage}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">{selectedWork.created_at}</Descriptions.Item>
              <Descriptions.Item label="工作目录">
                <Typography.Text copyable>{selectedWork.work_dir || '-'}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="日志文件">
                <Typography.Text copyable>{selectedWork.log_path || '-'}</Typography.Text>
              </Descriptions.Item>
            </Descriptions>

            <Card title="输入文件" size="small">
              <Table<WorkInputFile>
                rowKey="role"
                size="small"
                dataSource={selectedWork.input_files}
                pagination={false}
                columns={[
                  { title: '角色', dataIndex: 'role' },
                  { title: '文件名', dataIndex: 'filename' },
                  {
                    title: '保存路径',
                    dataIndex: 'stored_path',
                    render: (value: string) => <Typography.Text copyable>{value}</Typography.Text>,
                  },
                ]}
              />
            </Card>

            <Card
              title="日志"
              size="small"
              extra={<Button size="small" loading={logLoading} onClick={() => loadLog(selectedWork.id)}>刷新日志</Button>}
            >
              <Table<WorkLog>
                rowKey={(row) => `${row.created_at}-${row.message}`}
                size="small"
                dataSource={selectedWork.logs}
                pagination={false}
                columns={[
                  { title: '时间', dataIndex: 'created_at' },
                  {
                    title: '级别',
                    dataIndex: 'level',
                    render: (value: string) => <Tag>{value}</Tag>,
                  },
                  { title: '消息', dataIndex: 'message' },
                ]}
              />
              <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{logContent || '暂无日志内容'}</pre>
              </Typography.Paragraph>
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </>
  )
}
