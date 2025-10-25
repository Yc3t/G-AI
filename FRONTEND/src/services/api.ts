import axios from 'axios'
import type { Meeting, MeetingListItem, Participant } from '../types'

// Configure axios defaults - using relative URLs for Vite proxy
const API_BASE_URL = ''

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export const meetingApi = {
  // Verify password (frontend helper)
  async verifyPassword(password: string): Promise<boolean> {
    try {
      const res = await api.post('/verify_password', { password }, {
        // Treat 401 as a normal response so the UI can show an inline error
        validateStatus: () => true,
      })
      return !!res.data?.success
    } catch (e) {
      return false
    }
  },

  async authStatus(): Promise<boolean> {
    try {
      const res = await api.get('/auth/status')
      return !!res.data?.authorized
    } catch {
      return false
    }
  },º
  // Get all meetings
  async getMeetings(date?: string): Promise<MeetingListItem[]> {
    const params = date ? { date } : {}
    const response = await api.get('/api/reuniones', { params })
    return response.data
  },

  // Get specific meeting by ID
  async getMeeting(id: string): Promise<Meeting> {
    const response = await api.get(`/api/reunion/${id}`)
    return response.data
  },

  // Upload audio file and create meeting
  async uploadAudio(file: File): Promise<{ reunion_id: string }> {
    const formData = new FormData()
    formData.append('audio', file)
    
    const response = await api.post('/upload_and_create_meeting', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Upload and process directly (skip participants)
  async uploadAndProcessDirectly(file: File): Promise<{ reunion_id: string }> {
    const formData = new FormData()
    formData.append('audio', file)
    
    const response = await api.post('/upload_and_process_directly', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      // Long-running server processing – disable client timeout for this request
      timeout: 0,
    })
    return response.data
  },

  // Identify speakers from a short names clip (legacy endpoint kept for convenience)
  async identifySpeakersFromClip(audioBlob: Blob): Promise<{ speakers: string[] }> {
    const formData = new FormData()
    formData.append('audio_names', audioBlob, 'names.webm')
    const response = await api.post('/identify_speakers', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    try {
      const speakers = Array.isArray(response.data?.speakers) ? response.data.speakers : []
      participantsCache.set(speakers.map((n: string) => ({ name: String(n).trim() })).filter((p: Participant) => p.name))
    } catch {}
    return response.data
  },

  // REMOVED: createMeetingFromParticipants - now handled by uploadRecordedAudio

  // Upload recorded audio for existing meeting
  async uploadRecordedAudio(reunionId: string | null, audioBlob: Blob, participants?: Participant[]): Promise<{ reunion_id: string }> {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    if (reunionId) {
      formData.append('reunionId', reunionId)
    }
    const toSend = (participants && participants.length > 0) ? participants : participantsCache.get()
    if (toSend && toSend.length > 0) {
      formData.append('participants', toSend.map(p => p.name).join(','))
    }
    
    const response = await api.post('/process_final_audio', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      // Long-running server processing – disable client timeout for this request
      timeout: 0,
    })
    try { participantsCache.clear() } catch {}
    return response.data
  },

  // Update participants for existing meeting
  async updateParticipants(reunionId: string, participants: Participant[]): Promise<{ participants: Participant[] }> {
    const response = await api.put(`/api/reunion/${reunionId}/participants`, {
      participants
    })
    return response.data
  },

  // Transcribe name clip for participant identification
  async transcribeName(reunionId: string, audioBlob: Blob): Promise<{ transcript: string; suggested_name?: string }> {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'name.webm')
    
    const response = await api.post(`/api/reunion/${reunionId}/transcribe-name`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Send summary email
  async sendSummaryEmail(reunionId: string): Promise<{ delivered: string[]; failed: string[]; count: { delivered: number; failed: number } }> {
    const response = await api.post(`/api/reunion/${reunionId}/send-summary`)
    return response.data
  },

  // Send acta PDF via email
  async sendActaPdfEmail(reunionId: string): Promise<{ delivered: string[]; failed: string[]; count: { delivered: number; failed: number } }> {
    const response = await api.post(`/api/reunion/${reunionId}/send-acta-pdf`)
    return response.data
  },

  // Send acta PDF (uploaded from frontend) via email
  async sendActaPdfUpload(
    reunionId: string,
    pdfBlob: Blob,
    filename: string
  ): Promise<{ delivered: string[]; failed: string[]; count: { delivered: number; failed: number } }> {
    const formData = new FormData()
    formData.append('pdf', pdfBlob, filename)
    formData.append('filename', filename)

    const response = await api.post(`/api/reunion/${reunionId}/send-acta-pdf-upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
    return response.data
  },

  // Rename meeting
  async renameMeeting(reunionId: string, newTitle: string): Promise<{ message: string }> {
    const response = await api.put(`/rename_reunion/${reunionId}`, {
      nuevo_titulo: newTitle
    })
    return response.data
  },

  // Delete meeting
  async deleteMeeting(reunionId: string): Promise<{ message: string }> {
    const response = await api.delete(`/delete_reunion/${reunionId}`)
    return response.data
  },

  // Update meeting minutes (participants, key points, tasks, custom sections)
  async updateMinutes(reunionId: string, data: {
    participants?: Array<{ name: string; email: string | null }>
    key_points?: Array<{ title: string }>
    tasks_and_objectives?: Array<{ task: string; description: string }>
    custom_sections?: Array<{ id: string; title: string; content: string }>
  }): Promise<{ message: string }> {
    const response = await api.put(`/api/reunion/${reunionId}/minutes`, data)
    return response.data
  },

  // Upload transcript directly
  async uploadTranscript(file: File): Promise<{ reunion_id: string }> {
    const formData = new FormData()
    formData.append('transcript_file', file)
    
    const response = await api.post('/direct_summarize_transcript', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  // Verify password (for database access)
  async verifyPassword(password: string): Promise<{ success: boolean }> {
    const response = await api.post('/verify_password', { password })
    return response.data
  }
}

export const audioService = {
  // Get audio URL for meeting
  getAudioUrl(filename: string): string {
    return `/audio/${filename}`
  }
}

export default api

// Simple in-memory cache for detected participants across flows
let cachedParticipants: Participant[] = []
export const participantsCache = {
  set(list: Participant[]) { cachedParticipants = Array.isArray(list) ? list : [] },
  get(): Participant[] { return cachedParticipants },
  clear() { cachedParticipants = [] }
}

// Contacts API
export const contactsApi = {
  async list(): Promise<Array<{ name: string; email?: string }>> {
    const res = await api.get('/api/contacts')
    return res.data
  },
  async upsert(name: string, email?: string): Promise<{ name: string; email?: string }>{
    const res = await api.post('/api/contacts', { name, email })
    return res.data
  },
  async remove(name: string): Promise<{ deleted: number }>{
    const res = await api.delete(`/api/contacts/${encodeURIComponent(name)}`)
    return res.data
  }
}
