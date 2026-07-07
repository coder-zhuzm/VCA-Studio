import { Button, Card, Descriptions, Form, Input, InputNumber, Select, Space, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CreateWorkPayload, ModelRecord, WorkInputMode, WorkRecord } from '../api/types'

export function Create() {
  const [form] = Form.useForm<CreateWorkPayload>()
  const [models, setModels] = useState<ModelRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [createdWork, setCreatedWork] = useState<WorkRecord>()
  const mode = Form.useWatch('mode', form) ?? 'song'

  async function createWork(values: CreateWorkPayload) {
    const payload: CreateWorkPayload = {
      name: values.name,
      model_id: values.model_id,
      params: values.params,
      mode: values.mode,
      ...(values.mode === 'song' ? { song_path: values.song_path } : {}),
      ...(values.mode === 'vocals' ? { vocals_path: values.vocals_path } : {}),
      ...(values.mode === 'stems' ? { vocals_path: values.vocals_path, instrumental_path: values.instrumental_path } : {}),
    }
    setLoading(true)
    try {
      const result = await api.createWork(payload)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '创建失败')
        return
      }
      setCreatedWork(result.work)
      message.success('作品已创建')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api.listModels().then((items) => {
      setModels(items)
      const preferred = items.find((item) => item.is_default) ?? items[0]
      if (preferred) form.setFieldValue('model_id', preferred.id)
    }).catch(() => message.error('加载模型失败'))
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="新建翻唱">
        <Form form={form} layout="vertical" onFinish={createWork} initialValues={{ mode: 'song', params: { transpose: 0, f0_method: 'rmvpe' } }}>
          <Form.Item name="name" label="作品名称" rules={[{ required: true, message: '请输入作品名称' }]}>
            <Input placeholder="例如：Demo Cover" allowClear />
          </Form.Item>
          <Form.Item name="model_id" label="目标模型" rules={[{ required: true, message: '请先选择目标模型' }]}>
            <Select
              placeholder="选择已导入模型"
              options={models.map((model) => ({
                value: model.id,
                label: `${model.name} (${model.framework}${model.is_default ? ' 默认' : ''})`,
              }))}
            />
          </Form.Item>
          <Form.Item name="mode" label="输入模式" rules={[{ required: true }]}>
            <Select<WorkInputMode>
              options={[
                { value: 'song', label: 'Song' },
                { value: 'vocals', label: 'Vocals' },
                { value: 'stems', label: 'Stems' },
              ]}
            />
          </Form.Item>
          <Form.Item name={['params', 'transpose']} label="变调">
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name={['params', 'f0_method']} label="F0 方法">
            <Select
              options={[
                { value: 'rmvpe', label: 'rmvpe' },
                { value: 'harvest', label: 'harvest' },
                { value: 'crepe', label: 'crepe' },
              ]}
            />
          </Form.Item>

          {mode === 'song' ? (
            <Form.Item name="song_path" label="歌曲文件路径" rules={[{ required: true, message: '请输入歌曲文件路径' }]}>
              <Input placeholder="/path/to/song.wav" allowClear />
            </Form.Item>
          ) : null}

          {mode === 'vocals' || mode === 'stems' ? (
            <Form.Item name="vocals_path" label="人声文件路径" rules={[{ required: true, message: '请输入人声文件路径' }]}>
              <Input placeholder="/path/to/vocals.wav" allowClear />
            </Form.Item>
          ) : null}

          {mode === 'stems' ? (
            <Form.Item name="instrumental_path" label="伴奏文件路径" rules={[{ required: true, message: '请输入伴奏文件路径' }]}>
              <Input placeholder="/path/to/instrumental.wav" allowClear />
            </Form.Item>
          ) : null}

          <Button type="primary" htmlType="submit" loading={loading}>创建</Button>
        </Form>
      </Card>

      {createdWork ? (
        <Card title="创建结果">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Work ID">
              <Typography.Text copyable>{createdWork.id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="模型">
              <Typography.Text copyable>{createdWork.model_id || '-'}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="参数">
              {createdWork.params ? `${createdWork.params.transpose}, ${createdWork.params.f0_method}` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color="blue">{createdWork.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="阶段">
              <Tag color="green">{createdWork.stage}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}
    </Space>
  )
}
