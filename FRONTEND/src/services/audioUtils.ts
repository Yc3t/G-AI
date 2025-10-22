export class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null
  private audioContext: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private microphone: MediaStreamAudioSourceNode | null = null
  private dataArray: Uint8Array | null = null
  private animationFrame: number | null = null
  private stream: MediaStream | null = null
  private chunks: Blob[] = []
  
  private onAudioLevelChange?: (level: number) => void
  private onDataAvailable?: (blob: Blob) => void
  private onError?: (error: Error) => void

  constructor(options: {
    onAudioLevelChange?: (level: number) => void
    onDataAvailable?: (blob: Blob) => void
    onError?: (error: Error) => void
  } = {}) {
    this.onAudioLevelChange = options.onAudioLevelChange
    this.onDataAvailable = options.onDataAvailable
    this.onError = options.onError
  }

  async requestPermission(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true
      })
      
      // Stop the test stream
      stream.getTracks().forEach(track => track.stop())
      return true
    } catch (error) {
      console.error('Failed to get microphone permission:', error)
      return false
    }
  }

  async startRecording(): Promise<void> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      // Set up audio context for level monitoring
      this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      this.analyser = this.audioContext.createAnalyser()
      this.microphone = this.audioContext.createMediaStreamSource(this.stream)
      
      this.analyser.fftSize = 256
      this.analyser.smoothingTimeConstant = 0.8
      this.dataArray = new Uint8Array(this.analyser.frequencyBinCount)
      
      this.microphone.connect(this.analyser)
      
      // Set up MediaRecorder
      const options: MediaRecorderOptions = {
        mimeType: 'audio/webm;codecs=opus'
      }
      
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'audio/webm'
      }
      
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = 'audio/mp4'
      }

      this.mediaRecorder = new MediaRecorder(this.stream, options)
      this.chunks = []

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.chunks.push(event.data)
        }
      }

      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.mediaRecorder!.mimeType })
        this.onDataAvailable?.(blob)
        this.chunks = []
      }

      this.mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event)
        this.onError?.(new Error('Recording failed'))
      }

      this.mediaRecorder.start(100) // Collect data every 100ms
      this.startAudioLevelMonitoring()
      
    } catch (error) {
      console.error('Failed to start recording:', error)
      this.onError?.(error as Error)
      throw error
    }
  }

  stopRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    
    this.stopAudioLevelMonitoring()
    this.cleanup()
  }

  pauseRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.pause()
      this.stopAudioLevelMonitoring()
    }
  }

  resumeRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
      this.mediaRecorder.resume()
      this.startAudioLevelMonitoring()
    }
  }

  private startAudioLevelMonitoring(): void {
    if (!this.analyser || !this.dataArray) return

    const updateLevel = () => {
      if (!this.analyser || !this.dataArray) return
      
      this.analyser.getByteFrequencyData(this.dataArray)
      
      // Calculate average level
      let sum = 0
      for (let i = 0; i < this.dataArray.length; i++) {
        sum += this.dataArray[i]
      }
      
      const average = sum / this.dataArray.length
      const normalizedLevel = Math.min(average / 128, 1) // Normalize to 0-1
      
      this.onAudioLevelChange?.(normalizedLevel)
      this.animationFrame = requestAnimationFrame(updateLevel)
    }
    
    updateLevel()
  }

  private stopAudioLevelMonitoring(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame)
      this.animationFrame = null
    }
    this.onAudioLevelChange?.(0)
  }

  private cleanup(): void {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
      this.stream = null
    }
    
    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }
    
    this.analyser = null
    this.microphone = null
    this.dataArray = null
  }

  get isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording'
  }

  get isPaused(): boolean {
    return this.mediaRecorder?.state === 'paused'
  }

  get isActive(): boolean {
    return this.mediaRecorder?.state === 'recording' || this.mediaRecorder?.state === 'paused'
  }
}

export const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

export const formatTimestamp = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export const parseTimestamp = (timeStr: string): number => {
  if (!timeStr || typeof timeStr !== 'string' || !timeStr.includes(':')) return 0
  const parts = timeStr.split(':')
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10)
}
