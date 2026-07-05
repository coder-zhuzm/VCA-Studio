import type { AppStatus, DesktopApi, RuntimeComponentStatus, RuntimeStatus, SetRuntimePathResult, SetSettingResult } from './types'

const mockSettings: Record<string, unknown> = {}

const mockRuntimePaths: Record<string, string> = {
  ffmpeg_path: '',
  ffprobe_path: '',
  rvc_python: '',
  sovits_repo: '',
  svc_python: '',
  uvr_model_dir: '',
  uvr_python: '',
}

function mockComponent(key: RuntimeComponentStatus['key'], name: string): RuntimeComponentStatus {
  return { key, name, status: 'missing', message: '浏览器 mock：未检测', checks: [] }
}

function mockRuntimeStatus(): RuntimeStatus {
  return {
    components: [
      mockComponent('ffmpeg', 'ffmpeg'),
      mockComponent('ffprobe', 'ffprobe'),
      mockComponent('svc', 'So-VITS-SVC'),
      mockComponent('rvc', 'RVC'),
      mockComponent('uvr', 'UVR'),
    ],
    paths: mockRuntimePaths,
  }
}

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
  async get_runtime_status(): Promise<RuntimeStatus> {
    return mockRuntimeStatus()
  },
  async set_runtime_path(key: string, value: string): Promise<SetRuntimePathResult> {
    mockRuntimePaths[key] = value
    return { ok: true, ...mockRuntimeStatus() }
  },
  async set_runtime_paths(paths: Record<string, string>): Promise<SetRuntimePathResult> {
    Object.assign(mockRuntimePaths, paths)
    return { ok: true, ...mockRuntimeStatus() }
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
  getRuntimeStatus: async () => (await desktop()).get_runtime_status(),
  setRuntimePath: async (key: string, path: string) => (await desktop()).set_runtime_path(key, path),
  setRuntimePaths: async (paths: Record<string, string>) => (await desktop()).set_runtime_paths(paths),
}
