import { Button, Card, Input, InputNumber, Select, Space, Table, Tag, Typography, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import type { ModelRecord, Segment, SegmentMode, WorkRecord } from '../api/types'

const MODE_OPTIONS: { label: string; value: SegmentMode }[] = [
  { label: '独唱 solo', value: 'solo' },
  { label: '合唱 choir', value: 'choir' },
  { label: '静音 mute', value: 'mute' },
  { label: '原声 original', value: 'original' },
]

function cloneSegments(segments?: Segment[]): Segment[] {
  return (segments ?? []).map((seg, idx) => ({
    id: seg.id || `seg_${idx}`,
    start: seg.start,
    end: seg.end ?? null,
    text: seg.text ?? '',
    assigned_model_ids: [...(seg.assigned_model_ids ?? [])],
    mode: seg.mode,
    fade_in: seg.fade_in ?? 0.03,
    fade_out: seg.fade_out ?? 0.03,
  }))
}

export function Editor() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [work, setWork] = useState<WorkRecord>()
  const [segments, setSegments] = useState<Segment[]>([])
  const [models, setModels] = useState<ModelRecord[]>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])

  const load = useCallback(async () => {
    const result = await api.getWork(id)
    if (!result.ok || !result.work) {
      message.error(result.error ?? '加载失败')
      return
    }
    setWork(result.work)
    setSegments(cloneSegments(result.work.segments))
    setDirty(false)
  }, [id])

  useEffect(() => {
    void load()
    void api.listModels().then((list) => setModels(list))
  }, [load])

  const modelOptions = models.map((model) => ({ label: `${model.name} (${model.framework})`, value: model.id }))

  function patch(index: number, next: Partial<Segment>) {
    setSegments((prev) => prev.map((seg, i) => (i === index ? { ...seg, ...next } : seg)))
    setDirty(true)
  }

  function addSegment() {
    setSegments((prev) => {
      const last = prev[prev.length - 1]
      const start = last?.end ?? 0
      const seg: Segment = {
        id: `seg_${Date.now()}`,
        start,
        end: start + 5,
        text: '',
        assigned_model_ids: models[0] ? [models[0].id] : [],
        mode: 'solo',
        fade_in: 0.03,
        fade_out: 0.03,
      }
      return [...prev, seg]
    })
    setDirty(true)
  }

  function splitSegment(index: number) {
    setSegments((prev) =>
      prev.flatMap((seg, i) => {
        if (i !== index) return [seg]
        const midpoint = seg.end != null ? (seg.start + seg.end) / 2 : seg.start + 2
        const first: Segment = { ...seg, end: midpoint, id: `${seg.id}_a` }
        const second: Segment = {
          ...seg,
          id: `${seg.id}_b`,
          start: midpoint,
          text: '',
        }
        return [first, second]
      }),
    )
    setDirty(true)
  }

  function mergeSelected() {
    if (selectedKeys.length < 2) {
      message.warning('请选择至少两个片段进行合并。')
      return
    }
    setSegments((prev) => {
      const picked = prev.filter((seg) => selectedKeys.includes(seg.id)).sort((a, b) => a.start - b.start)
      const indices = picked.map((seg) => prev.indexOf(seg))
      const contiguous = indices.every((value, i) => i === 0 || value === indices[i - 1] + 1)
      if (!contiguous) {
        message.warning('只能合并连续的片段。')
        return prev
      }
      const merged: Segment = {
        id: picked[0].id,
        start: picked[0].start,
        end: picked[picked.length - 1].end ?? null,
        text: picked.map((seg) => seg.text).filter(Boolean).join(' / '),
        assigned_model_ids: Array.from(new Set(picked.flatMap((seg) => seg.assigned_model_ids))),
        mode: picked[0].mode,
        fade_in: picked[0].fade_in ?? 0.03,
        fade_out: picked[picked.length - 1].fade_out ?? 0.03,
      }
      const pickedIds = new Set(picked.map((seg) => seg.id))
      return [...prev.filter((seg) => !pickedIds.has(seg.id)), merged]
    })
    setSelectedKeys([])
    setDirty(true)
  }

  function deleteSelected() {
    if (!selectedKeys.length) {
      message.warning('请先选择片段。')
      return
    }
    setSegments((prev) => prev.filter((seg) => !selectedKeys.includes(seg.id)))
    setSelectedKeys([])
    setDirty(true)
  }

  async function save() {
    setSaving(true)
    try {
      const result = await api.updateWorkSegments(id, segments)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '保存失败')
        return
      }
      setWork(result.work)
      setDirty(false)
      message.success('时间轴已保存')
    } finally {
      setSaving(false)
    }
  }

  async function rerender() {
    if (dirty) {
      await save()
    }
    setRendering(true)
    try {
      const result = await api.rerenderWork(id)
      if (!result.ok || !result.work) {
        message.error(result.error ?? '重渲染失败')
        setRendering(false)
        return
      }
      setWork(result.work)
      message.info('局部重渲染已开始')
      poll()
    } catch {
      setRendering(false)
    }
  }

  async function fullRerender() {
    const result = await api.startWork(id)
    if (!result.ok || !result.work) {
      message.error(result.error ?? '启动失败')
      return
    }
    setWork(result.work)
    poll()
  }

  function poll() {
    const timer = setInterval(async () => {
      const result = await api.getWork(id)
      if (result.ok && result.work) {
        setWork(result.work)
        if (result.work.status === 'done' || result.work.status === 'failed') {
          clearInterval(timer)
          setRendering(false)
          if (result.work.status === 'done') message.success('渲染完成')
          else message.warning(result.work.logs.at(-1)?.message ?? '渲染失败')
        }
      }
    }, 1500)
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 120,
    },
    {
      title: '起始(s)',
      dataIndex: 'start',
      width: 110,
      render: (_: number, _row: Segment, index: number) => (
        <InputNumber
          min={0}
          step={0.1}
          value={segments[index]?.start}
          onChange={(value) => patch(index, { start: Number(value ?? 0) })}
        />
      ),
    },
    {
      title: '结束(s)',
      dataIndex: 'end',
      width: 110,
      render: (_: number, _row: Segment, index: number) => (
        <InputNumber
          min={0}
          step={0.1}
          value={segments[index]?.end ?? null}
          onChange={(value) => patch(index, { end: value == null ? null : Number(value) })}
        />
      ),
    },
    {
      title: '歌词',
      dataIndex: 'text',
      render: (_: string, _row: Segment, index: number) => (
        <Input value={segments[index]?.text} onChange={(e) => patch(index, { text: e.target.value })} />
      ),
    },
    {
      title: '模型',
      dataIndex: 'assigned_model_ids',
      render: (_: string[], _row: Segment, index: number) => (
        <Select
          mode="multiple"
          style={{ minWidth: 180 }}
          options={modelOptions}
          value={segments[index]?.assigned_model_ids}
          onChange={(value) => patch(index, { assigned_model_ids: value })}
        />
      ),
    },
    {
      title: '模式',
      dataIndex: 'mode',
      width: 140,
      render: (_: SegmentMode, _row: Segment, index: number) => (
        <Select
          style={{ width: 130 }}
          options={MODE_OPTIONS}
          value={segments[index]?.mode}
          onChange={(value) => patch(index, { mode: value })}
        />
      ),
    },
    {
      title: '淡入',
      dataIndex: 'fade_in',
      width: 90,
      render: (_: number, _row: Segment, index: number) => (
        <InputNumber min={0} max={0.5} step={0.01} value={segments[index]?.fade_in} onChange={(value) => patch(index, { fade_in: Number(value ?? 0) })} />
      ),
    },
    {
      title: '淡出',
      dataIndex: 'fade_out',
      width: 90,
      render: (_: number, _row: Segment, index: number) => (
        <InputNumber min={0} max={0.5} step={0.01} value={segments[index]?.fade_out} onChange={(value) => patch(index, { fade_out: Number(value ?? 0) })} />
      ),
    },
    {
      title: '操作',
      width: 120,
      render: (_: unknown, _row: Segment, index: number) => (
        <Button size="small" onClick={() => splitSegment(index)}>
          拆分
        </Button>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title={`时间轴编辑 · ${work?.name ?? id}`}
        extra={
          <Space>
            <Button onClick={() => navigate('/works')}>返回</Button>
            <Button onClick={addSegment}>添加片段</Button>
            <Button onClick={mergeSelected}>合并选中</Button>
            <Button danger onClick={deleteSelected}>删除选中</Button>
            <Button onClick={save} loading={saving}>
              保存时间轴
            </Button>
            <Button type="primary" onClick={rerender} loading={rendering}>
              局部重渲染
            </Button>
            <Button onClick={fullRerender}>整轨重渲染</Button>
          </Space>
        }
      >
        <Space style={{ marginBottom: 12 }}>
          <Typography.Text>状态：</Typography.Text>
          <Tag color={work?.status === 'done' ? 'green' : work?.status === 'failed' ? 'red' : 'blue'}>{work?.status ?? '-'}</Tag>
          {work?.progress != null && <Typography.Text>进度 {work.progress}%</Typography.Text>}
          {dirty && <Tag color="orange">未保存</Tag>}
        </Space>
        <Table<Segment>
          rowKey="id"
          dataSource={segments}
          columns={columns}
          pagination={false}
          rowSelection={{ selectedRowKeys: selectedKeys, onChange: (keys) => setSelectedKeys(keys as string[]) }}
        />
      </Card>
    </Space>
  )
}
