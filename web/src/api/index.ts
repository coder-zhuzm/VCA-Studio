import type { AppStatus, SetSettingResult } from './types'

const mockSettings: Record<string, unknown> = {}

const mock = {
  async get_app_status(): Promise<AppStatus> {
    return {
      name: 'VCA-Studio',
      title: 'VCA-Studio',
      version: '0.1.0',
      data_dir: '.vca_studio',
      dist_index: 'web/dist/index.html',
    }
  },
  async get_settings(): Promise<Record<string, unknown>> {
    return mockSettings
  },
  async set_setting(key: string, value: unknown): Promise<SetSettingResult> {
    mockSettings[key] = value
    return { ok: true, settings: mockSettings }
  },
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function desktop() {
  if (window.pywebview?.api) return window.pywebview.api

  if (window.location.protocol === 'file:') {
    for (let i = 0; i < 20; i++) {
      await delay(25)
      if (window.pywebview?.api) return window.pywebview.api
    }
  }

  return mock
}

export const api = {
  getAppStatus: async () => (await desktop()).get_app_status(),
  getSettings: async () => (await desktop()).get_settings(),
  setSetting: async (key: string, value: unknown) => (await desktop()).set_setting(key, value),
}
