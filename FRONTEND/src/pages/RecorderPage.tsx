import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MicOff,
  FileUp,
  Download,
  Trash2,
  Check,
  Database
} from 'lucide-react'
import { AudioRecorder } from '../services/audioUtils'
import { meetingApi } from '../services/api'
import type { Participant, RecorderState } from '../types'

export const RecorderPage: React.FC = () => {
  const navigate = useNavigate()
  const [recorderState, setRecorderState] = useState<RecorderState>({
    isRecording: false,
    isPreRecording: false,
    isPaused: false,
    recordingTime: 0,
    audioLevel: 0,
    hasPermission: false
  })
  
  const [participants, setParticipants] = useState<Participant[]>([])
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [shouldAutoUpload, setShouldAutoUpload] = useState(false)
  const shouldAutoUploadRef = useRef(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [waveformPoints, setWaveformPoints] = useState<number[]>(() => Array.from({ length: 100 }, () => 12))
  const [rightWaveformPoints, setRightWaveformPoints] = useState<number[]>(() => Array.from({ length: 50 }, () => 8))
  const waveformIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const rightWaveformIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const audioLevelRef = useRef(0)
  const lastWaveformValueRef = useRef(12)
  const preRecordingAudioContextRef = useRef<AudioContext | null>(null)
  const preRecordingAnalyserRef = useRef<AnalyserNode | null>(null)
  const preRecordingAnimationFrameRef = useRef<number | null>(null)

  const formatLocalTime = (date: Date) =>
    date.toLocaleTimeString('es-ES', { hour: 'numeric', minute: '2-digit', hour12: true })

  const [currentClockLabel, setCurrentClockLabel] = useState(() => formatLocalTime(new Date()))

  // Voice-capture states (continuous until meeting start)
  const [hasCompletedNamesClip, setHasCompletedNamesClip] = useState(false)
  const [namesClipBlob, setNamesClipBlob] = useState<Blob | null>(null)
  const [isLoadingParticipants, setIsLoadingParticipants] = useState(false)
  const namesMediaRecorderRef = useRef<MediaRecorder | null>(null)
  const namesStreamRef = useRef<MediaStream | null>(null)
  const namesChunksRef = useRef<Blob[]>([])

  const audioRecorderRef = useRef<AudioRecorder | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    // Initialize audio recorder
    audioRecorderRef.current = new AudioRecorder({
      onAudioLevelChange: (level) => {
        setRecorderState(prev => ({ ...prev, audioLevel: level }))
      },
      onDataAvailable: (blob) => {
        setRecordedBlob(blob)
        console.log('Recording completed, blob size:', blob.size)
        if (shouldAutoUploadRef.current) {
          setShouldAutoUpload(false)
          shouldAutoUploadRef.current = false
          // Trigger upload immediately
          void handleSaveRecording(blob)
        }
      },
      onError: (error) => {
        setError(`Error de grabación: ${error.message}`)
        console.error('Recording error:', error)
      }
    })

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
      if (audioRecorderRef.current) {
        audioRecorderRef.current.stopRecording()
      }
      stopPreRecordingAudioMonitoring()
    }
  }, [])

  // Keep ref in sync
  useEffect(() => {
    shouldAutoUploadRef.current = shouldAutoUpload
  }, [shouldAutoUpload])

  useEffect(() => {
    audioLevelRef.current = recorderState.audioLevel
  }, [recorderState.audioLevel])

  useEffect(() => {
    const shouldAnimate = recorderState.isRecording || recorderState.isPreRecording

    if (shouldAnimate && !waveformIntervalRef.current) {
      waveformIntervalRef.current = window.setInterval(() => {
        setWaveformPoints(prev => {
          const next = prev.slice(1)
          const baseLevel = Math.min(1, Math.max(0, audioLevelRef.current))
          const target = baseLevel * 100 + 10
          const jitter = (Math.random() - 0.5) * 15
          const blended = lastWaveformValueRef.current * 0.58 + (target + jitter) * 0.42
          const clamped = Math.max(6, Math.min(60, blended))
          lastWaveformValueRef.current = clamped
          next.push(clamped)
          return next
        })
      }, 80)
    }

    if (!shouldAnimate) {
      if (waveformIntervalRef.current) {
        window.clearInterval(waveformIntervalRef.current)
        waveformIntervalRef.current = null
      }
      lastWaveformValueRef.current = 12
      setWaveformPoints(Array.from({ length: 100 }, () => 12))
    }

    return () => {
      if (waveformIntervalRef.current) {
        window.clearInterval(waveformIntervalRef.current)
        waveformIntervalRef.current = null
      }
    }
  }, [recorderState.isRecording, recorderState.isPreRecording])

  useEffect(() => {
    const shouldAnimate = recorderState.isRecording || recorderState.isPreRecording

    if (shouldAnimate && !rightWaveformIntervalRef.current) {
      rightWaveformIntervalRef.current = window.setInterval(() => {
        setRightWaveformPoints(prev => {
          const next = prev.slice(1)
          next.push(8 + Math.random() * 2)
          return next
        })
      }, 80)
    }

    if (!shouldAnimate) {
      if (rightWaveformIntervalRef.current) {
        window.clearInterval(rightWaveformIntervalRef.current)
        rightWaveformIntervalRef.current = null
      }
      setRightWaveformPoints(Array.from({ length: 50 }, () => 8))
    }

    return () => {
      if (rightWaveformIntervalRef.current) {
        window.clearInterval(rightWaveformIntervalRef.current)
        rightWaveformIntervalRef.current = null
      }
    }
  }, [recorderState.isRecording, recorderState.isPreRecording])

  useEffect(() => {
    setCurrentClockLabel(formatLocalTime(new Date()))
    const intervalId = window.setInterval(() => {
      setCurrentClockLabel(formatLocalTime(new Date()))
    }, 60000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [])

  const checkMicrophonePermission = async () => {
    try {
      // Prefer direct call to avoid race with ref initialization
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(t => t.stop())
      setRecorderState(prev => ({ ...prev, hasPermission: true }))
      setError(null)
    } catch (e) {
      const err = e as { name?: string }
      let message = 'Se requiere acceso al micrófono para grabar.'
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        message = 'Permiso al micrófono denegado. Habilítalo en los ajustes del sitio.'
      } else if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') {
        message = 'No se encontró ningún micrófono en el dispositivo.'
      } else if (err?.name === 'NotReadableError') {
        message = 'El micrófono está en uso por otra aplicación.'
      }
      setRecorderState(prev => ({ ...prev, hasPermission: false }))
      setError(message)
    }
  }

  const startTimer = () => {
    timerRef.current = setInterval(() => {
      setRecorderState(prev => ({ 
        ...prev, 
        recordingTime: prev.recordingTime + 1 
      }))
    }, 1000)
  }

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const startPreRecordingAudioMonitoring = (stream: MediaStream) => {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      const analyser = audioContext.createAnalyser()
      const microphone = audioContext.createMediaStreamSource(stream)

      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8
      const dataArray = new Uint8Array(analyser.frequencyBinCount)

      microphone.connect(analyser)

      preRecordingAudioContextRef.current = audioContext
      preRecordingAnalyserRef.current = analyser

      const updateLevel = () => {
        if (!preRecordingAnalyserRef.current) return

        preRecordingAnalyserRef.current.getByteFrequencyData(dataArray)

        let sum = 0
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i]
        }

        const average = sum / dataArray.length
        const normalizedLevel = Math.min(average / 128, 1)

        setRecorderState(prev => ({ ...prev, audioLevel: normalizedLevel }))
        preRecordingAnimationFrameRef.current = requestAnimationFrame(updateLevel)
      }

      updateLevel()
    } catch (e) {
      console.error('Failed to start audio monitoring', e)
    }
  }

  const stopPreRecordingAudioMonitoring = () => {
    if (preRecordingAnimationFrameRef.current) {
      cancelAnimationFrame(preRecordingAnimationFrameRef.current)
      preRecordingAnimationFrameRef.current = null
    }
    if (preRecordingAudioContextRef.current) {
      preRecordingAudioContextRef.current.close()
      preRecordingAudioContextRef.current = null
    }
    preRecordingAnalyserRef.current = null
    setRecorderState(prev => ({ ...prev, audioLevel: 0 }))
  }

  const handleStartRecording = async () => {
    if (!recorderState.hasPermission) {
      await checkMicrophonePermission()
      return
    }
    // If no participants yet, offer inline pre-recording state first
    if (participants.length === 0 && !recorderState.isPreRecording) {
      setRecorderState(prev => ({ ...prev, isPreRecording: true }))
      // start continuous names mic capture
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
        })
        const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
        namesChunksRef.current = []
        mr.ondataavailable = (e) => { if (e.data.size > 0) namesChunksRef.current.push(e.data) }
        mr.onstop = () => {
          const blob = new Blob(namesChunksRef.current, { type: mr.mimeType })
          setNamesClipBlob(blob)
          namesStreamRef.current?.getTracks().forEach(t => t.stop())
          namesMediaRecorderRef.current = null
          namesStreamRef.current = null
        }
        namesMediaRecorderRef.current = mr
        namesStreamRef.current = stream
        mr.start() // no fixed 6s; will stop when starting the meeting

        // Start audio level monitoring for waveform
        startPreRecordingAudioMonitoring(stream)
      } catch (e) {
        console.error('No se pudo iniciar la captura de nombres', e)
      }
      return
    }
    await beginMainRecording()
  }

  const beginMainRecording = async () => {
    try {
      if (audioRecorderRef.current) {

        // Capture the names clip blob before starting recording
        let blobToSend: Blob | null = null
        if (recorderState.isPreRecording) {
          // Stop pre-recording audio monitoring
          stopPreRecordingAudioMonitoring()

          const mr = namesMediaRecorderRef.current
          if (mr && mr.state !== 'inactive') {
            // Wait for final dataavailable/stop to ensure full blob
            blobToSend = await new Promise<Blob | null>((resolve) => {
              const handleStop = () => {
                try {
                  const finalBlob = new Blob(namesChunksRef.current, { type: mr.mimeType || 'audio/webm' })
                  setNamesClipBlob(finalBlob)
                  namesStreamRef.current?.getTracks().forEach(t => t.stop())
                  namesMediaRecorderRef.current = null
                  namesStreamRef.current = null
                  resolve(finalBlob)
                } catch {
                  resolve(null)
                }
              }
              mr.addEventListener('stop', handleStop, { once: true })
              try { mr.stop() } catch { resolve(null) }
            })
          } else {
            blobToSend = namesClipBlob || (namesChunksRef.current.length ? new Blob(namesChunksRef.current, { type: 'audio/webm' }) : null)
          }
        }

        // Start recording immediately (don't wait for name extraction)
        await audioRecorderRef.current.startRecording()
        setRecorderState(prev => ({
          ...prev,
          isRecording: true,
          isPaused: false,
          isPreRecording: false,
          recordingTime: 0
        }))
        setRecordedBlob(null)
        setError(null)
        setHasCompletedNamesClip(true)
        startTimer()

        // Process names in the background (non-blocking)
        if (blobToSend && blobToSend.size > 0) {
          setIsLoadingParticipants(true)
          meetingApi.identifySpeakersFromClip(blobToSend)
            .then((resp) => {
              const speakerNames = Array.isArray(resp.speakers) ? resp.speakers : []
              const cleaned = speakerNames.map(s => ({ name: String(s).trim() })).filter(p => p.name)
              if (cleaned.length > 0) {
                setParticipants(cleaned)
              }
              setIsLoadingParticipants(false)
            })
            .catch((e) => {
              console.error('Identificación de nombres falló - posible problema de backend:', e)
              setIsLoadingParticipants(false)
              // Continue with empty participants if name detection fails
            })
        }
      }
    } catch (error) {
      setError('No se pudo iniciar la grabación. Verifica los permisos del micrófono.')
      console.error('Failed to start recording:', error)
    }
  }

  const handleStopRecording = () => {
    if (audioRecorderRef.current) {
      audioRecorderRef.current.stopRecording()
      setRecorderState(prev => ({ 
        ...prev, 
        isRecording: false,
        isPaused: false,
        audioLevel: 0
      }))
      stopTimer()
    }
  }

  const handleDiscardRecording = () => {
    setRecordedBlob(null)
    setRecorderState(prev => ({ 
      ...prev, 
      recordingTime: 0
    }))
  }

  const handleSaveRecording = async (blobOverride?: Blob) => {
    const blob = blobOverride ?? recordedBlob
    if (!blob) return

    setIsUploading(true)
    setError(null)

    try {
      // Upload the recorded audio with participants - backend will create meeting if needed
      const result = await meetingApi.uploadRecordedAudio(null, blob, participants)
      const meetingId = result.reunion_id
      
      // Navigate to the meeting analysis page
      navigate(`/meeting/${meetingId}`)
    } catch (error) {
      console.error('Failed to save recording:', error)
      setError('Error al guardar la grabación. Por favor, inténtalo de nuevo.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleFinishRecording = () => {
    setShouldAutoUpload(true)
    shouldAutoUploadRef.current = true
    handleStopRecording()
  }

  // --- Upload audio directly ---
  const handleUploadAudio = async (fileOverride?: File) => {
    const fileToUpload = fileOverride ?? uploadFile
    if (!fileToUpload) return

    setIsUploading(true)
    setError(null)
    try {
      const result = await meetingApi.uploadAndProcessDirectly(fileToUpload)
      navigate(`/meeting/${result.reunion_id}`)
    } catch (err) {
      console.error('Upload failed:', err)
      setError('Error al subir el audio. Int�ntalo de nuevo.')
    } finally {
      setIsUploading(false)
      setUploadFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setUploadFile(file)
      setError(null)
      void handleUploadAudio(file)
    }
  }

  const handleFilePickerClick = () => {
    fileInputRef.current?.click()
  }

  const handleDatabaseNavigation = () => {
    navigate('/database')
  }

  // Drag & drop handlers removed with simplified upload UI

  // Names clip helpers removed - simplified inline UI

  const downloadRecording = () => {
    if (!recordedBlob) return
    
    const url = URL.createObjectURL(recordedBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = `grabacion-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.webm`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const isActiveRecording = recorderState.isRecording || recorderState.isPaused
  const hasStartedSession = recorderState.isPreRecording || isActiveRecording
  
  const statusLabel = recorderState.isRecording && !recorderState.isPaused
    ? 'Grabando'
    : recorderState.isPaused
    ? 'Pausado'
    : recorderState.isPreRecording
    ? 'Preparando'
    : 'Listo'
  const statusClasses = recorderState.isRecording && !recorderState.isPaused
    ? 'bg-red-100 text-red-800'
    : recorderState.isPaused
    ? 'bg-yellow-100 text-yellow-800'
    : recorderState.isPreRecording
    ? 'bg-blue-100 text-blue-800'
    : 'bg-gray-100 text-gray-600'
  const statusDot = recorderState.isRecording && !recorderState.isPaused
    ? 'bg-red-500'
    : recorderState.isPaused
    ? 'bg-yellow-500'
    : recorderState.isPreRecording
    ? 'bg-blue-500'
    : 'bg-gray-400'

  type PrimaryButtonState = 'idle' | 'preRecording' | 'recording' | 'paused' | 'ready'

  const primaryButtonState: PrimaryButtonState = !hasStartedSession
    ? 'idle'
    : recorderState.isPreRecording
    ? 'preRecording'
    : recorderState.isRecording && !recorderState.isPaused
    ? 'recording'
    : recorderState.isPaused
    ? 'paused'
    : 'ready'

  const primaryButtonAppearance = (() => {
    switch (primaryButtonState) {
      case 'preRecording':
        return {
          bg: 'bg-white ring-slate-200',
          inner: <div className="h-12 w-12 sm:h-14 sm:w-14 rounded-full bg-red-500 shadow-inner shadow-red-500/40" />,
          label: 'Comenzar grabacion'
        }
      case 'recording':
        return {
          bg: 'bg-white ring-red-500/60',
          inner: <div className="h-8 w-8 sm:h-10 sm:w-10 rounded-sm bg-red-500 shadow-inner shadow-red-500/40" />,
          label: 'Detener grabacion'
        }
      case 'paused':
        return {
          bg: 'bg-white ring-yellow-500/60',
          inner: (
            <div className="flex items-center justify-center gap-1">
              <span className="h-8 w-2 sm:h-10 sm:w-2 rounded-sm bg-yellow-500" />
              <span className="h-8 w-2 sm:h-10 sm:w-2 rounded-sm bg-yellow-500" />
            </div>
          ),
          label: 'Finalizar grabacion'
        }
      case 'ready':
        return {
          bg: 'bg-white ring-slate-200',
          inner: <div className="h-12 w-12 sm:h-14 sm:w-14 rounded-full bg-red-500 shadow-inner shadow-red-500/40" />,
          label: 'Iniciar nueva grabacion'
        }
      default:
        return {
          bg: 'bg-white ring-slate-200',
          inner: <div className="h-20 w-20 rounded-full bg-red-500 shadow-inner shadow-red-500/40" />,
          label: 'Comenzar grabacion'
        }
    }
  })()

  const isPrimaryButtonDisabled =
    (primaryButtonState === 'idle' && !recorderState.hasPermission) ||
    isUploading

  const handlePrimaryButtonClick = () => {
    if (!hasStartedSession) {
      void handleStartRecording()
      return
    }

    if (recorderState.isPreRecording) {
      void beginMainRecording()
      return
    }

    if (recorderState.isRecording || recorderState.isPaused) {
      handleFinishRecording()
      return
    }

    void handleStartRecording()
  }

  return (
    <div className="relative flex min-h-screen w-full overflow-hidden bg-white" style={{ minHeight: '100svh' }}>
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,.mp3,.wav,.m4a,.webm"
        className="hidden"
        onChange={onFileInputChange}
      />

      <div className="flex w-full flex-1 flex-col items-center min-h-0">
        <header className="w-full bg-white border-b border-gray-200 flex-shrink-0">
          <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4">
              {/* Database button - left */}
              <button
                onClick={handleDatabaseNavigation}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
                aria-label="Ver base de datos de reuniones"
              >
                <Database className="h-5 w-5" />
              </button>

              {/* Logo - center */}
              <img
                src="/frumecar.jpg"
                alt="Frumecar"
                className="h-10 w-10 rounded-xl object-contain shadow-sm ring-1 ring-slate-200"
              />

              {/* Upload button - right */}
              <button
                onClick={handleFilePickerClick}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
                aria-label="Subir grabacion"
              >
                <FileUp className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="w-full px-4 sm:px-6 mt-4">
            {error && (
              <div className="w-full max-w-md mx-auto rounded-2xl bg-red-50 px-3 py-2 text-red-700 shadow-sm ring-1 ring-red-200 flex-shrink-0" role="alert">
                <p className="font-medium text-sm">{error}</p>
              </div>
            )}

            {!recorderState.hasPermission && (
              <div className="w-full max-w-md mx-auto rounded-2xl bg-yellow-50 px-3 py-2 text-yellow-800 shadow-sm ring-1 ring-yellow-200 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <MicOff className="h-4 w-4" />
                  <span className="font-medium text-sm">Se requiere acceso al microfono para grabar</span>
                  <button
                    onClick={checkMicrophonePermission}
                    className="ml-auto inline-flex items-center rounded-full bg-yellow-600 px-2 py-1 text-xs text-white transition hover:bg-yellow-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-yellow-300 focus-visible:ring-offset-2"
                  >
                    Conceder permiso
                  </button>
                </div>
              </div>
            )}
          </div>

          <main className="flex w-full flex-1 flex-col items-center justify-center min-h-0 max-h-full">
            {recorderState.isPreRecording && (
              <div className="absolute top-20 sm:top-24 flex flex-col items-center gap-3 z-20">
                <div className="inline-flex items-center gap-2 rounded-full bg-green-50 px-4 py-2 ring-1 ring-green-200">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                  <p className="text-sm font-medium text-green-700">Di los nombres de los participantes</p>
                </div>
              </div>
            )}

            {!hasStartedSession ? null : (
            <div className={`absolute flex w-full max-w-md flex-col items-center gap-1 text-center flex-shrink-0 z-10 ${
              recorderState.isPreRecording ? 'top-36 sm:top-40' : 'top-20 sm:top-24'
            }`}>
              <p className="text-base font-medium text-slate-900">Nueva grabación</p>
              <p className="text-sm text-slate-500">{currentClockLabel}</p>
            </div>
            )}

            {!hasStartedSession ? null : (participants.length > 0 || isLoadingParticipants) && (
            <div className={`absolute flex w-full max-w-md flex-col items-center gap-2 text-center flex-shrink-0 z-10 px-4 ${
              recorderState.isPreRecording ? 'top-52 sm:top-56' : 'top-36 sm:top-40'
            }`}>
              <div className="w-full">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Participantes</p>
                {isLoadingParticipants && participants.length === 0 ? (
                  <p className="italic text-slate-400">Mostrando participantes...</p>
                ) : (
                  <div className="overflow-x-auto scrollbar-thin -mx-4 px-4">
                    <div className="flex gap-3 sm:justify-center" style={{ minWidth: 'min-content' }}>
                      {participants.map((participant, index) => (
                        <div
                          key={`${participant.name}-${index}`}
                          className="flex flex-col items-center gap-1 flex-shrink-0"
                          style={{ width: 'clamp(70px, 20vw, 100px)' }}
                        >
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-300 text-xs font-semibold text-slate-700">
                            {participant.name?.[0]?.toUpperCase() ?? '?'}
                          </div>
                          <span className="w-full truncate text-xs text-slate-600 text-center">
                            {participant.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
            )}

            {!hasStartedSession ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-6">
                <button
                  onClick={handlePrimaryButtonClick}
                  disabled={isPrimaryButtonDisabled}
                  aria-label={primaryButtonAppearance.label}
                  className={`grid h-32 w-32 place-items-center rounded-full shadow-lg transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-red-300 focus-visible:ring-offset-4 ${primaryButtonAppearance.bg} disabled:cursor-not-allowed disabled:opacity-40`}
                  style={{
                    border: '6px solid white',
                    boxShadow: '0 0 0 2px rgb(226 232 240)'
                  }}
                >
                  {primaryButtonAppearance.inner}
                  <span className="sr-only">{primaryButtonAppearance.label}</span>
                </button>
                <p className="max-w-sm text-center text-lg text-slate-700">Toca para comenzar a grabar tu reunion</p>
              </div>
            ) : (
              <div className="flex w-full flex-col items-center gap-6 flex-shrink pt-12 sm:pt-16">
                <div className="relative w-full max-w-2xl px-2 sm:px-4 flex-shrink-0" style={{ height: 'clamp(200px, 30vh, 320px)' }}>
                  {/* Playhead */}
                  <div className={`absolute left-1/2 top-0 z-10 h-full w-0.5 -translate-x-1/2 ${
                    recorderState.isPreRecording ? 'bg-green-500' : 'bg-blue-500'
                  }`}>
                    <div className={`absolute left-1/2 top-0 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${
                      recorderState.isPreRecording ? 'bg-green-500' : 'bg-blue-500'
                    }`} />
                    <div className={`absolute bottom-0 left-1/2 h-3 w-3 -translate-x-1/2 translate-y-1/2 rounded-full ${
                      recorderState.isPreRecording ? 'bg-green-500' : 'bg-blue-500'
                    }`} />
                  </div>

                  {/* Waveform */}
                  <div className="flex h-full items-center gap-px sm:gap-0.5">
                    {/* Left side - recorded audio (past) */}
                    <div className="flex h-full flex-1 items-center justify-end gap-px sm:gap-0.5">
                      {waveformPoints.slice(-50).map((value, index) => (
                        <div
                          key={`left-${index}`}
                          className={`w-0.5 sm:w-1 rounded-full transition-all duration-100 ${
                            recorderState.isPreRecording ? 'bg-green-500/40' : 'bg-blue-500/40'
                          }`}
                          style={{ height: `${value}%` }}
                        />
                      ))}
                    </div>

                    {/* Right side - future/silence (animated but flat) */}
                    <div className="flex h-full flex-1 items-center justify-start gap-px sm:gap-0.5">
                      {rightWaveformPoints.map((value, index) => (
                        <div
                          key={`right-${index}`}
                          className={`w-0.5 sm:w-1 rounded-full transition-all duration-100 ${
                            recorderState.isPreRecording ? 'bg-green-500/20' : 'bg-blue-500/20'
                          }`}
                          style={{ height: `${value}%` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {!recorderState.isPreRecording && (
                <div className="flex flex-col items-center gap-2 text-center flex-shrink-0">
                  <div
                    className="font-mono text-4xl sm:text-5xl font-light tracking-tight text-slate-900"
                    style={{ fontVariantNumeric: 'tabular-nums' }}
                  >
                    {Math.floor(recorderState.recordingTime / 3600).toString().padStart(2, '0')}:
                    {Math.floor((recorderState.recordingTime % 3600) / 60).toString().padStart(2, '0')}:
                    {(recorderState.recordingTime % 60).toString().padStart(2, '0')}
                  </div>
                </div>
                )}

                <button
                  onClick={handlePrimaryButtonClick}
                  disabled={isPrimaryButtonDisabled}
                  aria-label={primaryButtonAppearance.label}
                  className={`grid h-20 w-20 sm:h-24 sm:w-24 place-items-center rounded-full shadow-lg transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-red-300 focus-visible:ring-offset-2 flex-shrink-0 ${primaryButtonAppearance.bg} disabled:cursor-not-allowed disabled:opacity-50`}
                  style={{
                    border: '6px solid white',
                    boxShadow: '0 0 0 2px rgb(226 232 240)'
                  }}
                >
                  {primaryButtonAppearance.inner}
                  <span className="sr-only">{primaryButtonAppearance.label}</span>
                </button>
              </div>
            )}
          </main>

          {/* Processing overlay - centered full screen */}
          {isUploading && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/95 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-6 px-6">
                <div className="relative">
                  <div className="h-20 w-20 animate-spin rounded-full border-b-4 border-t-4 border-blue-500" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="h-12 w-12 rounded-full bg-blue-50" />
                  </div>
                </div>
                <div className="text-center">
                  <h3 className="mb-2 text-2xl font-semibold text-slate-900">Procesando reunión</h3>
                  <p className="text-slate-600">Analizando audio y generando transcripción...</p>
                </div>
              </div>
            </div>
          )}

          {/* Recording completed card - only show when not uploading */}
          {recordedBlob && !isUploading && (
            <div className="absolute bottom-0 left-0 right-0 w-full max-w-md mx-auto rounded-t-2xl bg-white/90 px-4 py-4 sm:px-6 sm:py-6 shadow-xl ring-1 ring-slate-200 backdrop-blur">
            <h3 className="mb-4 text-xl font-semibold text-slate-900">Grabacion completada</h3>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <button
                onClick={downloadRecording}
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-6 py-3 text-sm font-medium text-white transition hover:bg-black focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-300 focus-visible:ring-offset-2"
              >
                <Download className="h-5 w-5" />
                Descargar
              </button>
              <button
                onClick={handleDiscardRecording}
                className="inline-flex items-center gap-2 rounded-full bg-red-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-red-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-red-300 focus-visible:ring-offset-2"
              >
                <Trash2 className="h-5 w-5" />
                Descartar
              </button>
              <button
                onClick={() => handleSaveRecording()}
                className="inline-flex items-center gap-2 rounded-full bg-primary-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-300 focus-visible:ring-offset-2"
              >
                <Check className="h-5 w-5" />
                Guardar y analizar
              </button>
            </div>
            </div>
          )}
        </div>
      </div>
    )
  }
