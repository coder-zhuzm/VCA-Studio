import type {
  AppStatus,
  CreateWorkPayload,
  DesktopApi,
  ImportModelPayload,
  ModelMutationResult,
  ModelRecord,
  OpenPathResult,
  RuntimeComponentResult,
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
  async choose_file(): Promise<OpenPathResult> {
    return { ok: false, error: '浏览器 mock 不支持文件选择，请手动输入路径。' }
  },
  async choose_directory(): Promise<OpenPathResult> {
    return { ok: false, error: '浏览器 mock 不支持目录选择，请手动输入路径。' }
  },
  async open_data_dir(): Promise<OpenPathResult> {
    return { ok: true, path: '.vca_studio' }
  },
  async get_runtime_status(): Promise<RuntimeStatus> {
    return mockRuntimeStatus()
  },
  async check_runtime_component(key: string): Promise<RuntimeComponentResult> {
    const status = mockRuntimeStatus()
    return { ok: true, ...status, component: status.components.find((item) => item.key === key) }
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
  async open_model_dir(id: string): Promise<OpenPathResult> {
    const model = mockModels.find((item) => item.id === id)
    const first = model ? Object.values(model.files)[0] : ''
    return model ? { ok: true, path: first ? first.replace(/[\\/][^\\/]*$/, '') : '' } : { ok: false, error: '模型不存在。' }
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
      params: payload.params,
      input_mode: payload.mode,
      input_files: files.map(([role, path]) => ({
        role,
        source_path: path,
        stored_path: path,
        filename: path.split(/[\\/]/).pop() || path,
      })),
      status: 'pending',
      stage: 'prepared',
      progress: 10,
      steps: [{ key: 'prepare', status: 'done', updated_at: now, message: 'Input prepared' }],
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
  async start_work(workId: string): Promise<WorkMutationResult> {
    const work = mockWorks.find((item) => item.id === workId)
    if (!work) return { ok: false, error: 'Work not found' }
    if (work.status !== 'pending' || work.stage !== 'prepared') return { ok: true, work }
    const now = new Date().toISOString()
    const log = { level: 'error', message: '浏览器 mock：真实 RVC 推理尚未接入。', created_at: now }
    Object.assign(work, {
      status: 'failed',
      stage: 'failed',
      progress: work.progress ?? 0,
      steps: [...(work.steps ?? []), { key: 'run', status: 'failed', updated_at: now, message: log.message }],
      logs: [...work.logs, log],
      updated_at: now,
    })
    return { ok: true, work }
  },
  async retry_work(workId: string): Promise<WorkMutationResult> {
    const work = mockWorks.find((item) => item.id === workId)
    if (!work) return { ok: false, error: 'Work not found' }
    if (work.status !== 'failed') return { ok: true, work }
    const now = new Date().toISOString()
    Object.assign(work, {
      status: 'pending',
      stage: 'prepared',
      progress: 10,
      steps: [...(work.steps ?? []).filter((step) => step.status !== 'failed'), { key: 'retry', status: 'done', updated_at: now, message: 'Work reset for retry' }],
      logs: [...work.logs, { level: 'info', message: 'Work reset for retry', created_at: now }],
      updated_at: now,
    })
    return { ok: true, work }
  },
  async rename_work(workId: string, name: string): Promise<WorkMutationResult> {
    const work = mockWorks.find((item) => item.id === workId)
    if (!work) return { ok: false, error: 'Work not found' }
    const cleaned = name.trim()
    if (!cleaned) return { ok: false, error: '作品名称不能为空。' }
    work.name = cleaned
    work.updated_at = new Date().toISOString()
    return { ok: true, work }
  },
  async export_work(workId: string, targetDir: string): Promise<OpenPathResult> {
    const work = mockWorks.find((item) => item.id === workId)
    if (!work) return { ok: false, error: 'Work not found' }
    return { ok: false, error: targetDir ? '浏览器 mock 没有真实输出文件。' : '导出目录不存在。' }
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
  async open_work_dir(workId: string): Promise<OpenPathResult> {
    const work = mockWorks.find((item) => item.id === workId)
    return work ? { ok: true, path: work.work_dir } : { ok: false, error: 'Work not found' }
  },
  async open_work_log(workId: string): Promise<OpenPathResult> {
    const work = mockWorks.find((item) => item.id === workId)
    return work ? { ok: true, path: work.log_path } : { ok: false, error: 'Work not found' }
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
  chooseFile: async () => (await desktop()).choose_file(),
  chooseDirectory: async () => (await desktop()).choose_directory(),
  openDataDir: async () => (await desktop()).open_data_dir(),
  getRuntimeStatus: async () => (await desktop()).get_runtime_status(),
  checkRuntimeComponent: async (key: string) => (await desktop()).check_runtime_component(key),
  setRuntimePath: async (key: string, path: string) => (await desktop()).set_runtime_path(key, path),
  setRuntimePaths: async (paths: Record<string, string>) => (await desktop()).set_runtime_paths(paths),
  listModels: async () => (await desktop()).list_models(),
  importModel: async (payload: ImportModelPayload) => (await desktop()).import_model(payload),
  deleteModel: async (id: string) => (await desktop()).delete_model(id),
  checkModel: async (id: string) => (await desktop()).check_model(id),
  setDefaultModel: async (id: string) => (await desktop()).set_default_model(id),
  openModelDir: async (id: string) => (await desktop()).open_model_dir(id),
  createWork: async (payload: CreateWorkPayload) => (await desktop()).create_work(payload),
  listWorks: async () => (await desktop()).list_works(),
  getWork: async (workId: string) => (await desktop()).get_work(workId),
  startWork: async (workId: string) => (await desktop()).start_work(workId),
  retryWork: async (workId: string) => (await desktop()).retry_work(workId),
  renameWork: async (workId: string, name: string) => (await desktop()).rename_work(workId, name),
  exportWork: async (workId: string, targetDir: string) => (await desktop()).export_work(workId, targetDir),
  deleteWork: async (workId: string) => (await desktop()).delete_work(workId),
  readWorkLog: async (workId: string) => (await desktop()).read_work_log(workId),
  openWorkDir: async (workId: string) => (await desktop()).open_work_dir(workId),
  openWorkLog: async (workId: string) => (await desktop()).open_work_log(workId),
}
