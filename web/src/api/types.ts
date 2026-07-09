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

export interface RuntimeComponentResult extends RuntimeStatus {
  ok: boolean
  error?: string
  component?: RuntimeComponentStatus
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

export interface ImportModelFromUrlPayload {
  url: string
  name?: string
}

export type WorkInputMode = 'song' | 'vocals' | 'stems'
export type WorkStatus = 'pending' | 'running' | 'done' | 'failed'
export type WorkStage = 'prepared' | 'queued' | 'inferencing' | 'mixing' | 'exported' | 'failed'
export type SegmentMode = 'solo' | 'choir' | 'mute' | 'original'

export interface Segment {
  id: string
  start: number
  end?: number | null
  text?: string
  assigned_model_ids: string[]
  mode: SegmentMode
  fade_in?: number
  fade_out?: number
}

export interface AnalysisNote {
  start: number
  end: number
  midi: number
  freq?: number
}

export interface AnalysisLyric {
  start: number
  end: number
  text: string
}

export interface Analysis {
  notes: AnalysisNote[]
  lyrics: string[]
  lyrics_aligned: AnalysisLyric[]
  created_at: string
}

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

export interface WorkStep {
  key: string
  status: string
  updated_at: string
  message: string
}

export interface WorkModelEntry {
  model_id: string
  params?: WorkParams
}

export interface WorkRecord {
  id: string
  name: string
  model_id?: string
  models?: WorkModelEntry[]
  params?: WorkParams
  segments?: Segment[]
  input_mode: WorkInputMode
  input_files: WorkInputFile[]
  status: WorkStatus
  stage: WorkStage
  progress?: number
  steps?: WorkStep[]
  logs: WorkLog[]
  work_dir?: string
  log_path?: string
  output_files?: Record<string, string>
  analysis?: Analysis
  created_at: string
  updated_at: string
}

export interface WorkAudioResult {
  ok: boolean
  error?: string
  work_id?: string
  kind?: string
  path?: string
  mime?: string
  data_base64?: string
}

export interface CreateWorkPayload {
  name: string
  model_id?: string
  models?: WorkModelEntry[]
  segments?: Segment[]
  lrc_text?: string
  params?: WorkParams
  mode: WorkInputMode
  song_path?: string
  vocals_path?: string
  instrumental_path?: string
  normalize_input?: boolean
}

export interface WorkParams {
  transpose: number
  f0_method: string
  index_rate: number
  rms_mix_rate: number
  protect: number
  filter_radius: number
  device: string
  f0_predictor?: string
  cluster_ratio?: number
  shallow_diffusion?: boolean
  vocal_volume?: number
  instrumental_volume?: number
  skip_dereverb?: boolean
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

export interface OpenPathResult {
  ok: boolean
  error?: string
  path?: string
}

export interface DesktopApi {
  get_app_status: () => Promise<AppStatus>
  get_settings: () => Promise<Record<string, unknown>>
  set_setting: (key: string, value: unknown) => Promise<SetSettingResult>
  choose_file: () => Promise<OpenPathResult>
  read_text_file: (path: string) => Promise<{ ok: boolean; error?: string; content?: string; path?: string }>
  choose_directory: () => Promise<OpenPathResult>
  open_data_dir: () => Promise<OpenPathResult>
  get_runtime_status: () => Promise<RuntimeStatus>
  check_runtime_component: (key: string) => Promise<RuntimeComponentResult>
  set_runtime_path: (key: string, path: string) => Promise<SetRuntimePathResult>
  set_runtime_paths: (paths: Record<string, string>) => Promise<SetRuntimePathResult>
  list_models: () => Promise<ModelRecord[]>
  import_model: (payload: ImportModelPayload) => Promise<ModelMutationResult>
  delete_model: (id: string) => Promise<ModelMutationResult>
  check_model: (id: string) => Promise<ModelMutationResult>
  set_default_model: (id: string) => Promise<ModelMutationResult>
  open_model_dir: (id: string) => Promise<OpenPathResult>
  import_model_from_url: (payload: ImportModelFromUrlPayload) => Promise<ModelMutationResult>
  create_work: (payload: CreateWorkPayload) => Promise<WorkMutationResult>
  list_works: () => Promise<WorkMutationResult>
  get_work: (workId: string) => Promise<WorkMutationResult>
  start_work: (workId: string) => Promise<WorkMutationResult>
  retry_work: (workId: string) => Promise<WorkMutationResult>
  rename_work: (workId: string, name: string) => Promise<WorkMutationResult>
  export_work: (workId: string, targetDir: string) => Promise<OpenPathResult>
  delete_work: (workId: string) => Promise<WorkMutationResult>
  read_work_log: (workId: string) => Promise<WorkLogContentResult>
  read_work_audio: (workId: string, kind?: string) => Promise<WorkAudioResult>
  open_work_dir: (workId: string) => Promise<OpenPathResult>
  open_work_log: (workId: string) => Promise<OpenPathResult>
  update_work_segments: (workId: string, segments: Segment[]) => Promise<WorkMutationResult>
  rerender_work: (workId: string) => Promise<WorkMutationResult>
  analyze_work: (workId: string, lyrics?: string[]) => Promise<WorkMutationResult>
  set_work_lyrics: (workId: string, lyrics: string[]) => Promise<WorkMutationResult>
}

declare global {
  interface Window {
    pywebview?: {
      api: DesktopApi
    }
  }
}
