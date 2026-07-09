import type { Segment } from '../api/types'

const TIME_LINE = /\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]/g

export function parseLrc(text: string): { start: number; text: string }[] {
  const lines: { start: number; text: string }[] = []
  for (const raw of (text || '').split(/\r?\n/)) {
    const stamps: RegExpExecArray[] = []
    let m: RegExpExecArray | null
    const re = new RegExp(TIME_LINE.source, 'g')
    while ((m = re.exec(raw)) !== null) stamps.push(m)
    if (!stamps.length) continue
    const last = stamps[stamps.length - 1]
    const content = raw.slice(last.index + last[0].length).trim()
    for (const match of stamps) {
      const frac = (match[3] || '0').padEnd(3, '0')
      const start = Number(match[1]) * 60 + Number(match[2]) + Number(frac) / 1000
      lines.push({ start, text: content })
    }
  }
  lines.sort((a, b) => a.start - b.start)
  return lines
}

export function lrcToSegments(lrcText: string, defaultModelId: string): Segment[] {
  return parseLrc(lrcText).map((line, idx) => ({
    id: `seg_${String(idx).padStart(3, '0')}`,
    start: line.start,
    end: null,
    text: line.text,
    assigned_model_ids: defaultModelId ? [defaultModelId] : [],
    mode: 'solo' as const,
    fade_in: 0.03,
    fade_out: 0.03,
  }))
}