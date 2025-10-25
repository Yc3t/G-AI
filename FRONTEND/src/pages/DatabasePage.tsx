import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Calendar,
  Search,
  Filter,
  MoreVertical,
  Trash2,
  Edit,
  ExternalLink,
  Users,
  FileText,
  Home
} from 'lucide-react'
import { meetingApi } from '../services/api'
import type { MeetingListItem } from '../types'
import { formatDuration } from '../services/audioUtils'

export const DatabasePage: React.FC = () => {
  const navigate = useNavigate()
  const [meetings, setMeetings] = useState<MeetingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [showDeleteModal, setShowDeleteModal] = useState<string | null>(null)
  const [showRenameModal, setShowRenameModal] = useState<string | null>(null)
  const [newTitle, setNewTitle] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const ITEMS_PER_PAGE = 50
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const [extraInfo, setExtraInfo] = useState<Record<string, { participants: number; duration: number }>>({})

  useEffect(() => {
    loadMeetings()
  }, [selectedDate])

  // Close contextual menus on any document click
  useEffect(() => {
    const onDocClick = () => setOpenMenuId(null)
    window.addEventListener('click', onDocClick)
    return () => window.removeEventListener('click', onDocClick)
  }, [])

  // Close menu on scroll/touch/resize to avoid scroll interception on desktop/mobile
  useEffect(() => {
    const close = () => setOpenMenuId(null)
    window.addEventListener('scroll', close, { passive: true })
    window.addEventListener('touchstart', close, { passive: true })
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close)
      window.removeEventListener('touchstart', close)
      window.removeEventListener('resize', close)
    }
  }, [])

  const loadMeetings = async () => {
    try {
      setLoading(true)
      const data = await meetingApi.getMeetings(selectedDate || undefined)
      setMeetings(data)
      setError(null)
    } catch (error) {
      console.error('Failed to load meetings:', error)
      setError('Error al cargar las reuniones')
    } finally {
      setLoading(false)
    }
  }

  const filteredMeetings = meetings.filter(meeting =>
    meeting.titulo.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchTerm, selectedDate])

  // Pagination calculations
  const totalPages = Math.ceil(filteredMeetings.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const paginatedMeetings = filteredMeetings.slice(startIndex, endIndex)

  // Fetch extra info (participants count, duration) for visible meetings as fallback
  useEffect(() => {
    let cancelled = false
    const loadExtras = async () => {
      try {
        const missing = paginatedMeetings
          .filter(m => !extraInfo[m.id])
          .map(m => m.id)
        if (missing.length === 0) return
        const results = await Promise.allSettled(missing.map(id => meetingApi.getMeeting(id)))
        if (cancelled) return
        setExtraInfo(prev => {
          const next = { ...prev }
          results.forEach((res, idx) => {
            const id = missing[idx]
            if (res.status === 'fulfilled' && res.value) {
              try {
                const data: any = res.value
                const participants = Array.isArray(data.participants) ? data.participants.filter((p: any) => p && (p.name || String(p).trim())).length : 0
                const duration = (data.minutes && data.minutes.metadata && typeof data.minutes.metadata.duration_seconds === 'number') ? data.minutes.metadata.duration_seconds : 0
                next[id] = { participants, duration }
              } catch {}
            }
          })
          return next
        })
      } catch {}
    }
    void loadExtras()
    return () => { cancelled = true }
  }, [paginatedMeetings])

  const handleDeleteMeeting = async (id: string) => {
    setDeleting(true)
    try {
      await meetingApi.deleteMeeting(id)
      setMeetings(prev => prev.filter(m => m.id !== id))
      setShowDeleteModal(null)
    } catch (error) {
      console.error('Failed to delete meeting:', error)
      setError('Error al eliminar la reunión')
    } finally {
      setDeleting(false)
    }
  }

  const handleRenameMeeting = async (id: string) => {
    if (!newTitle.trim()) return
    
    setRenaming(true)
    try {
      await meetingApi.renameMeeting(id, newTitle.trim())
      setMeetings(prev => prev.map(m => 
        m.id === id ? { ...m, titulo: newTitle.trim() } : m
      ))
      setShowRenameModal(null)
      setNewTitle('')
    } catch (error) {
      console.error('Failed to rename meeting:', error)
      setError('Error al renombrar la reunión')
    } finally {
      setRenaming(false)
    }
  }

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return dateString
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <h3 className="text-lg font-semibold text-gray-900">Cargando reuniones...</h3>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white overflow-x-hidden">
      {/* Header Navbar */}
      <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
            aria-label="Ir a inicio"
          >
            <Home className="h-5 w-5" />
          </button>
          <img
            src="/frumecar.jpg"
            alt="Frumecar"
            className="h-10 w-10 rounded-xl object-contain shadow-sm ring-1 ring-slate-200"
          />
          <button
            onClick={() => navigate('/table')}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
            aria-label="Tabla de contactos"
          >
            <Users className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="px-4 sm:px-6 py-6 space-y-6">
        {/* Page Title */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Base de Datos de Reuniones</h1>  
          </div>
          <div className="text-sm text-gray-500">
            {paginatedMeetings.length} de {filteredMeetings.length} reuniones
          </div>
        </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar reuniones..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="pl-10 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          
          <button
            onClick={() => {
              setSearchTerm('')
              setSelectedDate('')
            }}
            className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors flex items-center justify-center space-x-2"
          >
            <Filter className="h-4 w-4" />
            <span>Limpiar Filtros</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg">
          <p>{error}</p>
        </div>
      )}

      {/* Meetings List */}
      {filteredMeetings.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {searchTerm || selectedDate ? 'No se encontraron reuniones' : 'No hay reuniones'}
          </h3>
          <p className="text-gray-600">
            {searchTerm || selectedDate 
              ? 'Intenta ajustar los filtros de búsqueda'
              : 'Crea tu primera reunión para empezar'
            }
          </p>
        </div>
      ) : (
        <>
        <div className="grid grid-cols-1 gap-3 sm:gap-4 w-full">
          {paginatedMeetings.map((meeting) => {
            const m: any = meeting as any
            const participantsCount: number | null = (() => {
              try {
                if (typeof m.participants_count === 'number') return m.participants_count
                if (Array.isArray(m.participants)) return m.participants.filter((p: any) => p && (p.name || String(p).trim())).length
                if (Array.isArray(m.participantes)) return m.participantes.filter((n: any) => String(n || '').trim()).length
                if (typeof m.resumen === 'string' && m.resumen.trim()) {
                  const parsed = JSON.parse(m.resumen)
                  const md = parsed && parsed.metadata
                  if (md && Array.isArray(md.participants)) return md.participants.filter((n: any) => String(n || '').trim()).length
                }
              } catch {}
              const fallback = extraInfo[meeting.id]?.participants
              return typeof fallback === 'number' ? fallback : null
            })()
            const durationSeconds: number | null = (() => {
              try {
                if (typeof m.duration_seconds === 'number' && m.duration_seconds > 0) return m.duration_seconds
                const text: string = typeof m.transcripcion === 'string' ? m.transcripcion : ''
                if (text) {
                  const lines = text.split('\n').map((ln: string) => ln.trim()).filter(Boolean)
                  for (let i = lines.length - 1; i >= 0; i--) {
                    const match = lines[i].match(/^\[(\d{2}):(\d{2})\]/)
                    if (match) {
                      const mins = parseInt(match[1], 10)
                      const secs = parseInt(match[2], 10)
                      return mins * 60 + secs
                    }
                  }
                }
              } catch {}
              const fallback = extraInfo[meeting.id]?.duration
              return typeof fallback === 'number' ? fallback : null
            })()

            return (
            <div
              key={meeting.id}
              className="w-full max-w-full bg-white rounded-lg shadow-sm border hover:shadow-md transition-all duration-200 overflow-visible"
            >
              <div className="p-3 sm:p-6">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-base sm:text-lg font-semibold text-gray-900 truncate">
                        {meeting.titulo}
                      </h3>
                    </div>

                    <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-xs sm:text-sm text-gray-600">
                      <div className="flex items-center space-x-1">
                        <Calendar className="h-3 w-3 sm:h-4 sm:w-4" />
                        <span>{formatDate(meeting.fecha_de_subida)}</span>
                      </div>
                      {participantsCount !== null && (
                        <div className="flex items-center space-x-1">
                          <Users className="h-3 w-3 sm:h-4 sm:w-4" />
                          <span>{participantsCount}</span>
                        </div>
                      )}
                      {durationSeconds !== null && durationSeconds > 0 && (
                        <div className="flex items-center space-x-1">
                          <FileText className="h-3 w-3 sm:h-4 sm:w-4" />
                          <span>{formatDuration(durationSeconds)}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 self-end sm:self-start w-full sm:w-auto justify-end sm:justify-start">
                    <button
                      onClick={() => navigate(`/meeting/${meeting.id}`)}
                      className="bg-primary-600 text-white px-3 py-2 rounded-lg hover:bg-primary-700 transition-colors flex items-center space-x-1 text-sm"
                    >
                      <ExternalLink className="h-3 w-3 sm:h-4 sm:w-4" />
                      <span>Ver</span>
                    </button>

                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setOpenMenuId(prev => prev === meeting.id ? null : meeting.id)
                        }}
                        className="text-gray-500 hover:text-gray-700 p-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded-md"
                        aria-haspopup="menu"
                        aria-expanded={openMenuId === meeting.id}
                      >
                        <MoreVertical className="h-4 w-4" />
                      </button>
                      {openMenuId === meeting.id && (
                        <div
                          onClick={(e) => e.stopPropagation()}
                          className="absolute right-0 top-9 sm:top-8 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-30 min-w-[160px]"
                        >
                          <button
                            onClick={() => {
                              setShowRenameModal(meeting.id)
                              setNewTitle(meeting.titulo)
                              setOpenMenuId(null)
                            }}
                            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                          >
                            <Edit className="h-4 w-4" />
                            <span>Renombrar</span>
                          </button>
                          <button
                            onClick={() => {
                              setShowDeleteModal(meeting.id)
                              setOpenMenuId(null)
                            }}
                            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span>Eliminar</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            )
          })}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-6 px-4 py-3 bg-white border rounded-lg">
            <div className="text-xs sm:text-sm text-gray-700">
              Mostrando {startIndex + 1} - {Math.min(endIndex, filteredMeetings.length)} de {filteredMeetings.length} reuniones
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1.5 text-xs sm:text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Anterior
              </button>
              <div className="hidden sm:flex items-center gap-1">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => {
                  if (
                    page === 1 ||
                    page === totalPages ||
                    (page >= currentPage - 1 && page <= currentPage + 1)
                  ) {
                    return (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                          currentPage === page
                            ? 'bg-primary-600 text-white'
                            : 'border hover:bg-gray-50'
                        }`}
                      >
                        {page}
                      </button>
                    )
                  } else if (page === currentPage - 2 || page === currentPage + 2) {
                    return <span key={page} className="px-2">...</span>
                  }
                  return null
                })}
              </div>
              <div className="sm:hidden text-xs text-gray-700">
                Página {currentPage} de {totalPages}
              </div>
              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1.5 text-xs sm:text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Siguiente
              </button>
            </div>
          </div>
        )}
        </>
      )}

      {/* Delete Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 backdrop-blur-sm bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Confirmar Eliminación</h3>
            <p className="text-gray-600 mb-6">
              ¿Estás seguro de que quieres eliminar esta reunión? Esta acción no se puede deshacer.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowDeleteModal(null)}
                disabled={deleting}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDeleteMeeting(showDeleteModal)}
                disabled={deleting}
                className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? 'Eliminando...' : 'Eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {showRenameModal && (
        <div className="fixed inset-0 backdrop-blur-sm bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Renombrar Reunión</h3>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent mb-6"
              placeholder="Nuevo título"
              onKeyPress={(e) => e.key === 'Enter' && handleRenameMeeting(showRenameModal)}
            />
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowRenameModal(null)
                  setNewTitle('')
                }}
                disabled={renaming}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleRenameMeeting(showRenameModal)}
                disabled={renaming || !newTitle.trim()}
                className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
              >
                {renaming ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}
