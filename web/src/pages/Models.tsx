import { Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ImportModelPayload, ModelFramework, ModelRecord, ModelStatus } from '../api/types'

const STATUS_COLOR: Record<ModelStatus, string> = {
  ready: 'green',
  missing: 'default',
  error: 'red',
}

export function Models() {
  const [form] = Form.useForm<ImportModelPayload>()
  const [models, setModels] = useState<ModelRecord[]>([])
  const [loading, setLoading] = useState(false)
  const framework = Form.useWatch('framework', form) ?? 'rvc'

  async function refresh() {
    setLoading(true)
    try {
      setModels(await api.listModels())
    } finally {
      setLoading(false)
    }
  }

  async function importModel(values: ImportModelPayload) {
    setLoading(true)
    try {
      const result = await api.importModel(values)
      if (!result.ok) {
        message.error(result.error ?? '导入失败')
        return
      }
      form.resetFields()
      form.setFieldValue('framework', values.framework)
      message.success('模型已导入')
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  async function checkModel(id: string) {
    const result = await api.checkModel(id)
    if (!result.ok) {
      message.error(result.error ?? '检查失败')
      return
    }
    await refresh()
  }

  async function setDefault(id: string) {
    const result = await api.setDefaultModel(id)
    if (!result.ok) {
      message.error(result.error ?? '设置失败')
      return
    }
    setModels(result.models ?? [])
  }

  async function deleteModel(id: string) {
    const result = await api.deleteModel(id)
    if (!result.ok) {
      message.error(result.error ?? '删除失败')
      return
    }
    setModels(result.models ?? [])
  }

  useEffect(() => {
    form.setFieldValue('framework', 'rvc')
    void refresh()
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="导入模型">
        <Typography.Paragraph type="secondary">
          导入时会复制模型文件到数据目录；后续流程不依赖原始外部路径。
        </Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={importModel} initialValues={{ framework: 'rvc' }}>
          <Form.Item name="name" label="模型名称" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如：my-rvc-model" />
          </Form.Item>
          <Form.Item name="framework" label="框架" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'rvc', label: 'RVC' },
                { value: 'so-vits-svc', label: 'So-VITS-SVC' },
              ]}
            />
          </Form.Item>
          <Form.Item name="checkpoint_path" label="主模型 .pth" rules={[{ required: true, message: '请输入主模型路径' }]}>
            <Input placeholder="D:\\models\\model.pth" allowClear />
          </Form.Item>
          {framework === 'rvc' ? (
            <Form.Item name="index_path" label="RVC index（可选）">
              <Input placeholder="D:\\models\\model.index" allowClear />
            </Form.Item>
          ) : (
            <>
              <Form.Item name="config_path" label="config.json" rules={[{ required: true, message: '请输入 config.json 路径' }]}>
                <Input placeholder="D:\\models\\config.json" allowClear />
              </Form.Item>
              <Form.Item name="diffusion_path" label="浅扩散模型 .pt（可选）">
                <Input placeholder="D:\\models\\diffusion.pt" allowClear />
              </Form.Item>
              <Form.Item name="diffusion_config_path" label="浅扩散配置 .yaml/.yml（可选）">
                <Input placeholder="D:\\models\\diffusion.yaml" allowClear />
              </Form.Item>
            </>
          )}
          <Button type="primary" htmlType="submit" loading={loading}>导入模型</Button>
        </Form>
      </Card>

      <Card title="模型列表" extra={<Button onClick={refresh} loading={loading}>刷新</Button>}>
        <Table<ModelRecord>
          rowKey="id"
          loading={loading}
          dataSource={models}
          pagination={false}
          columns={[
            { title: '名称', dataIndex: 'name' },
            { title: '框架', dataIndex: 'framework' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: ModelStatus) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
            },
            {
              title: '默认',
              dataIndex: 'is_default',
              render: (value: boolean) => value ? <Tag color="blue">默认</Tag> : null,
            },
            {
              title: '文件',
              render: (_, row) => (
                <Space direction="vertical" size={2}>
                  {Object.entries(row.files).map(([role, path]) => (
                    <Typography.Text key={role} type="secondary">{role}: {path}</Typography.Text>
                  ))}
                </Space>
              ),
            },
            {
              title: '操作',
              render: (_, row) => (
                <Space>
                  <Button size="small" onClick={() => checkModel(row.id)}>检查</Button>
                  <Button size="small" disabled={row.is_default} onClick={() => setDefault(row.id)}>设为默认</Button>
                  <Popconfirm title="删除这个模型？" onConfirm={() => deleteModel(row.id)}>
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  )
}
