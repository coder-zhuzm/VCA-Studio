import { Button, Card, Collapse, Descriptions, Form, Input, Progress, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type {
  HostProfile,
  RuntimeComponentStatus,
  RuntimeInstallJob,
  RuntimeInstallTask,
  RuntimeStatus,
  RuntimeStatusValue,
} from '../api/types'

const PATH_FIELDS = [
  ['ffmpeg_path', 'ffmpeg 路径'],
  ['ffprobe_path', 'ffprobe 路径'],
  ['svc_python', 'SVC Python'],
  ['sovits_repo', 'So-VITS-SVC 仓库'],
  ['rvc_python', 'RVC Python'],
  ['uvr_python', 'UVR Python'],
  ['uvr_model_dir', 'UVR 模型目录'],
] as const

const STATUS_COLOR: Record<RuntimeStatusValue, string> = {
  ready: 'green',
  partial: 'orange',
  missing: 'default',
  error: 'red',
}

export function Runtime() {
  const [form] = Form.useForm<Record<string, string>>()
  const [status, setStatus] = useState<RuntimeStatus | null>(null)
  const [profile, setProfile] = useState<HostProfile | null>(null)
  const [tasks, setTasks] = useState<RuntimeInstallTask[]>([])
  const [installJob, setInstallJob] = useState<RuntimeInstallJob | null>(null)
  const [installLog, setInstallLog] = useState('')
  const [loading, setLoading] = useState(false)
  const [checkingKey, setCheckingKey] = useState<string>()
  const [installingId, setInstallingId] = useState<string>()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function stopPoll() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function pollInstallOnce() {
    const [st, log] = await Promise.all([api.getRuntimeInstallStatus(), api.readRuntimeInstallLog()])
    if (st.ok) setInstallJob(st.job ?? null)
    if (log.ok) setInstallLog(log.content ?? '')
    return st.ok ? st.job : null
  }

  function startInstallPoll(taskId: string) {
    stopPoll()
    setInstallJob({ id: taskId, status: 'running', message: '正在启动…', progress: 0 })
    setInstallingId(taskId)
    void pollInstallOnce()
    pollRef.current = window.setInterval(async () => {
      const job = await pollInstallOnce()
      if (job && job.status !== 'running') {
        stopPoll()
        setInstallingId(undefined)
        await refresh()
        if (job.status === 'done') message.success(job.message)
        else message.error(job.message)
      }
    }, 800)
  }

  const installBusy = Boolean(installingId) || installJob?.status === 'running'

  const ffmpegStatus = status?.components.find((c) => c.key === 'ffmpeg')
  const rvcStatus = status?.components.find((c) => c.key === 'rvc')
  const taskById = Object.fromEntries(tasks.map((t) => [t.id, t]))

  const readiness = [
    {
      key: 'ffmpeg',
      title: 'ffmpeg（必需）',
      status: ffmpegStatus?.status ?? 'missing',
      message: ffmpegStatus?.message ?? '未检测',
      primaryTaskId: taskById.ffmpeg_winget?.available
        ? 'ffmpeg_winget'
        : 'ffmpeg_path_hint',
      primaryLabel: taskById.ffmpeg_winget?.available ? '安装 ffmpeg' : '检测并绑定',
    },
    {
      key: 'rvc',
      title: 'RVC（必需）',
      status: rvcStatus?.status ?? 'missing',
      message: rvcStatus?.message ?? '未检测',
      primaryTaskId: taskById.rvc_venv_cuda?.available
        ? 'rvc_venv_cuda'
        : taskById.rvc_venv_mps?.available
          ? 'rvc_venv_mps'
          : taskById.rvc_venv_cpu?.available
            ? 'rvc_venv_cpu'
            : '',
      primaryLabel: taskById.rvc_venv_cuda?.available
        ? '安装 RVC（CUDA）'
        : taskById.rvc_venv_mps?.available
          ? '安装 RVC（MPS）'
          : taskById.rvc_venv_cpu?.available
            ? '安装 RVC（CPU）'
            : '已就绪或请手填路径',
    },
  ]

  async function refresh() {
    setLoading(true)
    try {
      const [next, taskPack, prof] = await Promise.all([
        api.getRuntimeStatus(),
        api.listRuntimeInstallTasks(),
        api.getHostProfile(),
      ])
      setStatus(next)
      form.setFieldsValue(next.paths)
      setProfile(prof)
      if (taskPack.ok) setTasks(taskPack.tasks ?? [])
      const inst = await api.getRuntimeInstallStatus()
      if (inst.ok) {
        setInstallJob(inst.job ?? null)
        if (inst.job?.status === 'running' && !pollRef.current) {
          setInstallingId(inst.job.id)
          stopPoll()
          pollRef.current = window.setInterval(async () => {
            const job = await pollInstallOnce()
            if (job && job.status !== 'running') {
              stopPoll()
              setInstallingId(undefined)
              await refresh()
              if (job.status === 'done') message.success(job.message)
              else message.error(job.message)
            }
          }, 800)
        }
      }
      const log = await api.readRuntimeInstallLog()
      if (log.ok) setInstallLog(log.content ?? '')
    } finally {
      setLoading(false)
    }
  }

  async function save() {
    setLoading(true)
    try {
      const values = form.getFieldsValue()
      const result = await api.setRuntimePaths(Object.fromEntries(
        PATH_FIELDS.map(([key]) => [key, values[key] ?? '']),
      ))
      if (!result.ok) {
        message.error(result.error ?? '保存失败')
        return
      }
      setStatus(result)
      form.setFieldsValue(result.paths)
      message.success('已保存并检测')
    } finally {
      setLoading(false)
    }
  }

  async function choosePath(key: string) {
    const result = key.endsWith('_dir') || key.endsWith('_repo') ? await api.chooseDirectory() : await api.chooseFile()
    if (!result.ok) {
      message.error(result.error ?? '选择失败')
      return
    }
    if (result.path) form.setFieldValue(key, result.path)
  }

  async function checkOne(key: string) {
    setCheckingKey(key)
    try {
      const result = await api.checkRuntimeComponent(key)
      if (!result.ok) {
        message.error(result.error ?? '检测失败')
        return
      }
      setStatus(result)
      form.setFieldsValue(result.paths)
    } finally {
      setCheckingKey(undefined)
    }
  }

  async function runInstall(taskId: string) {
    if (taskId === 'ffmpeg_path_hint') {
      setInstallingId(taskId)
      try {
        const result = await api.runRuntimeInstallTask(taskId)
        if (!result.ok) {
          message.error(result.error ?? '未找到 ffmpeg，请先 Homebrew 安装或手动填写路径')
          return
        }
        if (result.components && result.paths) {
          setStatus({ components: result.components, paths: result.paths })
          form.setFieldsValue(result.paths)
        } else {
          await refresh()
        }
        message.success(result.message ?? 'ffmpeg 已绑定')
      } finally {
        setInstallingId(undefined)
      }
      return
    }

    try {
      const result = await api.runRuntimeInstallTask(taskId)
      if (!result.ok) {
        message.error(result.error ?? '无法启动')
        return
      }
      message.info('message' in result && result.message ? result.message : '已开始')
      startInstallPoll(taskId)
    } catch {
      stopPoll()
      setInstallingId(undefined)
    }
  }

  async function applyRecommendedDevice() {
    if (!profile?.recommended_device) return
    await api.setSetting('default_inference_device', profile.recommended_device)
    message.success(`已记住推荐设备：${profile.recommended_device}（新建翻唱表单可选手动选 cuda）`)
  }

  useEffect(() => {
    void refresh()
    return () => stopPoll()
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {profile ? (
        <Card title="本机环境" size="small" extra={<Button size="small" disabled={installBusy} onClick={() => applyRecommendedDevice()}>记住推荐推理设备</Button>}>
          <Descriptions column={2} size="small">
            <Descriptions.Item label="系统">{profile.platform} / {profile.machine}</Descriptions.Item>
            <Descriptions.Item label="GPU">{profile.gpu_name || '（无 NVIDIA 或未检测到）'}</Descriptions.Item>
            <Descriptions.Item label="驱动">{profile.driver_version || '—'}</Descriptions.Item>
            <Descriptions.Item label="推荐设备">
              <Tag color="blue">{profile.recommended_device}</Tag>
              {profile.cuda_detected ? <Tag color="green">CUDA</Tag> : null}
            </Descriptions.Item>
          </Descriptions>
          {profile.notes?.length ? (
            <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              {profile.notes.map((n) => (
                <li key={n}><Typography.Text type="secondary">{n}</Typography.Text></li>
              ))}
            </ul>
          ) : null}
        </Card>
      ) : null}

      <Card title="就绪清单（先完成这两项）" size="small">
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          混音依赖 ffmpeg；翻唱推理依赖 RVC。UVR / So-VITS-SVC 可在下方手填路径（本页不提供一键安装）。
        </Typography.Paragraph>
        {readiness.map((row) => (
          <div key={row.key} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
            <div>
              <Space>
                <Typography.Text strong>{row.title}</Typography.Text>
                <Tag color={STATUS_COLOR[row.status as RuntimeStatusValue] ?? 'default'}>{row.status}</Tag>
              </Space>
              <div><Typography.Text type="secondary">{row.message}</Typography.Text></div>
            </div>
            <Button
              type="primary"
              size="small"
              disabled={installBusy || !row.primaryTaskId || row.status === 'ready'}
              loading={installingId === row.primaryTaskId}
              onClick={() => row.primaryTaskId && runInstall(row.primaryTaskId)}
            >
              {row.status === 'ready' ? '已完成' : row.primaryLabel}
            </Button>
          </div>
        ))}
      </Card>

      <Card
        title="其它安装任务"
        extra={<Button onClick={refresh} loading={loading} disabled={installBusy}>刷新</Button>}
      >
        {installBusy ? (
          <Typography.Text type="warning" style={{ display: 'block', marginBottom: 8 }}>
            安装进行中：已禁用其它安装与路径保存，请等待完成。
          </Typography.Text>
        ) : null}
        {status?.components.find((c) => c.key === 'ffmpeg')?.status === 'ready' ? (
          <Typography.Text type="success" style={{ display: 'block', marginBottom: 8 }}>
            ffmpeg 已就绪，无需重复安装 Homebrew/winget 项。
          </Typography.Text>
        ) : null}
        <Typography.Paragraph type="secondary">
          先在本机跑通翻唱：Windows + NVIDIA 建议 ffmpeg → RVC（CUDA）；macOS（Apple Silicon）建议 ffmpeg（brew）→ RVC（MPS），新建翻唱设备选 mps。
          Intel Mac 用 CPU。UVR / SVC 仍手动配置路径。
        </Typography.Paragraph>
        {installJob ? (
          <Card size="small" type="inner" title="安装进度" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Space wrap>
                <Tag>{installJob.id}</Tag>
                <Tag color={installJob.status === 'done' ? 'green' : installJob.status === 'failed' ? 'red' : 'processing'}>
                  {installJob.status}
                </Tag>
              </Space>
              <Progress
                percent={installJob.status === 'running' ? (installJob.progress ?? 5) : 100}
                status={installJob.status === 'failed' ? 'exception' : installJob.status === 'done' ? 'success' : 'active'}
                strokeColor={installJob.status === 'running' ? { from: '#1677ff', to: '#69b1ff' } : undefined}
              />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {installJob.message || '等待后端输出…'}
              </Typography.Text>
            </Space>
          </Card>
        ) : null}
        <Table<RuntimeInstallTask>
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={tasks}
          columns={[
            { title: '任务', dataIndex: 'label' },
            { title: '说明', dataIndex: 'description', ellipsis: true },
            { title: '注意', dataIndex: 'risk', ellipsis: true },
            {
              title: '操作',
              width: 120,
              render: (_, row) => (
                <Button
                  size="small"
                  type="primary"
                  disabled={!row.available || installBusy}
                  loading={installingId === row.id}
                  onClick={() => runInstall(row.id)}
                >
                  {row.id === 'ffmpeg_path_hint' ? '检测' : row.available ? '安装' : '已完成'}
                </Button>
              ),
            },
          ]}
        />
        <pre
          style={{
            marginTop: 12,
            maxHeight: installJob?.status === 'running' ? 280 : 200,
            overflow: 'auto',
            fontSize: 11,
            background: '#fafafa',
            padding: 8,
            border: installJob?.status === 'running' ? '1px solid #d9d9d9' : undefined,
          }}
        >
          {(installLog || (installJob?.status === 'running' ? '（日志刷新中…）' : ''))
            .split('\n')
            .slice(-40)
            .join('\n')}
        </pre>
      </Card>

      <Card title="组件状态">
        <Table<RuntimeComponentStatus>
          rowKey="key"
          loading={loading}
          dataSource={status?.components ?? []}
          pagination={false}
          columns={[
            { title: '组件', dataIndex: 'name' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: RuntimeStatusValue) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
            },
            { title: '说明', dataIndex: 'message' },
            {
              title: '检查项',
              render: (_, row) => (
                <Space direction="vertical" size={2}>
                  {row.checks.map((check) => (
                    <Typography.Text key={check.key} type={check.ok ? 'success' : 'secondary'}>
                      {check.ok ? '✓' : '×'} {check.label}: {check.message}
                    </Typography.Text>
                  ))}
                </Space>
              ),
            },
            {
              title: '操作',
              render: (_, row) => (
                <Button size="small" disabled={installBusy} loading={checkingKey === row.key} onClick={() => checkOne(row.key)}>
                  重测
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Card title="高级：手动路径" size="small">
        <Collapse
          items={[{
            key: 'paths',
            label: '已有自建环境时展开填写',
            children: (
              <>
                <Form form={form} layout="vertical">
                  {PATH_FIELDS.map(([key, label]) => (
                    <Form.Item key={key} name={key} label={label}>
                      <Input
                        allowClear
                        disabled={installBusy}
                        addonAfter={
                          <Button type="link" size="small" disabled={installBusy} onClick={() => choosePath(key)}>
                            选择
                          </Button>
                        }
                      />
                    </Form.Item>
                  ))}
                </Form>
                <Button type="primary" onClick={save} loading={loading} disabled={installBusy}>
                  保存并检测
                </Button>
              </>
            ),
          }]}
        />
      </Card>
    </Space>
  )
}