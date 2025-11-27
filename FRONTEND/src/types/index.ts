export interface Participant {
  name: string
  email?: string
}

export interface MeetingMetadata {
  title: string
  participants: string[]
  date?: string
  duration_seconds?: number
  meeting_id?: string
}

export interface KeyTimestamp {
  description: string
  time?: string
}

export interface DetailedSummaryItem {
  title: string
  content: string
  key_timestamps: KeyTimestamp[]
  start_time?: string
}

export interface MainPoint {
  id: string
  title: string
  time?: string
}

export interface ActionItem {
  task: string
  description: string
}

export interface TranscriptSegment {
  id: number
  start: number
  text: string
}

export interface TranscriptData {
  segments: TranscriptSegment[]
}

export interface CustomSection {
  id: string
  title: string
  content: string
}

export interface MinutesData {
  metadata: {
    title: string
    date?: string
    duration_seconds?: number
    meeting_id?: string
  }
  objective?: string
  participants: Participant[]
  key_points: {
    id: string
    title: string
    time?: string
  }[]
  details: Record<string, {
    title?: string
    content: string
  }>
  custom_sections?: CustomSection[]
  tasks_and_objectives?: ActionItem[]
}

export interface Meeting {
  id: string
  titulo: string
  audio_filename?: string
  full_transcript_data?: TranscriptData
  participants: Participant[]
  is_processed: boolean
  fecha_de_subida?: string
  minutes?: MinutesData
}

export interface MeetingListItem {
  id: string
  titulo: string
  fecha_de_subida: string
  is_processed?: boolean
}

export interface RecorderState {
  isRecording: boolean
  isPreRecording: boolean
  isPaused: boolean
  recordingTime: number
  audioLevel: number
  hasPermission: boolean
}

export interface AudioVisualizerProps {
  isRecording: boolean
  isPreRecording?: boolean
  audioLevel: number
  duration: number
  namesClipDurationSec?: number
  hasCompletedNamesClip?: boolean
  namesClipBlob?: Blob | null
  showHeader?: boolean
  showStatus?: boolean
  fitParent?: boolean
}

export interface ApiResponse<T = any> {
  data?: T
  error?: string
  message?: string
}
