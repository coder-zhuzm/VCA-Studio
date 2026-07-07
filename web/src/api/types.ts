export interface AppStatus {
  name: string
  title: string
  version: string
  data_dir: string
  dist_index: string
}

export interface SetSettingResult {
  ok: boolean
  settings: Record<string, unknown>
}

export type RuntimeComponentKey = 'ffmpeg' | 'ffprobe' | 'svc' | 'rvc' | 'uvr'
export type RuntimeStatusValue = 'ready' | 'missing' | 'partial' | 'error'

export interface RuntimeCheck {
  key: string
  label: string
  ok: boolean
  message: string
}

export interface RuntimeComponentStatus {
  key: RuntimeComponentKey
  name: string
  status: RuntimeStatusValue
  message: string
  checks: RuntimeCheck[]
}

export interface RuntimeStatus {
  components: RuntimeComponentStatus[]
  paths: Record<string, string>
}

export interface SetRuntimePathResult extends RuntimeStatus {
  ok: boolean
  error?: string
}

export type ModelFramework = 'rvc' | 'so-vits-svc'
export type ModelStatus = 'ready' | 'missing' | 'error'

export interface ModelCheck {
  key: string
  label: string
  ok: boolean
  message: string
}

export interface ModelRecord {
  id: string
  name: string
  framework: ModelFramework
  files: Record<string, string>
  status: ModelStatus
  is_default: boolean
  created_at: string
  updated_at: string
  checks: ModelCheck[]
}

export interface ImportModelPayload {
  name: string
  framework: ModelFramework
  checkpoint_path: string
  index_path?: string
  config_path?: string
  diffusion_path?: string
  diffusion_config_path?: string
}

export interface ModelMutationResult {
  ok: boolean
  error?: string
  model?: ModelRecord
  models?: ModelRecord[]
}

export type WorkInputMode = 'song' | 'vocals' | 'stems'
export type WorkStatus = 'pending' | 'running' | 'done' | 'failed'
export type WorkStage = 'prepared' | 'queued' | 'inferencing' | 'mixing' | 'exported' | 'failed'

export interface WorkInputFile {
  role: string
  source_path: string
  stored_path: string
  filename: string
}

export interface WorkLog {
  level: string
  message: string
  created_at: string
}

export interface WorkRecord {
  id: string
  name: string
  model_id?: string
  params?: WorkParams
  input_mode: WorkInputMode
  input_files: WorkInputFile[]
  status: WorkStatus
  stage: WorkStage
  logs: WorkLog[]
  work_dir?: string
  log_path?: string
  created_at: string
  updated_at: string
}

export interface CreateWorkPayload {
  name: string
  model_id: string
  params?: WorkParams
  mode: WorkInputMode
  song_path?: string
  vocals_path?: string
  instrumental_path?: string
}

export interface WorkParams {
  transpose: number
  f0_method: string
}

export interface WorkMutationResult {
  ok: boolean
  error?: string
  work?: WorkRecord
  works?: WorkRecord[]
}

export interface WorkLogContentResult {
  ok: boolean
  error?: string
  work_id?: string
  log_path?: string
  content?: string
}

export interface DesktopApi {
  get_app_status: () => Promise<AppStatus>
  get_settings: () => Promise<Record<string, unknown>>
  set_setting: (key: string, value: unknown) => Promise<SetSettingResult>
  get_runtime_status: () => Promise<RuntimeStatus>
  set_runtime_path: (key: string, path: string) => Promise<SetRuntimePathResult>
  set_runtime_paths: (paths: Record<string, string>) => Promise<SetRuntimePathResult>
  list_models: () => Promise<ModelRecord[]>
  import_model: (payload: ImportModelPayload) => Promise<ModelMutationResult>
  delete_model: (id: string) => Promise<ModelMutationResult>
  check_model: (id: string) => Promise<ModelMutationResult>
  set_default_model: (id: string) => Promise<ModelMutationResult>
  create_work: (payload: CreateWorkPayload) => Promise<WorkMutationResult>
  list_works: () => Promise<WorkMutationResult>
  get_work: (workId: string) => Promise<WorkMutationResult>
  delete_work: (workId: string) => Promise<WorkMutationResult>
  read_work_log: (workId: string) => Promise<WorkLogContentResult>
}

declare global {
  interface Window {
    pywebview?: {
      api: DesktopApi
    }
  }
}
