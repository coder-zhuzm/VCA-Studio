import { Button, Space, Typography, message } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

type Kind = 'final' | 'ai_vocal' | 'instrumental'

const LABEL: Record<Kind, string> = {
  final: '成品',
  ai_vocal: 'AI 干声',
  instrumental: '伴奏',
}

export function WorkAudioPreview({ workId, kinds }: { workId: string; kinds: Kind[] }) {
  const [loading, setLoading] = useState<Kind | null>(null)
  const [src, setSrc] = useState('')
  const [label, setLabel] = useState('')
  const objectUrl = useRef('')

  useEffect(() => () => {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
  }, [])

  async function play(kind: Kind) {
    setLoading(kind)
    try {
      const result = await api.readWorkAudio(workId, kind)
      if (!result.ok || !result.data_base64) {
        message.warning(result.error ?? '无法加载音频')
        return
      }
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current)
      const mime = result.mime || 'audio/wav'
      const blob = await fetch(`data:${mime};base64,${result.data_base64}`).then((r) => r.blob())
      objectUrl.current = URL.createObjectURL(blob)
      setSrc(objectUrl.current)
      setLabel(LABEL[kind])
    } finally {
      setLoading(null)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Space wrap>
        {kinds.map((kind) => (
          <Button key={kind} size="small" loading={loading === kind} onClick={() => play(kind)}>
            试听{LABEL[kind]}
          </Button>
        ))}
      </Space>
      {src ? (
        <>
          <Typography.Text type="secondary">{label}</Typography.Text>
          <audio controls src={src} style={{ width: '100%' }} />
        </>
      ) : (
        <Typography.Text type="secondary">完成的作品可在此试听（需桌面环境）。</Typography.Text>
      )}
    </Space>
  )
}