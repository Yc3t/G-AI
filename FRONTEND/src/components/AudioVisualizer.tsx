import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { AudioVisualizerProps } from '../types'
import WaveSurfer from 'wavesurfer.js'
// Record plugin includes live microphone rendering
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - types are shipped but path-based import confuses TS occasionally
import RecordPlugin from 'wavesurfer.js/dist/plugins/record.esm.js'

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  isRecording,
  isPreRecording,
  audioLevel,
  duration,
  hasCompletedNamesClip,
  namesClipBlob,
  showHeader = true
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const waveRef = useRef<WaveSurfer | null>(null)
  const recordRef = useRef<any | null>(null)
  const overlayWaveRef = useRef<WaveSurfer | null>(null)
  const overlayContainerRef = useRef<HTMLDivElement | null>(null)
  const [isQuiet, setIsQuiet] = useState(false)
  const lastLoudRef = useRef<number>(Date.now())
  // timeline + layout
  const WINDOW_SECONDS = 20
  const [pxPerSecond, setPxPerSecond] = useState<number>(6)
  const [displayTime, setDisplayTime] = useState<number>(duration)
  const baseTimeRef = useRef<number>(duration)
  const baseTimestampRef = useRef<number>(typeof performance !== 'undefined' ? performance.now() : Date.now())
  const isActive = isRecording || isPreRecording

  // Smooth amplitude for potential future UI (kept minimal)
  useMemo(() => {
    const clamped = Math.max(0, Math.min(1, audioLevel))
    return 1 - Math.pow(1 - clamped, 2)
  }, [audioLevel])

  // Detect silence and gently fade the waveform when quiet
  useEffect(() => {
    const threshold = 0.06 // tuned for our normalized audioLevel
    if (audioLevel > threshold) {
      lastLoudRef.current = Date.now()
    }
    const silentForMs = Date.now() - lastLoudRef.current
    setIsQuiet(silentForMs > 450)
  }, [audioLevel])

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  // Init WaveSurfer once
  useEffect(() => {
    if (!containerRef.current) return
    const ws = WaveSurfer.create({
      container: containerRef.current,
      height: 110,
      waveColor: isPreRecording ? 'rgba(16,185,129,0.55)' : 'rgba(99,102,241,0.55)',
      progressColor: isPreRecording ? 'rgba(5,150,105,0.85)' : 'rgba(236,72,153,0.85)',
      cursorWidth: 0,
      interact: false,
      normalize: false
    })
    const record = ws.registerPlugin(RecordPlugin.create({
      scrollingWaveform: true,
      scrollingWaveformWindow: WINDOW_SECONDS
    }))

    waveRef.current = ws
    recordRef.current = record

    return () => {
      try {
        record.stopMic?.()
      } catch {}
      ws.destroy()
      overlayWaveRef.current?.destroy()
      waveRef.current = null
      recordRef.current = null
      overlayWaveRef.current = null
    }
  }, [])

  // Measure container to derive px/second for the timeline
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => {
      const measured = Math.max(el.clientWidth, 1)
      setPxPerSecond(measured / WINDOW_SECONDS)
    }
    update()
    let ro: ResizeObserver | null = null
    try {
      ro = new ResizeObserver(() => update())
      ro.observe(el)
    } catch {
      // ignored if ResizeObserver is unavailable
    }
    return () => {
      ro?.disconnect()
    }
  }, [])

  // Keep the timeline in sync with parent duration (integer seconds) while animating in-between ticks
  const nowTime = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())

  useEffect(() => {
    baseTimeRef.current = duration
    baseTimestampRef.current = nowTime()
    setDisplayTime(duration)
  }, [duration])

  useEffect(() => {
    if (!isActive) {
      baseTimeRef.current = duration
      baseTimestampRef.current = nowTime()
      setDisplayTime(duration)
    }
  }, [isActive, duration])

  useEffect(() => {
    let frame: number
    const loop = () => {
      const now = nowTime()
      if (isActive) {
        const elapsed = (now - baseTimestampRef.current) / 1000
        setDisplayTime(baseTimeRef.current + Math.max(elapsed, 0))
      } else {
        setDisplayTime(baseTimeRef.current)
      }
      frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [isActive])

  // Start/stop mic preview based on recording or pre-recording state
  useEffect(() => {
    const record = recordRef.current
    if (!record) return
    const start = async () => {
      try {
        await record.startMic({
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100
        })
      } catch (err) {
        // Ignore if permissions are blocked; the parent already handles error UI
        // eslint-disable-next-line no-console
        console.warn('WaveSurfer mic failed:', err)
      }
    }
    if (isRecording || isPreRecording) {
      start()
    } else {
      record.stopMic?.()
    }
  }, [isRecording, isPreRecording])

  // Update colors when switching pre-record state
  useEffect(() => {
    const ws = waveRef.current
    if (!ws) return
    ws.setOptions({
      waveColor: isPreRecording ? 'rgba(16,185,129,0.55)' : 'rgba(99,102,241,0.55)',
      progressColor: isPreRecording ? 'rgba(5,150,105,0.85)' : 'rgba(236,72,153,0.85)'
    })
  }, [isPreRecording])

  return (
    <div className="w-full max-w-4xl mx-auto">
      {showHeader && (
        <div className="text-center mb-4 sm:mb-6">
          <div className="text-3xl sm:text-4xl font-mono font-bold text-gray-900">
            {formatTime(duration)}
          </div>
          {isPreRecording ? (
            <div className="text-xs sm:text-sm text-emerald-600 mt-1">Di los nombres de los participantes</div>
          ) : (
            <div className="text-xs sm:text-sm text-gray-500 mt-1">{isRecording ? 'Grabando...' : 'Detenido'}</div>
          )}
        </div>
      )}

      <div className="relative mb-2 sm:mb-3" style={{ height: '12.5rem' /* match h-40 sm:h-48 approx */ }}>
        {/* Left-half anchored live mic waveform: right edge exactly at center playhead */}
        <div className="absolute inset-y-0" style={{ right: '50%', width: '50%' }}>
          <div
            ref={containerRef}
            className="h-full w-full"
            style={{ opacity: isQuiet ? 0.35 : 1 }}
          />
        </div>

        {/* Static green names waveform overlay, clipped to left half */}
        {hasCompletedNamesClip && namesClipBlob && (
          <div className="absolute inset-y-0 overflow-hidden" style={{ right: '50%', width: '50%' }}>
            <div ref={overlayContainerRef} className="h-full w-full" />
          </div>
        )}
      </div>

      {/* Timeline under the waveform: center is current time; left shows past seconds; right shows next two seconds */}
      <div className="relative mb-4 sm:mb-6 select-none" style={{ height: 28 }}>
        {/* Center label at playhead */}
        <div className="pointer-events-none absolute inset-y-0 left-1/2 -translate-x-1/2 flex items-end">
          <div className="flex flex-col items-center">
            <div className="h-3 w-px bg-gray-400" />
            <div className="text-[10px] leading-none text-gray-700 mt-1 font-mono">{formatTime(Math.max(displayTime, 0))}</div>
          </div>
        </div>

        {/* Left: past seconds up to WINDOW_SECONDS */}
        <div className="absolute inset-y-0 overflow-hidden" style={{ right: '50%', width: '50%', maskImage: 'linear-gradient(to left, transparent 0%, rgba(0,0,0,0.2) 10%, rgba(0,0,0,0.8) 35%, black 60%)', WebkitMaskImage: 'linear-gradient(to left, transparent 0%, rgba(0,0,0,0.2) 10%, rgba(0,0,0,0.8) 35%, black 60%)' }}>
          {(() => {
            if (!Number.isFinite(displayTime) || pxPerSecond <= 0) return null
            const capped = Math.max(displayTime, 0)
            const baseSeconds = Math.floor(capped)
            const secondsSpacing = pxPerSecond < 24 ? (pxPerSecond < 16 ? (pxPerSecond < 10 ? 4 : 3) : 2) : 1
            const ticks = []
            for (let step = secondsSpacing; step <= WINDOW_SECONDS; step += secondsSpacing) {
              const value = baseSeconds - step
              if (value < 0) break
              const distance = capped - value
              if (distance < 0) continue
              const offset = Math.max(distance * pxPerSecond, 0)
              ticks.push(
                <div key={value} className="absolute bottom-0" style={{ right: offset, opacity: Math.max(0, 1 - distance / 18) }}>
                  <div className="h-2 w-px bg-gray-300" />
                  <div className="text-[10px] leading-none text-gray-500 mt-1 font-mono text-right" style={{ minWidth: secondsSpacing > 2 ? 36 : 32 }}>
                    {formatTime(value)}
                  </div>
                </div>
              )
            }
            return ticks
          })()}
        </div>

        {/* Right: next two seconds */}
        <div className="absolute inset-y-0 overflow-hidden" style={{ left: '50%', width: '50%', maskImage: 'linear-gradient(to right, transparent 0%, rgba(0,0,0,0.25) 20%, rgba(0,0,0,0.85) 55%, black 85%)', WebkitMaskImage: 'linear-gradient(to right, transparent 0%, rgba(0,0,0,0.25) 20%, rgba(0,0,0,0.85) 55%, black 85%)' }}>
          {(() => {
            if (!Number.isFinite(displayTime) || pxPerSecond <= 0) return null
            const capped = Math.max(displayTime, 0)
            const ticks = []
            for (let step = 1; step <= 2; step += 1) {
              const value = Math.floor(capped) + step
              const distance = value - capped
              if (distance < 0) continue
              const offset = Math.max(distance * pxPerSecond, 0)
              ticks.push(
                <div key={value} className="absolute bottom-0" style={{ left: offset, opacity: Math.max(0, 1 - distance / 4) }}>
                  <div className="h-2 w-px bg-gray-300" />
                  <div className="text-[10px] leading-none text-gray-500 mt-1 font-mono text-left" style={{ minWidth: 28 }}>
                    {formatTime(value)}
                  </div>
                </div>
              )
            }
            return ticks
          })()}
        </div>
      </div>

      {/* Render the overlay waveform from blob when available */}
      {hasCompletedNamesClip && namesClipBlob && (
        <OverlayRenderer namesClipBlob={namesClipBlob} containerRef={overlayContainerRef} waveRef={overlayWaveRef} />
      )}

      <div className="text-center">
        <div className={`inline-flex items-center space-x-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium ${isRecording ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-600'}`}>
          <div className={`w-2 h-2 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-gray-400'}`} />
          <span>{isRecording ? 'En vivo' : 'Inactivo'}</span>
        </div>
      </div>
    </div>
  )
}

// Helper subcomponent to render overlay once the container exists
const OverlayRenderer: React.FC<{
  namesClipBlob: Blob
  containerRef: React.RefObject<HTMLDivElement | null>
  waveRef: React.MutableRefObject<WaveSurfer | null>
}> = ({ namesClipBlob, containerRef, waveRef }) => {
  useEffect(() => {
    if (!containerRef.current) return
    // Destroy previous
    waveRef.current?.destroy()
    // Create a small, static wavesurfer for the names clip
    const ws = WaveSurfer.create({
      container: containerRef.current,
      height: 110,
      waveColor: 'rgba(16,185,129,0.55)',
      progressColor: 'rgba(5,150,105,0.85)',
      cursorWidth: 0,
      interact: false,
      normalize: true
    })
    const url = URL.createObjectURL(namesClipBlob)
    ws.load(url)
    waveRef.current = ws
    return () => {
      ws.destroy()
      waveRef.current = null
      URL.revokeObjectURL(url)
    }
  }, [namesClipBlob, containerRef, waveRef])
  return null
}
