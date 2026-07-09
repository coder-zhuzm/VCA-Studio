import { Button, Card, Descriptions, Form, Input, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
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
      if (inst.ok) setInstallJob(inst.job ?? null)
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
    setInstallingId(taskId)
    try {
      const result = await api.runRuntimeInstallTask(taskId)
      if (!result.ok) {
        message.error(result.error ?? '无法启动')
        return
      }
      message.info('message' in result && result.message ? result.message : '已开始')
      if (taskId === 'ffmpeg_path_hint') {
        await refresh()
        setInstallingId(undefined)
        return
      }
      const poll = window.setInterval(async () => {
        const st = await api.getRuntimeInstallStatus()
        if (st.ok) {
          setInstallJob(st.job ?? null)
          if (st.job && st.job.status !== 'running') {
            window.clearInterval(poll)
            setInstallingId(undefined)
            const log = await api.readRuntimeInstallLog()
            if (log.ok) setInstallLog(log.content ?? '')
            await refresh()
            if (st.job.status === 'done') message.success(st.job.message)
            else message.error(st.job.message)
          }
        }
      }, 2000)
    } finally {
      if (!installJob) setInstallingId(undefined)
    }
  }

  async function applyRecommendedDevice() {
    if (!profile?.recommended_device) return
    await api.setSetting('default_inference_device', profile.recommended_device)
    message.success(`已记住推荐设备：${profile.recommended_device}（新建翻唱表单可选手动选 cuda）`)
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {profile ? (
        <Card title="本机环境" size="small" extra={<Button size="small" onClick={() => applyRecommendedDevice()}>记住推荐推理设备</Button>}>
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

      <Card
        title="可选安装（用户确认后执行）"
        extra={<Button onClick={refresh} loading={loading}>刷新</Button>}
      >
        <Typography.Paragraph type="secondary">
          先在本机跑通翻唱：Windows + NVIDIA（如 RTX 2060 SUPER）建议安装 ffmpeg → RVC 虚拟环境（CUDA）→ 手动导入模型 → 新建翻唱设备选 cuda。
          UVR / SVC 仍建议手动配置路径。
        </Typography.Paragraph>
        {installJob ? (
          <Typography.Paragraph>
            安装任务：<Tag>{installJob.id}</Tag> <Tag color={installJob.status === 'done' ? 'green' : installJob.status === 'failed' ? 'red' : 'processing'}>{installJob.status}</Tag>
            {installJob.message}
          </Typography.Paragraph>
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
                  disabled={!row.available || Boolean(installingId)}
                  loading={installingId === row.id}
                  onClick={() => runInstall(row.id)}
                >
                  安装
                </Button>
              ),
            },
          ]}
        />
        {installLog ? (
          <pre style={{ marginTop: 12, maxHeight: 200, overflow: 'auto', fontSize: 12, background: '#fafafa', padding: 8 }}>{installLog}</pre>
        ) : null}
      </Card>

      <Card
        title="运行环境路径"
        extra={
          <Space>
            <Button onClick={refresh} loading={loading}>刷新状态</Button>
            <Button type="primary" onClick={save} loading={loading}>保存并检测</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          {PATH_FIELDS.map(([key, label]) => (
            <Form.Item key={key} name={key} label={label}>
              <Input placeholder="留空则使用 PATH 或显示未配置" allowClear addonAfter={<Button type="link" size="small" onClick={() => choosePath(key)}>选择</Button>} />
            </Form.Item>
          ))}
        </Form>
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
              render: (_, row) => <Button size="small" loading={checkingKey === row.key} onClick={() => checkOne(row.key)}>重测</Button>,
            },
          ]}
        />
      </Card>
    </Space>
  )
}