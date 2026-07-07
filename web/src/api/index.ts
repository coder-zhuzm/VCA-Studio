import type {
  AppStatus,
  CreateWorkPayload,
  DesktopApi,
  ImportModelPayload,
  ModelMutationResult,
  ModelRecord,
  RuntimeComponentStatus,
  RuntimeStatus,
  SetRuntimePathResult,
  SetSettingResult,
  WorkLogContentResult,
  WorkMutationResult,
  WorkRecord,
} from './types'

const mockSettings: Record<string, unknown> = {}
const mockModels: ModelRecord[] = []
const mockWorks: WorkRecord[] = []

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
  async list_models(): Promise<ModelRecord[]> {
    return mockModels
  },
  async import_model(payload: ImportModelPayload): Promise<ModelMutationResult> {
    const now = new Date().toISOString()
    const model: ModelRecord = {
      id: `model_${Date.now()}`,
      name: payload.name || payload.framework,
      framework: payload.framework,
      files: Object.fromEntries(Object.entries(payload).filter(([key, value]) => key.endsWith('_path') && value)) as Record<string, string>,
      status: 'ready',
      is_default: mockModels.length === 0,
      created_at: now,
      updated_at: now,
      checks: [],
    }
    mockModels.unshift(model)
    return { ok: true, model }
  },
  async delete_model(id: string): Promise<ModelMutationResult> {
    const index = mockModels.findIndex((model) => model.id === id)
    const wasDefault = index >= 0 && mockModels[index].is_default
    if (index >= 0) mockModels.splice(index, 1)
    if (wasDefault && mockModels[0]) mockModels[0].is_default = true
    return { ok: true, models: mockModels }
  },
  async check_model(id: string): Promise<ModelMutationResult> {
    const model = mockModels.find((item) => item.id === id)
    return model ? { ok: true, model } : { ok: false, error: '模型不存在。' }
  },
  async set_default_model(id: string): Promise<ModelMutationResult> {
    for (const model of mockModels) model.is_default = model.id === id
    return { ok: true, models: mockModels }
  },
  async create_work(payload: CreateWorkPayload): Promise<WorkMutationResult> {
    const now = new Date().toISOString()
    const workId = `work_${Date.now()}`
    const files = [
      payload.song_path ? ['input_song', payload.song_path] : undefined,
      payload.vocals_path ? ['vocals', payload.vocals_path] : undefined,
      payload.instrumental_path ? ['instrumental', payload.instrumental_path] : undefined,
    ].filter(Boolean) as [string, string][]
    const work: WorkRecord = {
      id: workId,
      name: payload.name || 'Untitled Work',
      model_id: payload.model_id,
      input_mode: payload.mode,
      input_files: files.map(([role, path]) => ({
        role,
        source_path: path,
        stored_path: path,
        filename: path.split(/[\\/]/).pop() || path,
      })),
      status: 'pending',
      stage: 'prepared',
      logs: [{ level: 'info', message: 'Input prepared', created_at: now }],
      work_dir: `.vca_studio/works/${workId}`,
      log_path: `.vca_studio/works/${workId}/run.log`,
      created_at: now,
      updated_at: now,
    }
    mockWorks.unshift(work)
    return { ok: true, work }
  },
  async list_works(): Promise<WorkMutationResult> {
    return { ok: true, works: mockWorks }
  },
  async get_work(workId: string): Promise<WorkMutationResult> {
    const work = mockWorks.find((item) => item.id === workId)
    return work ? { ok: true, work } : { ok: false, error: 'Work not found' }
  },
  async delete_work(workId: string): Promise<WorkMutationResult> {
    const index = mockWorks.findIndex((item) => item.id === workId)
    if (index < 0) return { ok: false, error: 'Work not found' }
    mockWorks.splice(index, 1)
    return { ok: true, works: mockWorks }
  },
  async read_work_log(workId: string): Promise<WorkLogContentResult> {
    const work = mockWorks.find((item) => item.id === workId)
    if (!work) return { ok: false, error: 'Work not found' }
    return {
      ok: true,
      work_id: work.id,
      log_path: work.log_path,
      content: work.logs.map((log) => `${log.created_at} [${log.level}] ${log.message}`).join('\n'),
    }
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
  listModels: async () => (await desktop()).list_models(),
  importModel: async (payload: ImportModelPayload) => (await desktop()).import_model(payload),
  deleteModel: async (id: string) => (await desktop()).delete_model(id),
  checkModel: async (id: string) => (await desktop()).check_model(id),
  setDefaultModel: async (id: string) => (await desktop()).set_default_model(id),
  createWork: async (payload: CreateWorkPayload) => (await desktop()).create_work(payload),
  listWorks: async () => (await desktop()).list_works(),
  getWork: async (workId: string) => (await desktop()).get_work(workId),
  deleteWork: async (workId: string) => (await desktop()).delete_work(workId),
  readWorkLog: async (workId: string) => (await desktop()).read_work_log(workId),
}
