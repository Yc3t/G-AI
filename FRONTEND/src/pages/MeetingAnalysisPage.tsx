import React, { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  FileText,
  Download,
  Mail,
  ChevronDown,
  ChevronUp,
  Search,
  Copy,
  Check,
  ChevronRight,
  ChevronLeft,
  Plus,
  Trash2,
  SquarePen,
  Save,
  Database,
  Home,
  ScrollText,
  X
} from 'lucide-react'
import type { Meeting } from '../types'
import { meetingApi, audioService } from '../services/api'
import { formatDuration, parseTimestamp } from '../services/audioUtils'
import { WaveformPlayer } from '../components/WaveformPlayer'
import { MarkdownContent } from '../components/MarkdownContent'
import { exportActaToPDF, exportSummaryToPDF, buildActaPdfBlob } from '../utils/pdfExport'

interface EditableParticipant {
  name: string
  email: string | null
}

interface EditableKeyPoint {
  title: string
}

interface EditableTask {
  task: string
  description: string
}

interface CustomSection {
  id: string
  title: string
  content: string
}

export const MeetingAnalysisPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedPoints, setExpandedPoints] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [showEmailModal, setShowEmailModal] = useState(false)
  const [sendingEmail, setSendingEmail] = useState(false)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'minutes' | 'summary'>('minutes')
  const [showTranscript, setShowTranscript] = useState(true)
  const [showTranscriptModal, setShowTranscriptModal] = useState(false)
  const [seekTime, setSeekTime] = useState<number | undefined>(undefined)

  // Editable state
  const [isEditMode, setIsEditMode] = useState(false)
  const [editableParticipants, setEditableParticipants] = useState<EditableParticipant[]>([])
  const [editableKeyPoints, setEditableKeyPoints] = useState<EditableKeyPoint[]>([])
  const [editableTasks, setEditableTasks] = useState<EditableTask[]>([])
  const [customSections, setCustomSections] = useState<CustomSection[]>([])
  const [saving, setSaving] = useState(false)
  const [emailRecipients, setEmailRecipients] = useState<EditableParticipant[]>([])

  useEffect(() => {
    if (id) {
      loadMeeting()
      // Set up polling for ongoing processing
      const interval = setInterval(() => {
        if (meeting && !meeting.is_processed) {
          loadMeeting()
        }
      }, 5000)
      
      return () => clearInterval(interval)
    }
  }, [id])


  const loadMeeting = async () => {
    if (!id) return

    try {
      setLoading(true)
      const data = await meetingApi.getMeeting(id)
      setMeeting(data)

      // (debug logs removed)

      // Initialize editable state from meeting data
      if (data.minutes) {
        setEditableParticipants((data.minutes.participants || []).map(p => ({ name: p.name, email: p.email ?? null })))
        setEditableKeyPoints((data.minutes.key_points || []).map(kp => ({ title: kp.title })))
        setEditableTasks((data.minutes.tasks_and_objectives || []).map(t => ({ task: t.task, description: t.description || '' })))
        setCustomSections(data.minutes.custom_sections || [])
      }

      setError(null)
    } catch (error) {
      console.error('Failed to load meeting:', error)
      setError('Error al cargar la reunión')
    } finally {
      setLoading(false)
    }
  }

  const enterEditMode = () => {
    if (meeting?.minutes) {
      setEditableParticipants(meeting.minutes.participants.map(p => ({ name: p.name, email: p.email ?? null })))
      setEditableKeyPoints(meeting.minutes.key_points.map(kp => ({ title: kp.title })))
      setEditableTasks((meeting.minutes.tasks_and_objectives || []).map(t => ({ task: t.task, description: t.description || '' })))
      setCustomSections([...(meeting.minutes.custom_sections || [])])
      setIsEditMode(true)
    }
  }

  const cancelEditMode = () => {
    setIsEditMode(false)
  }

  const saveChanges = async () => {
    if (!id) return

    setSaving(true)
    try {
      await meetingApi.updateMinutes(id, {
        participants: editableParticipants,
        key_points: editableKeyPoints,
        tasks_and_objectives: editableTasks,
        custom_sections: customSections
      })

      // Update local state (merge to preserve ids/times)
      if (meeting?.minutes) {
        const mergedKeyPoints = (meeting.minutes.key_points || []).map((kp, idx) => ({
          ...kp,
          title: editableKeyPoints[idx]?.title ?? kp.title
        }))
        const mergedParticipants = editableParticipants.map(p => ({ name: p.name, email: p.email || undefined }))
        const mergedTasks = editableTasks.map(t => ({ task: t.task, description: t.description }))
        setMeeting({
          ...meeting,
          minutes: {
            ...meeting.minutes,
            participants: mergedParticipants,
            key_points: mergedKeyPoints,
            tasks_and_objectives: mergedTasks,
            custom_sections: customSections
          }
        })
      }

      setIsEditMode(false)
    } catch (error) {
      console.error('Failed to save changes:', error)
      alert('Error al guardar los cambios')
    } finally {
      setSaving(false)
    }
  }

  // Participant editing functions
  const addParticipant = () => {
    setEditableParticipants([...editableParticipants, { name: '', email: null }])
  }

  const updateParticipant = (index: number, field: 'name' | 'email', value: string) => {
    const updated = [...editableParticipants]
    updated[index] = { ...updated[index], [field]: value || null }
    setEditableParticipants(updated)
  }

  const removeParticipant = (index: number) => {
    setEditableParticipants(editableParticipants.filter((_, i) => i !== index))
  }

  // Key point editing functions
  const addKeyPoint = () => {
    setEditableKeyPoints([...editableKeyPoints, { title: '' }])
  }

  const updateKeyPoint = (index: number, value: string) => {
    const updated = [...editableKeyPoints]
    updated[index] = { title: value }
    setEditableKeyPoints(updated)
  }

  const removeKeyPoint = (index: number) => {
    setEditableKeyPoints(editableKeyPoints.filter((_, i) => i !== index))
  }

  // Task editing functions
  const addTask = () => {
    setEditableTasks([...editableTasks, { task: '', description: '' }])
  }

  const updateTask = (index: number, field: 'task' | 'description', value: string) => {
    const updated = [...editableTasks]
    updated[index] = { ...updated[index], [field]: value }
    setEditableTasks(updated)
  }

  const removeTask = (index: number) => {
    setEditableTasks(editableTasks.filter((_, i) => i !== index))
  }

  // Custom section editing functions
  const addCustomSection = () => {
    setCustomSections([...customSections, { id: Date.now().toString(), title: '', content: '' }])
  }

  const updateCustomSection = (id: string, field: 'title' | 'content', value: string) => {
    const updated = customSections.map(section =>
      section.id === id ? { ...section, [field]: value } : section
    )
    setCustomSections(updated)
  }

  const removeCustomSection = (id: string) => {
    setCustomSections(customSections.filter(section => section.id !== id))
  }

  const togglePoint = (pointId: string) => {
    const newExpanded = new Set(expandedPoints)
    if (newExpanded.has(pointId)) {
      newExpanded.delete(pointId)
    } else {
      newExpanded.add(pointId)
    }
    setExpandedPoints(newExpanded)
  }

  const seekToTime = (timeStr: string) => {
    if (timeStr) {
      const seconds = parseTimestamp(timeStr)
      setSeekTime(seconds)
    }
  }

  const copyTranscript = async () => {
    if (!meeting?.full_transcript_data?.segments) return
    
    const fullText = meeting.full_transcript_data.segments
      .map(segment => `[${formatDuration(segment.start)}] ${segment.text}`)
      .join('\n')
    
    try {
      await navigator.clipboard.writeText(fullText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy text:', error)
    }
  }

  const filteredSegments = useMemo(() => {
    const list = meeting?.full_transcript_data?.segments || []
    const q = searchTerm.toLowerCase()
    if (!q) return list
    return list.filter(segment => segment.text.toLowerCase().includes(q))
  }, [meeting?.full_transcript_data?.segments, searchTerm])

  const openEmailModal = () => {
    // Initialize email recipients from ALL current participants (including those without emails)
    const recipients = (meeting?.minutes?.participants || [])
      .map(p => ({ name: p.name, email: p.email || null }))
    setEmailRecipients(recipients)
    setShowEmailModal(true)
  }

  const addEmailRecipient = () => {
    setEmailRecipients([...emailRecipients, { name: '', email: null }])
  }

  const updateEmailRecipient = (index: number, field: 'name' | 'email', value: string) => {
    const updated = [...emailRecipients]
    updated[index] = { ...updated[index], [field]: value || null }
    setEmailRecipients(updated)
  }

  const removeEmailRecipient = (index: number) => {
    setEmailRecipients(emailRecipients.filter((_, i) => i !== index))
  }

  const handleSendEmail = async () => {
    if (!id) return

    setSendingEmail(true)
    try {
      // 1) Persist recipients as participants (backend email endpoint reads from DB)
      const recipients = emailRecipients
        .map(r => ({ name: (r.name || '').trim(), email: (r.email || '').trim() }))
        .filter(r => r.name && r.email)

      if (recipients.length === 0) throw new Error('No recipients to send')

      await meetingApi.updateParticipants(id, recipients)

      // 2) Build the PDF in the frontend and upload it to email exactly that file
      if (!meeting) throw new Error('Meeting not loaded')
      const built = await buildActaPdfBlob(meeting)
      if (!built) throw new Error('No se pudo generar el PDF en el frontend')
      await meetingApi.sendActaPdfUpload(id, built.blob, built.filename)

      setShowEmailModal(false)
      setEmailRecipients([])
    } catch (error) {
      console.error('Failed to send email:', error)
    } finally {
      setSendingEmail(false)
    }
  }

  const handleExportActa = () => {
    if (meeting) {
      exportActaToPDF(meeting)
    }
  }

  const handleExportSummary = () => {
    if (meeting) {
      exportSummaryToPDF(meeting)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <h3 className="text-lg font-semibold text-gray-900">Cargando reunión...</h3>
          <p className="text-gray-600">Esto puede tomar unos minutos para reuniones nuevas</p>
        </div>
      </div>
    )
  }

  if (error || !meeting) {
    return (
      <div className="text-center space-y-4">
        <h2 className="text-2xl font-bold text-gray-900">Error</h2>
        <p className="text-gray-600">{error || 'Reunión no encontrada'}</p>
        <button
          onClick={() => navigate('/database')}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors"
        >
          Volver a la base de datos
        </button>
      </div>
    )
  }

  if (!meeting.is_processed) {
    return (
      <div className="text-center space-y-6">
        <div className="animate-pulse">
          <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileText className="h-8 w-8 text-primary-600" />
          </div>
        </div>
        <h2 className="text-3xl font-bold text-gray-900">Procesando reunión...</h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          La IA está analizando la transcripción y generando el resumen. 
          Los resultados aparecerán automáticamente cuando esté listo.
        </p>
        <div className="bg-white rounded-lg p-6 shadow-lg border max-w-md mx-auto">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
            <span className="text-gray-700">Analizando contenido...</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top Navbar */}
      <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/database')}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
            aria-label="Ver base de datos de reuniones"
          >
            <Database className="h-5 w-5" />
          </button>
          <img
            src="/frumecar.jpg"
            alt="Frumecar"
            className="h-10 w-10 rounded-xl object-contain shadow-sm ring-1 ring-slate-200"
          />
          <button
            onClick={() => navigate('/')}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
            aria-label="Ir a inicio"
          >
            <Home className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Main Layout */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex overflow-hidden">
          {/* Main Content Area */}
          <div className="flex-1 flex flex-col bg-white">
          {/* Tab Navigation */}
          <div className="border-b border-gray-200">
            <div className="flex px-4 sm:px-6">
              <button
                onClick={() => setActiveTab('minutes')}
                className={`flex-1 sm:flex-none px-4 sm:px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'minutes'
                    ? 'text-primary-600 border-b-2 border-primary-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Acta
              </button>
              <button
                onClick={() => setActiveTab('summary')}
                className={`flex-1 sm:flex-none px-4 sm:px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'summary'
                    ? 'text-primary-600 border-b-2 border-primary-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Resumen
              </button>
            </div>
          </div>

          {/* Tab Content - Scrollable */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4 sm:p-6">
              {activeTab === 'minutes' && meeting.minutes && (
                <div className="space-y-6">
                  {/* Meeting Metadata */}
                  <div className="pb-4 border-b border-gray-200">
                    <div className="space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        {(() => {
                          const metaTitle = meeting.minutes?.metadata?.title
                          const displayTitle = (typeof metaTitle === 'string' && metaTitle.trim()) ? metaTitle : meeting.titulo
                          return (
                            <h2 className="text-base sm:text-lg font-semibold text-gray-900">{displayTitle}</h2>
                          )
                        })()}
                        <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                          {isEditMode ? (
                            <>
                              <button
                                onClick={cancelEditMode}
                                className="text-gray-600 hover:text-gray-800 px-2 sm:px-3 py-1 rounded transition-colors text-xs sm:text-sm"
                              >
                                Cancelar
                              </button>
                              <button
                                onClick={saveChanges}
                                disabled={saving}
                                className="bg-gray-600 text-white px-2 sm:px-3 py-1 rounded hover:bg-gray-700 transition-colors flex items-center space-x-1 text-xs sm:text-sm disabled:opacity-50"
                              >
                                <Save className="h-3 w-3 sm:h-4 sm:w-4" />
                                <span className="hidden sm:inline">{saving ? 'Guardando...' : 'Guardar'}</span>
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={enterEditMode}
                                className="text-gray-500 hover:text-gray-700 transition-colors flex items-center space-x-1 px-2 sm:px-3 py-1 rounded hover:bg-gray-50"
                                title="Editar acta"
                              >
                                <SquarePen className="h-3 w-3 sm:h-4 sm:w-4" />
                                <span className="text-xs sm:text-sm hidden sm:inline">Editar</span>
                              </button>
                              <button
                                onClick={openEmailModal}
                                className="text-gray-500 hover:text-gray-700 transition-colors flex items-center space-x-1 px-2 sm:px-3 py-1 rounded hover:bg-gray-50"
                                title="Enviar por email"
                              >
                                <Mail className="h-3 w-3 sm:h-4 sm:w-4" />
                                <span className="text-xs sm:text-sm hidden sm:inline">Enviar</span>
                              </button>
                              <button
                                onClick={handleExportActa}
                                className="text-gray-500 hover:text-gray-700 transition-colors flex items-center space-x-1 px-2 sm:px-3 py-1 rounded hover:bg-gray-50"
                                title="Exportar Acta"
                              >
                                <Download className="h-3 w-3 sm:h-4 sm:w-4" />
                                <span className="text-xs sm:text-sm hidden sm:inline">Exportar</span>
                              </button>
                              <button
                                onClick={() => setShowTranscriptModal(true)}
                                className="md:hidden text-gray-500 hover:text-gray-700 transition-colors flex items-center space-x-1 px-2 sm:px-3 py-1 rounded hover:bg-gray-50"
                                title="Ver transcripción"
                              >
                                <ScrollText className="h-3 w-3 sm:h-4 sm:w-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs sm:text-sm text-gray-600">
                        <span>
                          <span className="font-medium">Fecha:</span>{' '}
                          {meeting.minutes.metadata.date ? new Date(meeting.minutes.metadata.date).toLocaleDateString() : 'No especificada'}
                        </span>
                        <span>
                          <span className="font-medium">Duración:</span>{' '}
                          {meeting.minutes.metadata.duration_seconds ? formatDuration(meeting.minutes.metadata.duration_seconds) : 'No especificada'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Participants */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-gray-900">Participantes</h3>
                      {isEditMode && (
                        <button
                          onClick={addParticipant}
                          className="text-primary-600 hover:text-primary-700 text-sm flex items-center space-x-1"
                        >
                          <Plus className="h-4 w-4" />
                          <span>Agregar</span>
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
                      {(isEditMode ? editableParticipants : meeting.minutes.participants).map((participant, index) => (
                        <div key={index} className="flex items-center space-x-2 sm:space-x-3 text-sm">
                          {!isEditMode && (
                            <>
                              <div className="w-6 h-6 rounded-full bg-slate-300 flex items-center justify-center flex-shrink-0">
                                <span className="text-[10px] font-semibold text-slate-700">
                                  {participant.name?.[0]?.toUpperCase() ?? '?'}
                                </span>
                              </div>
                              <div className="min-w-0">
                                <div className="font-medium text-gray-900 truncate">{participant.name}</div>
                                {participant.email && <div className="text-gray-500 text-xs truncate">{participant.email}</div>}
                              </div>
                            </>
                          )}
                          {isEditMode && (
                            <div className="flex-1 space-y-2 p-3 border border-gray-300 rounded-lg relative">
                              <button
                                onClick={() => removeParticipant(index)}
                                className="absolute top-1 right-1 text-gray-400 hover:text-red-600"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                              <input
                                type="text"
                                value={participant.name}
                                onChange={(e) => updateParticipant(index, 'name', e.target.value)}
                                placeholder="Nombre"
                                className="w-full text-sm border border-gray-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                              />
                              <input
                                type="email"
                                value={participant.email || ''}
                                onChange={(e) => updateParticipant(index, 'email', e.target.value)}
                                placeholder="Email (opcional)"
                                className="w-full text-xs border border-gray-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                              />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

              {/* Key Points */}
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-gray-900">Puntos Clave</h3>
                      {isEditMode && (
                        <button
                          onClick={addKeyPoint}
                          className="text-primary-600 hover:text-primary-700 text-sm flex items-center space-x-1"
                        >
                          <Plus className="h-4 w-4" />
                          <span>Agregar</span>
                        </button>
                      )}
                    </div>
                    <div className="space-y-3">
                      {(isEditMode ? editableKeyPoints : meeting.minutes.key_points).map((point, index) => (
                        <div key={index} className="flex items-start space-x-3">
                          <span className="flex-shrink-0 w-6 h-6 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center text-xs font-semibold">
                            {index + 1}
                          </span>
                          {!isEditMode && (
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-900">{point.title}</p>
                            </div>
                          )}
                          {isEditMode && (
                            <div className="flex-1 flex items-center space-x-2">
                              <input
                                type="text"
                                value={point.title}
                                onChange={(e) => updateKeyPoint(index, e.target.value)}
                                placeholder="Título del punto clave"
                                className="flex-1 text-sm border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                              />
                              <button
                                onClick={() => removeKeyPoint(index)}
                                className="text-gray-400 hover:text-red-600"
                              >
                                <Trash2 className="h-5 w-5" />
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Custom Sections */}
                  {(isEditMode || customSections.length > 0) && (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-gray-900">Secciones Personalizadas</h3>
                        {isEditMode && (
                          <button
                            onClick={addCustomSection}
                            className="text-primary-600 hover:text-primary-700 text-sm flex items-center space-x-1"
                          >
                            <Plus className="h-4 w-4" />
                            <span>Agregar Sección</span>
                          </button>
                        )}
                      </div>
                      <div className="space-y-4">
                        {customSections.map((section) => (
                          <div key={section.id} className="border border-gray-200 rounded-lg p-4">
                            {!isEditMode && (
                              <>
                                <h4 className="text-sm font-semibold text-gray-900 mb-2">{section.title}</h4>
                                <p className="text-sm text-gray-700 whitespace-pre-wrap">{section.content}</p>
                              </>
                            )}
                            {isEditMode && (
                              <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                  <input
                                    type="text"
                                    value={section.title}
                                    onChange={(e) => updateCustomSection(section.id, 'title', e.target.value)}
                                    placeholder="Título de la sección"
                                    className="flex-1 text-sm font-semibold border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                  />
                                  <button
                                    onClick={() => removeCustomSection(section.id)}
                                    className="ml-2 text-gray-400 hover:text-red-600"
                                  >
                                    <Trash2 className="h-5 w-5" />
                                  </button>
                                </div>
                                <textarea
                                  value={section.content}
                                  onChange={(e) => updateCustomSection(section.id, 'content', e.target.value)}
                                  placeholder="Contenido de la sección"
                                  rows={4}
                                  className="w-full text-sm border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tasks and Objectives */}
                  {(isEditMode || (meeting?.minutes?.tasks_and_objectives && meeting.minutes.tasks_and_objectives.length > 0)) && (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-gray-900">Tareas y Objetivos</h3>
                        {isEditMode && (
                          <button
                            onClick={addTask}
                            className="text-primary-600 hover:text-primary-700 text-sm flex items-center space-x-1"
                          >
                            <Plus className="h-4 w-4" />
                            <span>Agregar</span>
                          </button>
                        )}
                      </div>
                      <div className="space-y-3">
                        {(isEditMode ? editableTasks : meeting.minutes.tasks_and_objectives || []).map((item, index) => (
                          <div key={index} className="flex items-start space-x-3">
                            <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">
                              {index + 1}
                            </span>
                            {!isEditMode && (
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900">{item.task}</p>
                                {item.description && (
                                  <p className="text-xs text-gray-600 mt-1">{item.description}</p>
                                )}
                              </div>
                            )}
                            {isEditMode && (
                              <div className="flex-1 space-y-2">
                                <div className="flex items-start space-x-2">
                                  <input
                                    type="text"
                                    value={item.task}
                                    onChange={(e) => updateTask(index, 'task', e.target.value)}
                                    placeholder="Título de la tarea"
                                    className="flex-1 text-sm font-medium border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                  />
                                  <button
                                    onClick={() => removeTask(index)}
                                    className="text-gray-400 hover:text-red-600 mt-1"
                                  >
                                    <Trash2 className="h-5 w-5" />
                                  </button>
                                </div>
                                <input
                                  type="text"
                                  value={item.description}
                                  onChange={(e) => updateTask(index, 'description', e.target.value)}
                                  placeholder="Descripción (opcional)"
                                  className="w-full text-xs border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                                />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'summary' && meeting.summary_data?.main_points && (
                <div className="space-y-6">
                  {/* Summary header with export button */}
                  <div className="flex items-center justify-between pb-4 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">Resumen de la Reunión</h2>
                    <button
                      onClick={handleExportSummary}
                      className="text-gray-500 hover:text-gray-700 transition-colors flex items-center space-x-1 px-3 py-1 rounded hover:bg-gray-50"
                      title="Exportar Resumen"
                    >
                      <Download className="h-4 w-4" />
                      <span className="text-sm">Exportar</span>
                    </button>
                  </div>

                  <div className="space-y-4">
                  {meeting.summary_data.main_points.map((point, idx) => {
                    // Build a stable composite key for toggling to avoid collisions when IDs repeat
                    const compositeId = `${point.id}::${point.time || ''}::${idx}`
                    const isExpanded = expandedPoints.has(compositeId)
                    const detail = meeting.summary_data?.detailed_summary[point.id]

                    return (
                      <div key={compositeId} className="flex items-start space-x-3">
                        {/* Simple dot */}
                        <div className="w-2 h-2 rounded-full bg-primary-500 mt-1.5 flex-shrink-0"></div>

                        <div className="flex-1">
                          <div className="flex items-start justify-between gap-4">
                            <button
                              onClick={() => togglePoint(compositeId)}
                              className="flex-1 text-left hover:opacity-80 transition-opacity"
                            >
                              <h3 className="text-sm font-medium text-gray-900">{point.title}</h3>
                            </button>
                            <div className="flex items-center space-x-2 flex-shrink-0">
                              {point.time && (
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    seekToTime(point.time!)
                                  }}
                                  className="text-xs text-primary-600 hover:text-primary-700 font-medium cursor-pointer"
                                >
                                  {point.time}
                                </span>
                              )}
                              <button
                                onClick={() => togglePoint(compositeId)}
                                className="hover:opacity-80 transition-opacity"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-gray-400" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-gray-400" />
                                )}
                              </button>
                            </div>
                          </div>

                          {/* Always-visible minimal timestamp chips (first 2) */}
                          {detail && (detail.start_time || (detail.key_timestamps && detail.key_timestamps.length > 0)) && (
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              {detail.start_time && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); seekToTime(detail.start_time!) }}
                                  className="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-700 hover:bg-primary-100"
                                >
                                  {detail.start_time}
                                </button>
                              )}
                              {(() => {
                                const all = (detail.key_timestamps || []).filter(kt => kt && kt.time)
                                const max = Math.max(0, 2 - (detail.start_time ? 1 : 0))
                                const shown = all.slice(0, max)
                                const remaining = all.length - shown.length
                                return (
                                  <>
                                    {shown.map((kt, i) => (
                                      <button
                                        key={`${point.id}-prets-${i}-${kt.time}`}
                                        onClick={(e) => { e.stopPropagation(); seekToTime(kt.time!) }}
                                        className="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-700 hover:bg-primary-100"
                                        title={kt.description}
                                      >
                                        {kt.time}
                                      </button>
                                    ))}
                                    {remaining > 0 && (
                                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">+{remaining}</span>
                                    )}
                                  </>
                                )
                              })()}
                            </div>
                          )}

                          {isExpanded && detail && (
                            <>
                              {(detail.start_time || (detail.key_timestamps && detail.key_timestamps.length > 0)) && (
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                  {detail.start_time && (
                                    <button
                                      onClick={(e) => { e.stopPropagation(); seekToTime(detail.start_time!) }}
                                      className="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-[11px] font-medium text-primary-700 hover:bg-primary-100"
                                    >
                                      {detail.start_time}
                                    </button>
                                  )}
                                  {(detail.key_timestamps || []).filter(kt => kt && kt.time).map((kt, i) => (
                                    <button
                                      key={`${point.id}-ts-${i}-${kt.time}`}
                                      onClick={(e) => { e.stopPropagation(); seekToTime(kt.time!) }}
                                      className="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-[11px] font-medium text-primary-700 hover:bg-primary-100"
                                      title={kt.description}
                                    >
                                      {kt.time}
                                    </button>
                                  ))}
                                </div>
                              )}
                              <div className="mt-2 text-sm text-gray-700">
                                <MarkdownContent content={detail.content} />
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Right Sidebar - Transcript - Hidden on mobile */}
        {meeting.full_transcript_data?.segments && meeting.full_transcript_data.segments.length > 0 && (
          <div className={`hidden md:block border-l border-gray-200 bg-white transition-all duration-300 ${showTranscript ? 'w-96' : 'w-12'}`}>
            {showTranscript ? (
              <div className="h-full flex flex-col">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-900">Transcripción</h3>
                  <button
                    onClick={() => setShowTranscript(false)}
                    className="text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>

              <div className="p-4 border-b border-gray-200">
                  <div className="relative mb-3">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Buscar en transcripción..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                  <button
                    onClick={copyTranscript}
                    className="w-full bg-gray-100 text-gray-700 px-3 py-2 rounded-lg hover:bg-gray-200 transition-colors flex items-center justify-center space-x-2 text-sm"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    <span>{copied ? 'Copiado' : 'Copiar'}</span>
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {(searchTerm ? filteredSegments : meeting.full_transcript_data.segments).map((segment) => (
                    <div key={segment.id} className="space-y-1">
                      <button
                        onClick={() => seekToTime(formatDuration(segment.start))}
                        className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                      >
                        {formatDuration(segment.start)}
                      </button>
                      <p className="text-sm text-gray-700 leading-relaxed">
                        {searchTerm ? (
                          <span
                            dangerouslySetInnerHTML={{
                              __html: segment.text.replace(
                                new RegExp(searchTerm, 'gi'),
                                (match) => `<mark class="bg-yellow-200">${match}</mark>`
                              )
                            }}
                          />
                        ) : (
                          segment.text
                        )}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowTranscript(true)}
                className="h-full w-full flex items-center justify-center hover:bg-gray-50 transition-colors"
              >
                <ChevronLeft className="h-5 w-5 text-gray-400" />
              </button>
            )}
          </div>
        )}
        </div>

        {/* Audio Player Fixed at Bottom */}
        {meeting.audio_filename && (
          <div className="border-t border-gray-200 p-2 sm:p-4 bg-white">
            <WaveformPlayer
              audioUrl={audioService.getAudioUrl(meeting.audio_filename)}
              seekTime={seekTime}
            />
          </div>
        )}
      </div>

      {/* Transcript Modal - Mobile Only */}
      {showTranscriptModal && meeting.full_transcript_data?.segments && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 md:hidden">
          <div className="bg-white rounded-lg w-full h-full flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <h3 className="text-base font-semibold text-gray-900">Transcripción</h3>
              <button
                onClick={() => setShowTranscriptModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 border-b border-gray-200">
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar en transcripción..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
              <button
                onClick={copyTranscript}
                className="w-full bg-gray-100 text-gray-700 px-3 py-2 rounded-lg hover:bg-gray-200 transition-colors flex items-center justify-center space-x-2 text-sm"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                <span>{copied ? 'Copiado' : 'Copiar'}</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {(searchTerm ? filteredSegments : meeting.full_transcript_data.segments).map((segment) => (
                <div key={segment.id} className="space-y-1">
                  <button
                    onClick={() => {
                      seekToTime(formatDuration(segment.start))
                      setShowTranscriptModal(false)
                    }}
                    className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                  >
                    {formatDuration(segment.start)}
                  </button>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {searchTerm ? (
                      <span
                        dangerouslySetInnerHTML={{
                          __html: segment.text.replace(
                            new RegExp(searchTerm, 'gi'),
                            (match) => `<mark class="bg-yellow-200">${match}</mark>`
                          )
                        }}
                      />
                    ) : (
                      segment.text
                    )}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Email Modal */}
      {showEmailModal && (
        <div className="fixed inset-0 backdrop-blur-[2px] backdrop-brightness-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-4 sm:p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto shadow-2xl border border-gray-300">
            <h3 className="text-lg font-semibold mb-4">Confirmar Destinatarios del Email</h3>
            <p className="text-gray-600 mb-4 text-sm">
              Revise y confirme los destinatarios que recibirán el resumen de la reunión.
            </p>

            {/* Recipients List */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-gray-900">Destinatarios</h4>
                <button
                  onClick={addEmailRecipient}
                  className="text-primary-600 hover:text-primary-700 text-sm flex items-center space-x-1"
                >
                  <Plus className="h-4 w-4" />
                  <span>Agregar</span>
                </button>
              </div>

              <div className="space-y-3">
                {emailRecipients.length === 0 && (
                  <p className="text-gray-500 text-sm italic">
                    No hay destinatarios. Agregue al menos uno para enviar el resumen.
                  </p>
                )}
                {emailRecipients.map((recipient, index) => (
                  <div key={index} className="flex items-center space-x-2 p-3 border border-gray-300 rounded-lg">
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        value={recipient.name}
                        onChange={(e) => updateEmailRecipient(index, 'name', e.target.value)}
                        placeholder="Nombre"
                        className="text-sm border border-gray-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                      <input
                        type="email"
                        value={recipient.email || ''}
                        onChange={(e) => updateEmailRecipient(index, 'email', e.target.value)}
                        placeholder="Email"
                        className="text-sm border border-gray-300 rounded px-2 py-1 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                    <button
                      onClick={() => removeEmailRecipient(index)}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t border-gray-200">
              <button
                onClick={() => {
                  setShowEmailModal(false)
                  setEmailRecipients([])
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleSendEmail}
                disabled={sendingEmail || emailRecipients.length === 0 || emailRecipients.some(r => !r.email)}
                className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
              >
                {sendingEmail ? 'Enviando...' : 'Enviar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
