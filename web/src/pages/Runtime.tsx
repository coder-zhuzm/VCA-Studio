import { Button, Card, Form, Input, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { RuntimeComponentStatus, RuntimeStatus, RuntimeStatusValue } from '../api/types'

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
  const [loading, setLoading] = useState(false)

  async function refresh() {
    setLoading(true)
    try {
      const next = await api.getRuntimeStatus()
      setStatus(next)
      form.setFieldsValue(next.paths)
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

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title="运行环境"
        extra={
          <Space>
            <Button onClick={refresh} loading={loading}>刷新状态</Button>
            <Button type="primary" onClick={save} loading={loading}>保存并检测</Button>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">
          先手动填写已有运行环境路径；自动安装和整合包扫描后续再加。
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          {PATH_FIELDS.map(([key, label]) => (
            <Form.Item key={key} name={key} label={label}>
              <Input placeholder="留空则使用 PATH 或显示未配置" allowClear />
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
          ]}
        />
      </Card>
    </Space>
  )
}
