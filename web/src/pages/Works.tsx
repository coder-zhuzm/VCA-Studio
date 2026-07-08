import { Button, Card, Descriptions, Drawer, Popconfirm, Progress, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { WorkInputFile, WorkLog, WorkRecord, WorkStage, WorkStatus, WorkStep } from '../api/types'

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
  const navigate = useNavigate()
  const [works, setWorks] = useState<WorkRecord[]>([])
  const [selectedWork, setSelectedWork] = useState<WorkRecord>()
  const [loading, setLoading] = useState(false)
  const [detailLoadingId, setDetailLoadingId] = useState<string>()
  const [startingId, setStartingId] = useState<string>()
  const [retryingId, setRetryingId] = useState<string>()
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

  async function renameWork(workId: string, name: string) {
    const result = await api.renameWork(workId, name)
    if (!result.ok || !result.work) {
      message.error(result.error ?? '重命名失败')
      return
    }
    setWorks((items) => items.map((item) => (item.id === workId ? result.work! : item)))
    if (selectedWork?.id === workId) setSelectedWork(result.work)
    message.success('已重命名')
  }

  async function exportWork(workId: string) {
    const picked = await api.chooseDirectory()
    if (!picked.ok || !picked.path) {
      if (!picked.ok) message.error(picked.error ?? '选择失败')
      return
    }
    const result = await api.exportWork(workId, picked.path)
    if (!result.ok) {
      message.error(result.error ?? '导出失败')
      return
    }
    message.success(`已导出：${result.path}`)
  }

  async function startWork(workId: string) {
    setStartingId(workId)
    try {
      const result = await api.startWork(workId)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '启动失败')
        return
      }
      setWorks((items) => items.map((item) => (item.id === workId ? result.work! : item)))
      if (selectedWork?.id === workId) {
        setSelectedWork(result.work)
        await loadLog(workId)
      }
      if (result.work.status === 'failed') {
        message.warning(result.work.logs.at(-1)?.message ?? '运行失败')
      } else {
        message.success('已开始运行')
      }
    } finally {
      setStartingId(undefined)
    }
  }

  async function retryWork(workId: string) {
    setRetryingId(workId)
    try {
      const result = await api.retryWork(workId)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '重试失败')
        return
      }
      setWorks((items) => items.map((item) => (item.id === workId ? result.work! : item)))
      if (selectedWork?.id === workId) {
        setSelectedWork(result.work)
        await loadLog(workId)
      }
      message.success('已重置为待运行')
    } finally {
      setRetryingId(undefined)
    }
  }

  async function openPath(action: () => Promise<{ ok: boolean; error?: string }>) {
    const result = await action()
    if (!result.ok) message.error(result.error ?? '打开失败')
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
                  <Typography.Text editable={{ onChange: (next) => renameWork(row.id, next) }}>{value}</Typography.Text>
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
            {
              title: '进度',
              dataIndex: 'progress',
              render: (value: number | undefined) => <Progress percent={value ?? 0} size="small" />,
            },
            { title: '创建时间', dataIndex: 'created_at' },
            {
              title: '操作',
              render: (_, row) => (
                <Space>
                  <Button
                    size="small"
                    onClick={() => startWork(row.id)}
                    loading={startingId === row.id}
                    disabled={row.status !== 'pending' || row.stage !== 'prepared'}
                  >
                    开始
                  </Button>
                  <Button
                    size="small"
                    onClick={() => retryWork(row.id)}
                    loading={retryingId === row.id}
                    disabled={row.status !== 'failed'}
                  >
                    重试
                  </Button>
                  <Button size="small" onClick={() => openDetails(row.id)} loading={detailLoadingId === row.id}>
                    查看
                  </Button>
                  <Button size="small" onClick={() => exportWork(row.id)}>
                    导出
                  </Button>
                  <Button size="small" type="link" onClick={() => navigate(`/editor/${row.id}`)}>
                    编辑
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
                {selectedWork.params ? JSON.stringify(selectedWork.params) : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="输入模式">{selectedWork.input_mode}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLOR[selectedWork.status]}>{selectedWork.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="阶段">
                <Tag color={STAGE_COLOR[selectedWork.stage]}>{selectedWork.stage}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="进度">
                <Progress percent={selectedWork.progress ?? 0} size="small" />
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">{selectedWork.created_at}</Descriptions.Item>
              <Descriptions.Item label="工作目录">
                <Space>
                  <Typography.Text copyable>{selectedWork.work_dir || '-'}</Typography.Text>
                  <Button size="small" onClick={() => openPath(() => api.openWorkDir(selectedWork.id))}>打开</Button>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="日志文件">
                <Space>
                  <Typography.Text copyable>{selectedWork.log_path || '-'}</Typography.Text>
                  <Button size="small" onClick={() => openPath(() => api.openWorkLog(selectedWork.id))}>打开</Button>
                </Space>
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

            <Card title="步骤" size="small">
              <Table<WorkStep>
                rowKey="key"
                size="small"
                dataSource={selectedWork.steps ?? []}
                pagination={false}
                columns={[
                  { title: '步骤', dataIndex: 'key' },
                  { title: '状态', dataIndex: 'status', render: (value: string) => <Tag>{value}</Tag> },
                  { title: '更新时间', dataIndex: 'updated_at' },
                  { title: '说明', dataIndex: 'message' },
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
