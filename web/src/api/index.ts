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

function desktop() {
  return window.pywebview?.api ?? mock
}

export const api = {
  getAppStatus: () => desktop().get_app_status(),
  getSettings: () => desktop().get_settings(),
  setSetting: (key: string, value: unknown) => desktop().set_setting(key, value),
}
