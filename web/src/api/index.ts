import type { AppStatus, DesktopApi, SetSettingResult } from './types'

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

function wantsDesktop() {
  return (
    window.location.protocol === 'file:' ||
    new URLSearchParams(window.location.search).get('desktop') === '1' ||
    new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('desktop') === '1'
  )
}

let desktopApi: Promise<DesktopApi> | undefined

async function desktop() {
  if (window.pywebview?.api) return window.pywebview.api
  if (!wantsDesktop()) return mock

  return (desktopApi ??= new Promise((resolve) => {
    window.addEventListener('pywebviewready', () => resolve(window.pywebview!.api), { once: true })
  }))
}

export const api = {
  getAppStatus: async () => (await desktop()).get_app_status(),
  getSettings: async () => (await desktop()).get_settings(),
  setSetting: async (key: string, value: unknown) => (await desktop()).set_setting(key, value),
}
