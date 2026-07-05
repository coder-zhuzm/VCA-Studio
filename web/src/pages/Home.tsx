import { Card, Descriptions, Spin } from 'antd'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AppStatus } from '../api/types'

export function Home() {
  const [status, setStatus] = useState<AppStatus | null>(null)

  useEffect(() => {
    api.getAppStatus().then(setStatus)
  }, [])

  if (!status) return <Spin />

  return (
    <Card title="首页">
      <Descriptions column={1} bordered size="small">
        <Descriptions.Item label="应用">{status.title}</Descriptions.Item>
        <Descriptions.Item label="版本">{status.version}</Descriptions.Item>
        <Descriptions.Item label="数据目录">{status.data_dir}</Descriptions.Item>
      </Descriptions>
    </Card>
  )
}
