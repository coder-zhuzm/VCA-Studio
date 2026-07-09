import {
  Button,
  Card,
  Checkbox,
  Collapse,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { CreateWorkPayload, ModelRecord, WorkInputMode, WorkModelEntry, WorkParams, WorkRecord } from '../api/types'
import { lrcToSegments } from '../utils/lrc'

const MODE_LABEL: Record<WorkInputMode, string> = {
  song: '完整歌曲，自动分离',
  vocals: '已分离人声',
  stems: '已分离人声 + 伴奏',
}

const SVC_DEFAULT: Partial<WorkParams> = {
  f0_predictor: 'rmvpe',
  method: 'reconstruct',
  speaker: 0,
  cluster_ratio: 0,
  shallow_diffusion: false,
}

const DEFAULT_PARAMS: WorkParams = {
  transpose: 0,
  f0_method: 'rmvpe',
  index_rate: 0.75,
  rms_mix_rate: 1,
  protect: 0.33,
  filter_radius: 3,
  device: 'auto',
  vocal_volume: 1,
  instrumental_volume: 0.85,
  skip_dereverb: false,
  ...SVC_DEFAULT,
} as WorkParams

type CreateFormValues = {
  name: string
  mode: WorkInputMode
  song_path?: string
  vocals_path?: string
  instrumental_path?: string
  normalize_input?: boolean
  model_id?: string
  params?: WorkParams
  multi_model?: boolean
  model_ids?: string[]
  lrc_text?: string
  auto_start?: boolean
}

function fileTitle(path = '') {
  return (path.split(/[\\/]/).pop() || '').replace(/\.[^.]+$/, '')
}

function cloneParams(p?: WorkParams): WorkParams {
  return { ...DEFAULT_PARAMS, ...(p || {}) }
}

export function Create() {
  const navigate = useNavigate()
  const [form] = Form.useForm<CreateFormValues>()
  const [models, setModels] = useState<ModelRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [createdWork, setCreatedWork] = useState<WorkRecord>()
  const [perModelParams, setPerModelParams] = useState<Record<string, WorkParams>>({})
  const mode = Form.useWatch('mode', form) ?? 'song'
  const songPath = Form.useWatch('song_path', form)
  const vocalsPath = Form.useWatch('vocals_path', form)
  const modelId = Form.useWatch('model_id', form)
  const multiModel = Form.useWatch('multi_model', form)
  const modelIds = Form.useWatch('model_ids', form) ?? []
  const lrcText = Form.useWatch('lrc_text', form) ?? ''
  const autoStart = Form.useWatch('auto_start', form) ?? true
  const [nameTouched, setNameTouched] = useState(false)
  const submitText = mode === 'vocals' ? '开始生成干声' : '开始生成翻唱'

  const previewSegments = useMemo(() => {
    const primary = multiModel ? modelIds[0] : modelId
    if (!lrcText.trim() || !primary) return []
    return lrcToSegments(lrcText, primary)
  }, [lrcText, modelId, modelIds, multiModel])

  const [runtimeHint, setRuntimeHint] = useState<string>()

  useEffect(() => {
    api.getRuntimeStatus().then((status) => {
      const rvc = status.components.find((c) => c.key === 'rvc')
      const svc = status.components.find((c) => c.key === 'svc')
      const ff = status.components.find((c) => c.key === 'ffmpeg')
      const hints: string[] = []
      if (rvc && rvc.status !== 'ready') hints.push(`RVC：${rvc.message}`)
      if (svc && svc.status !== 'ready') hints.push(`So-VITS-SVC：${svc.message}`)
      if (ff && ff.status !== 'ready') hints.push(`ffmpeg：${ff.message}`)
      setRuntimeHint(hints.length ? hints.join('；') : undefined)
    }).catch(() => undefined)
  }, [])

  async function submitPipeline(values: CreateFormValues, autoStart: boolean) {
    const baseParams = cloneParams(values.params)
    let payload: CreateWorkPayload = {
      name: values.name,
      params: baseParams,
      normalize_input: values.normalize_input,
      mode: values.mode,
      ...(values.mode === 'song' ? { song_path: values.song_path } : {}),
      ...(values.mode === 'vocals' ? { vocals_path: values.vocals_path } : {}),
      ...(values.mode === 'stems' ? { vocals_path: values.vocals_path, instrumental_path: values.instrumental_path } : {}),
    }

    if (values.multi_model && values.model_ids?.length) {
      const entries: WorkModelEntry[] = values.model_ids.map((id) => ({
        model_id: id,
        params: cloneParams(perModelParams[id] ?? baseParams),
      }))
      payload = { ...payload, models: entries, model_id: values.model_ids[0] }
      if (values.lrc_text?.trim()) {
        payload.lrc_text = values.lrc_text.trim()
      }
    } else {
      if (!values.model_id) {
        message.error('请选择目标模型')
        return
      }
      payload = { ...payload, model_id: values.model_id }
      if (values.lrc_text?.trim()) {
        payload.lrc_text = values.lrc_text.trim()
      }
    }

    setLoading(true)
    try {
      const result = await api.createWork(payload)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '创建失败')
        return
      }
      setCreatedWork(result.work)
      if (autoStart) {
        const started = await api.startWork(result.work.id)
        if (!started.ok || !started.work) {
          message.error(started.error ?? '启动失败')
          return
        }
        if (started.work.status === 'failed') {
          message.warning(started.work.logs.at(-1)?.message ?? '运行失败，请到作品库查看日志')
          navigate('/works')
          return
        }
        message.success('已开始翻唱，请到作品库查看进度')
        navigate('/works')
        return
      }
      message.success('作品已创建，请到作品库点击「开始」运行')
    } finally {
      setLoading(false)
    }
  }

  const selectedModel = models.find((m) => m.id === (multiModel ? modelIds[0] : modelId))
  const isSvc = selectedModel?.framework === 'so-vits-svc'
  const needsSvcRuntime = multiModel
    ? modelIds.some((id) => models.find((m) => m.id === id)?.framework === 'so-vits-svc')
    : isSvc
  const needsRvcRuntime = multiModel
    ? modelIds.some((id) => models.find((m) => m.id === id)?.framework === 'rvc')
    : !isSvc

  async function chooseFile(field: 'song_path' | 'vocals_path' | 'instrumental_path') {
    const result = await api.chooseFile()
    if (!result.ok) {
      message.error(result.error ?? '选择失败')
      return
    }
    if (result.path) {
      form.setFieldValue(field, result.path)
      fillName(field, result.path)
    }
  }

  async function chooseLrcFile() {
    const picked = await api.chooseFile()
    if (!picked.ok || !picked.path) {
      if (!picked.ok) message.error(picked.error ?? '选择失败')
      return
    }
    const read = await api.readTextFile(picked.path)
    if (!read.ok || read.content == null) {
      message.error(read.error ?? '读取失败，请粘贴 LRC 到文本框')
      return
    }
    form.setFieldValue('lrc_text', read.content)
    message.success('已导入 LRC')
  }

  function fillName(field: keyof CreateFormValues, path: string) {
    if (nameTouched) return
    const base = fileTitle(path)
    if (!base || field === 'instrumental_path') return
    const model = models.find((item) => item.id === form.getFieldValue('model_id'))
    form.setFieldValue('name', model ? `${base} - ${model.name}` : base)
  }

  function syncPerModelParams(ids: string[]) {
    setPerModelParams((prev) => {
      const base = cloneParams(form.getFieldValue('params'))
      const next = { ...prev }
      for (const id of ids) {
        if (!next[id]) next[id] = cloneParams(base)
      }
      return next
    })
  }

  useEffect(() => {
    api.getHostProfile().then((p) => {
      if (!p?.recommended_device) return
      const cur = form.getFieldValue(['params', 'device'])
      if (!cur || cur === 'auto') {
        form.setFieldValue(['params', 'device'], p.recommended_device)
      }
    }).catch(() => undefined)
  }, [])


  useEffect(() => {
    api.listModels().then((items) => {
      setModels(items)
      const preferred = items.find((item) => item.is_default) ?? items[0]
      if (preferred) {
        form.setFieldValue('model_id', preferred.id)
        form.setFieldValue('model_ids', [preferred.id])
      }
    }).catch(() => message.error('加载模型失败'))
  }, [])

  useEffect(() => {
    if (nameTouched || !modelId) return
    const path = mode === 'song' ? songPath : vocalsPath
    if (path) fillName(mode === 'song' ? 'song_path' : 'vocals_path', path)
  }, [mode, modelId, songPath, vocalsPath])

  useEffect(() => {
    if (multiModel && modelIds.length) syncPerModelParams(modelIds)
  }, [modelIds.join(','), multiModel])

  const modelOptions = models.map((model) => ({
    value: model.id,
    label: `${model.name} (${model.framework}${model.is_default ? ' 默认' : ''})`,
  }))

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {runtimeHint ? (
        <Typography.Text type="warning">
          运行环境未就绪，翻唱可能无法完成：{runtimeHint}（<Link to="/runtime">去配置</Link>）
          {needsSvcRuntime ? ' · 使用 SVC 模型需配置 svc_python + sovits_repo' : null}
          {needsRvcRuntime ? ' · 使用 RVC 模型需配置 rvc_python' : null}
        </Typography.Text>
      ) : null}
      <Card title="新建翻唱">
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => submitPipeline(values, Boolean(values.auto_start))}
          initialValues={{
            mode: 'song',
            multi_model: false,
            auto_start: true,
            params: { ...DEFAULT_PARAMS },
          }}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Card size="small" title="输入文件">
              <Form.Item name="mode" label="输入类型" rules={[{ required: true }]}>
                <Select<WorkInputMode>
                  options={(Object.entries(MODE_LABEL) as [WorkInputMode, string][]).map(([value, label]) => ({ value, label }))}
                />
              </Form.Item>

              {mode === 'song' ? (
                <Form.Item name="song_path" label="歌曲文件路径" rules={[{ required: true, message: '请输入歌曲文件路径' }]}>
                  <Input placeholder="/path/to/song.wav" allowClear addonAfter={<Button type="primary" size="small" onClick={() => chooseFile('song_path')}>选择</Button>} />
                </Form.Item>
              ) : null}

              {mode === 'vocals' || mode === 'stems' ? (
                <Form.Item name="vocals_path" label="人声文件路径" rules={[{ required: true, message: '请输入人声文件路径' }]}>
                  <Input placeholder="/path/to/vocals.wav" allowClear addonAfter={<Button type="primary" size="small" onClick={() => chooseFile('vocals_path')}>选择</Button>} />
                </Form.Item>
              ) : null}

              {mode === 'stems' ? (
                <Form.Item name="instrumental_path" label="伴奏文件路径" rules={[{ required: true, message: '请输入伴奏文件路径' }]}>
                  <Input placeholder="/path/to/instrumental.wav" allowClear addonAfter={<Button type="primary" size="small" onClick={() => chooseFile('instrumental_path')}>选择</Button>} />
                </Form.Item>
              ) : null}
              <Form.Item name="normalize_input" valuePropName="checked">
                <Checkbox>导入时转换为 44100Hz WAV</Checkbox>
              </Form.Item>
              {mode === 'song' ? (
                <Form.Item name={['params', 'skip_dereverb']} valuePropName="checked">
                  <Checkbox>跳过去混响（已处理过的人声可勾选）</Checkbox>
                </Form.Item>
              ) : null}
              {mode === 'stems' || mode === 'song' ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <Form.Item name={['params', 'vocal_volume']} label="人声音量">
                    <InputNumber min={0} max={2} step={0.05} style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item name={['params', 'instrumental_volume']} label="伴奏音量">
                    <InputNumber min={0} max={2} step={0.05} style={{ width: '100%' }} />
                  </Form.Item>
                </div>
              ) : null}
            </Card>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(320px, 420px)', gap: 24, alignItems: 'start' }}>
              <Card size="small" title="基础信息">
                <Form.Item name="name" label="作品名称" rules={[{ required: true, message: '请输入作品名称' }]}>
                  <Input placeholder="选择文件后自动生成，可编辑" allowClear onChange={() => setNameTouched(true)} />
                </Form.Item>

                <Form.Item name="multi_model" label="多模型混唱" valuePropName="checked">
                  <Switch checkedChildren="多模型" unCheckedChildren="单模型" />
                </Form.Item>

                {!multiModel ? (
                  <Form.Item name="model_id" label="目标模型" rules={[{ required: true, message: '请先选择目标模型' }]}>
                    <Select placeholder="选择已导入模型" options={modelOptions} />
                  </Form.Item>
                ) : (
                  <Form.Item name="model_ids" label="参与模型" rules={[{ required: true, message: '请至少选择一个模型' }]}>
                    <Select
                      mode="multiple"
                      placeholder="选择多个模型"
                      options={modelOptions}
                      onChange={(ids) => syncPerModelParams(ids as string[])}
                    />
                  </Form.Item>
                )}

                <Form.Item name="lrc_text" label="LRC 歌词（可选，用于片段时间轴）">
                  <Input.TextArea rows={6} placeholder="粘贴 .lrc 内容，或导入后在此编辑" />
                </Form.Item>
                <Button size="small" onClick={() => chooseLrcFile()} style={{ marginBottom: 12 }}>
                  从文件导入 LRC（桌面环境）
                </Button>
                {previewSegments.length ? (
                  <Typography.Text type="secondary">将生成 {previewSegments.length} 个片段（首句默认指派首个模型，可在编辑页调整）</Typography.Text>
                ) : null}
              </Card>

              <Card size="small" title={multiModel ? '默认参数（新选模型继承）' : isSvc ? 'So-VITS-SVC 参数' : 'RVC 参数'}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
                  <Form.Item name={['params', 'transpose']} label="变调" rules={[{ required: true, message: '请输入变调值' }]}>
                    <InputNumber style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item name={['params', 'device']} label="设备" rules={[{ required: true, message: '请选择设备' }]}>
                    <Select
                      options={[
                        { value: 'auto', label: 'auto' },
                        { value: 'cpu', label: 'cpu' },
                        { value: 'cuda', label: 'cuda' },
                        { value: 'mps', label: 'mps' },
                      ]}
                    />
                  </Form.Item>
                  {isSvc ? (
                    <>
                      <Form.Item name={['params', 'f0_predictor']} label="F0 预测" rules={[{ required: true }]}>
                        <Select options={[
                          { value: 'rmvpe', label: 'rmvpe' },
                          { value: 'pm', label: 'pm' },
                          { value: 'dio', label: 'dio' },
                          { value: 'harvest', label: 'harvest' },
                          { value: 'crepe', label: 'crepe' },
                        ]}
                        />
                      </Form.Item>
                      <Form.Item name={['params', 'method']} label="推理方法">
                        <Select options={[{ value: 'reconstruct', label: 'reconstruct' }, { value: 'cluster', label: 'cluster' }]} />
                      </Form.Item>
                      <Form.Item name={['params', 'speaker']} label="Speaker ID">
                        <InputNumber min={0} step={1} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name={['params', 'cluster_ratio']} label="Cluster 比例">
                        <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name={['params', 'shallow_diffusion']} valuePropName="checked" style={{ gridColumn: '1 / -1' }}>
                        <Checkbox>浅扩散（需模型含 diffusion 权重）</Checkbox>
                      </Form.Item>
                    </>
                  ) : (
                    <>
                      <Form.Item name={['params', 'f0_method']} label="F0 方法" rules={[{ required: true, message: '请选择 F0 方法' }]}>
                        <Select options={[{ value: 'rmvpe', label: 'rmvpe' }, { value: 'harvest', label: 'harvest' }, { value: 'crepe', label: 'crepe' }]} />
                      </Form.Item>
                      <Form.Item name={['params', 'index_rate']} label="Index" rules={[{ required: true, message: '请输入 Index Rate' }]}>
                        <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                      </Form.Item>
                    </>
                  )}
                </div>

                {!isSvc ? (
                <Collapse
                  ghost
                  size="small"
                  items={[
                    {
                      key: 'advanced',
                      label: 'RVC 高级参数',
                      children: (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 12px' }}>
                          <Form.Item name={['params', 'rms_mix_rate']} label="RMS" rules={[{ required: true }]}>
                            <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                          </Form.Item>
                          <Form.Item name={['params', 'protect']} label="Protect" rules={[{ required: true }]}>
                            <InputNumber min={0} max={0.5} step={0.01} style={{ width: '100%' }} />
                          </Form.Item>
                          <Form.Item name={['params', 'filter_radius']} label="Filter" rules={[{ required: true }]}>
                            <InputNumber min={0} step={1} style={{ width: '100%' }} />
                          </Form.Item>
                        </div>
                      ),
                    },
                  ]}
                />
                ) : null}

                {multiModel && modelIds.length ? (
                  <Collapse
                    style={{ marginTop: 8 }}
                    size="small"
                    items={modelIds.map((id) => {
                      const model = models.find((m) => m.id === id)
                      const svcModel = model?.framework === 'so-vits-svc'
                      return {
                        key: id,
                        label: `${model?.name ?? id} (${model?.framework ?? '?'})`,
                        children: svcModel ? (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <span>变调</span>
                            <InputNumber
                              value={perModelParams[id]?.transpose ?? 0}
                              onChange={(v) => setPerModelParams((p) => ({ ...p, [id]: { ...cloneParams(p[id]), transpose: Number(v ?? 0) } }))}
                            />
                            <span>F0 预测</span>
                            <Select
                              value={perModelParams[id]?.f0_predictor ?? 'rmvpe'}
                              onChange={(v) => setPerModelParams((p) => ({ ...p, [id]: { ...cloneParams(p[id]), f0_predictor: v } }))}
                              options={[{ value: 'rmvpe', label: 'rmvpe' }, { value: 'pm', label: 'pm' }]}
                            />
                            <span>Cluster</span>
                            <InputNumber
                              min={0}
                              max={1}
                              step={0.05}
                              value={perModelParams[id]?.cluster_ratio ?? 0}
                              onChange={(v) => setPerModelParams((p) => ({ ...p, [id]: { ...cloneParams(p[id]), cluster_ratio: Number(v ?? 0) } }))}
                            />
                          </div>
                        ) : (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                            <span>变调</span>
                            <InputNumber
                              value={perModelParams[id]?.transpose ?? 0}
                              onChange={(v) => setPerModelParams((p) => ({ ...p, [id]: { ...cloneParams(p[id]), transpose: Number(v ?? 0) } }))}
                            />
                            <span>Index</span>
                            <InputNumber
                              min={0}
                              max={1}
                              step={0.05}
                              value={perModelParams[id]?.index_rate ?? 0.75}
                              onChange={(v) => setPerModelParams((p) => ({ ...p, [id]: { ...cloneParams(p[id]), index_rate: Number(v ?? 0) } }))}
                            />
                          </div>
                        ),
                      }
                    })}
                  />
                ) : null}

                <Form.Item name="auto_start" valuePropName="checked" style={{ marginTop: 8 }}>
                  <Checkbox>创建后立即开始翻唱（推荐）</Checkbox>
                </Form.Item>

                <Button type="primary" htmlType="submit" loading={loading} block style={{ marginTop: 12 }}>
                  {autoStart ? submitText : '仅创建作品'}
                </Button>
                <Button block style={{ marginTop: 8 }} disabled={loading} onClick={() => form.validateFields().then((v) => submitPipeline(v, false))}>
                  仅创建、稍后运行
                </Button>
              </Card>
            </div>
          </Space>
        </Form>
      </Card>

      {createdWork ? (
        <Card title="创建结果">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Work ID">
              <Typography.Text copyable>{createdWork.id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="模型">
              {(createdWork.models?.length ? createdWork.models.map((m) => m.model_id).join(', ') : createdWork.model_id) || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="片段数">{createdWork.segments?.length ?? 0}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color="blue">{createdWork.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="阶段">
              <Tag color="green">{createdWork.stage}</Tag>
            </Descriptions.Item>
          </Descriptions>
          <Space style={{ marginTop: 12 }}>
            <Link to="/works">前往作品库</Link>
            <Button type="primary" size="small" onClick={() => api.startWork(createdWork.id).then((r) => {
              if (r.ok) {
                message.success('已开始')
                navigate('/works')
              } else message.error(r.error)
            })}>立即开始</Button>
          </Space>
        </Card>
      ) : null}
    </Space>
  )
}