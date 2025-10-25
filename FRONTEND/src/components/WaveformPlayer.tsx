import React, { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Play, Pause } from 'lucide-react'

interface WaveformPlayerProps {
  audioUrl: string
  onTimeUpdate?: (time: number) => void
  onDurationChange?: (duration: number) => void
  seekTime?: number
}

export const WaveformPlayer: React.FC<WaveformPlayerProps> = ({
  audioUrl,
  onTimeUpdate,
  onDurationChange,
  seekTime
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isReady, setIsReady] = useState(false)

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current) return

    const wavesurfer = WaveSurfer.create({
      container: containerRef.current,
      waveColor: 'rgba(99, 102, 241, 0.5)',
      progressColor: 'rgba(99, 102, 241, 0.9)',
      cursorColor: 'rgba(236, 72, 153, 0.9)',
      barWidth: 2,
      barRadius: 3,
      cursorWidth: 2,
      height: 80,
      barGap: 2,
      normalize: true,
      interact: true
    })

    wavesurfer.load(audioUrl)

    // Ignore AbortError that can be thrown when destroying during pending loads
    wavesurfer.on('error', (e: any) => {
      if (e && (e.name === 'AbortError' || e.code === 'ABORT_ERR')) {
        return
      }
      // eslint-disable-next-line no-console
      console.error('WaveSurfer error:', e)
    })

    wavesurfer.on('ready', () => {
      const dur = wavesurfer.getDuration()
      setDuration(dur)
      onDurationChange?.(dur)
      setIsReady(true)
    })

    wavesurfer.on('audioprocess', (time) => {
      setCurrentTime(time)
      onTimeUpdate?.(time)
    })

    wavesurfer.on('seeking', (time) => {
      setCurrentTime(time)
      onTimeUpdate?.(time)
    })

    wavesurfer.on('play', () => {
      setIsPlaying(true)
    })

    wavesurfer.on('pause', () => {
      setIsPlaying(false)
    })

    wavesurfer.on('finish', () => {
      setIsPlaying(false)
    })

    wavesurferRef.current = wavesurfer

    return () => {
      try {
        wavesurfer.destroy()
      } catch (e: any) {
        // Swallow AbortError on teardown
        if (!e || (e.name !== 'AbortError' && e.code !== 'ABORT_ERR')) {
          // eslint-disable-next-line no-console
          console.error('Error destroying WaveSurfer:', e)
        }
      }
    }
  }, [audioUrl, onTimeUpdate, onDurationChange])

  // Reset loading state when audio URL changes
  useEffect(() => {
    setIsReady(false)
  }, [audioUrl])

  // Handle external seek requests (auto-play only when seekTime changes)
  useEffect(() => {
    const ws = wavesurferRef.current
    if (!ws || typeof seekTime !== 'number') return
    const dur = ws.getDuration()
    if (!dur || !isFinite(dur)) return
    const fraction = Math.min(1, Math.max(0, seekTime / dur))
    ws.seekTo(fraction)
    ws.play()
  }, [seekTime])

  const togglePlayPause = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause()
    }
  }

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-4">
        <button
          onClick={togglePlayPause}
          className="flex-shrink-0 bg-primary-600 text-white rounded-full p-3 hover:bg-primary-700 transition-colors"
        >
          {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </button>

        <div className="flex-1">
          <div className="relative" style={{ height: 80 }} aria-busy={!isReady}>
            <div ref={containerRef} className="w-full h-full" />
            {!isReady && (
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="h-20 w-full rounded bg-gray-200 animate-pulse" />
                <div className="mt-2 text-xs text-gray-600">Cargando audio…</div>
              </div>
            )}
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
