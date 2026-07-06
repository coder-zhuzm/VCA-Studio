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
}

declare global {
  interface Window {
    pywebview?: {
      api: DesktopApi
    }
  }
}
