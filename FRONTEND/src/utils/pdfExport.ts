import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import type { Meeting } from '../types/index'

const BRAND_COLOR_RGB = [23, 52, 92] as [number, number, number] // hsl(222, 72%, 21%)

const loadLogo = async (): Promise<HTMLImageElement | null> => {
  try {
    const img = new Image()
    img.src = '/frumecar-ext.png'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject()
      setTimeout(() => reject(new Error('Timeout')), 2000)
    })
    return img
  } catch (error) {
    console.log('Logo not loaded, continuing without it')
    return null
  }
}

const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

const addHeaderWithLogo = (doc: jsPDF, img: HTMLImageElement | null, title: string, date?: string) => {
  const pageWidth = doc.internal.pageSize.getWidth()

  // Logo
  if (img) {
    doc.addImage(img, 'PNG', 15, 10, 40, 15)
  }

  // Title
  doc.setFontSize(18)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...BRAND_COLOR_RGB)
  const titleWidth = doc.getTextWidth(title)
  const titleXPos = (pageWidth - titleWidth) / 2
  doc.text(title, titleXPos, 20)

  // Date on the right
  if (date) {
    doc.setFontSize(18)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(...BRAND_COLOR_RGB)
    const dateText = new Date(date).toLocaleDateString('es-ES')
    doc.text(dateText, pageWidth - 15, 20, { align: 'right' })
  }

  // Separator line
  doc.setDrawColor(0, 0, 0)
  doc.setLineWidth(0.3)
  doc.line(15, 25, pageWidth - 15, 25)

  doc.setTextColor(0, 0, 0) // Reset to black
}

const buildActaDoc = async (meeting: Meeting): Promise<jsPDF | null> => {
  if (!meeting?.minutes) return null
  const minutes = meeting.minutes

  const doc = new jsPDF()
  const img = await loadLogo()

  addHeaderWithLogo(doc, img, 'Acta de Reunión', minutes.metadata.date)

  // Meeting title and duration as table (single row)
  let yPos = 30
  const titleDurationRow = [
    'Título',
    minutes.metadata.title,
    'Duración',
    formatDuration(minutes.metadata.duration_seconds || 0)
  ]

  autoTable(doc, {
    startY: yPos,
    body: [titleDurationRow],
    theme: 'plain',
    styles: {
      fontSize: 10,
      cellPadding: 2,
      textColor: [0, 0, 0],
      lineWidth: 0
    },
    columnStyles: {
      0: {
        fontStyle: 'bold',
        cellWidth: 20,
        fillColor: BRAND_COLOR_RGB,
        textColor: [255, 255, 255],
        fontSize: 9
      },
      1: { cellWidth: 'auto' },
      2: {
        fontStyle: 'bold',
        cellWidth: 20,
        fillColor: BRAND_COLOR_RGB,
        textColor: [255, 255, 255],
        fontSize: 9
      },
      3: { cellWidth: 30 }
    },
    margin: { left: 15, right: 15 }
  })

  yPos = (doc as any).lastAutoTable.finalY + 12

  if (minutes.objective) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Objetivo', 15, yPos)
    yPos += 5
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(10)
    const objectiveLines = doc.splitTextToSize(minutes.objective, 180)
    doc.text(objectiveLines, 15, yPos)
    yPos += objectiveLines.length * 5 + 8
  }

  // Participants
  if (minutes.participants.length > 0) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Participantes', 15, yPos)
    yPos += 5

    const participantData = minutes.participants.map(p => [
      p.name,
      p.email || '-'
    ])

    autoTable(doc, {
      startY: yPos,
      head: [['Nombre', 'Email']],
      body: participantData,
      theme: 'striped',
      headStyles: {
        fillColor: BRAND_COLOR_RGB,
        textColor: [255, 255, 255],
        fontSize: 10,
        fontStyle: 'bold',
        halign: 'left',
        lineWidth: 0.5,
        lineColor: [203, 213, 225]
      },
      bodyStyles: {
        fontSize: 9,
        cellPadding: 4,
        textColor: [0, 0, 0]
      },
      alternateRowStyles: {
        fillColor: [248, 250, 252]
      },
      margin: { left: 15, right: 15 }
    })

    yPos = (doc as any).lastAutoTable.finalY + 10
  }

  // Key Points
  if (minutes.key_points.length > 0) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Puntos Clave', 15, yPos)
    yPos += 5

    const keyPointsData = minutes.key_points.map((kp, idx) => [
      `${idx + 1}`,
      kp.title
    ])

    autoTable(doc, {
      startY: yPos,
      head: [['Nº', 'Descripción']],
      body: keyPointsData,
      theme: 'striped',
      headStyles: {
        fillColor: BRAND_COLOR_RGB,
        textColor: [255, 255, 255],
        fontSize: 10,
        fontStyle: 'bold',
        halign: 'left',
        lineWidth: 0.5,
        lineColor: [203, 213, 225]
      },
      bodyStyles: {
        fontSize: 9,
        cellPadding: 4,
        textColor: [0, 0, 0]
      },
      columnStyles: {
        0: { cellWidth: 15, halign: 'center' }
      },
      alternateRowStyles: {
        fillColor: [248, 250, 252]
      },
      margin: { left: 15, right: 15 }
    })

    yPos = (doc as any).lastAutoTable.finalY + 10
  }

  const detailEntries = minutes.key_points
    .map((kp, idx) => {
      const detail = minutes.details?.[kp.id]
      if (!detail || !detail.content?.trim()) return null
      return {
        index: idx + 1,
        title: detail.title || kp.title,
        time: kp.time,
        content: detail.content
      }
    })
    .filter(Boolean) as Array<{ index: number; title: string; time?: string; content: string }>

  if (detailEntries.length > 0) {
    if (yPos > 250) {
      doc.addPage()
      yPos = 20
    }

    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Temas tratados', 15, yPos)
    yPos += 6

    detailEntries.forEach(entry => {
      if (yPos > 270) {
        doc.addPage()
        yPos = 20
      }

      doc.setFontSize(11)
      doc.setFont('helvetica', 'bold')
      const header = `${entry.index}. ${entry.title}${entry.time ? ` (${entry.time})` : ''}`
      doc.text(header, 15, yPos)
      yPos += 5

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(10)
      const bulletLines = entry.content
        .split('\n')
        .map(line => {
          const trimmed = line.replace(/\s+$/, '')
          if (!trimmed.trim()) return null
          const trimmedLeft = trimmed.replace(/^\s+/, '')
          if (!trimmedLeft.startsWith('-')) {
            return { text: trimmedLeft, indent: 0, isBullet: false }
          }
          const bulletText = trimmedLeft.replace(/^-\s*/, '').trim()
          const isSub = trimmed.startsWith('  -')
          return { text: bulletText, indent: isSub ? 8 : 0, isBullet: true }
        })
        .filter((item): item is { text: string; indent: number; isBullet: boolean } => !!item)

      bulletLines.forEach(line => {
        if (yPos > 280) {
          doc.addPage()
          yPos = 20
        }

        const bulletX = 20 + line.indent
        const textX = bulletX + (line.isBullet ? 5 : 0)
        const maxWidth = 170 - line.indent
        const wrappedText = doc.splitTextToSize(line.text, maxWidth)

        if (line.isBullet) {
          doc.setFont('helvetica', 'bold')
          doc.text('•', bulletX, yPos)
          doc.setFont('helvetica', 'normal')
        }

        wrappedText.forEach((wrapLine: string, idx: number) => {
          if (yPos > 280) {
            doc.addPage()
            yPos = 20
          }
          doc.text(wrapLine, idx === 0 ? textX : bulletX + 5, yPos)
          yPos += 4
        })
        yPos += 2
      })
      yPos += 4
    })
  }

  // Tasks and Objectives (task + description only)
  if (meeting.minutes.tasks_and_objectives && meeting.minutes.tasks_and_objectives.length > 0) {
    if (yPos > 250) {
      doc.addPage()
      yPos = 20
    }

    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Tareas y Objetivos', 15, yPos)
    yPos += 5

    const taskRows = meeting.minutes.tasks_and_objectives.map(it => [
      it.task,
      it.description || ''
    ])

    autoTable(doc, {
      startY: yPos,
      head: [['Tarea/Objetivo', 'Descripción']],
      body: taskRows,
      theme: 'striped',
      headStyles: {
        fillColor: BRAND_COLOR_RGB,
        textColor: [255, 255, 255],
        fontSize: 10,
        fontStyle: 'bold',
        halign: 'left',
        lineWidth: 0.5,
        lineColor: [203, 213, 225]
      },
      bodyStyles: {
        fontSize: 9,
        cellPadding: 4,
        textColor: [0, 0, 0]
      },
      columnStyles: {
        0: { cellWidth: 80 },
        1: { cellWidth: 110 }
      },
      alternateRowStyles: {
        fillColor: [248, 250, 252]
      },
      margin: { left: 15, right: 15 }
    })

    yPos = (doc as any).lastAutoTable.finalY + 10
  }

  // Custom Sections
  if (meeting.minutes.custom_sections && meeting.minutes.custom_sections.length > 0) {
    meeting.minutes.custom_sections.forEach(section => {
      if (yPos > 250) {
        doc.addPage()
        yPos = 20
      }

      doc.setFontSize(12)
      doc.setFont('helvetica', 'bold')
      doc.text(section.title, 15, yPos)
      yPos += 7

      doc.setFontSize(10)
      doc.setFont('helvetica', 'normal')
      const lines = doc.splitTextToSize(section.content, 180)
      doc.text(lines, 15, yPos)
      yPos += lines.length * 5 + 10
    })
  }

  return doc
}

export const exportActaToPDF = async (meeting: Meeting) => {
  const doc = await buildActaDoc(meeting)
  if (!doc || !meeting?.minutes) return
  const fileName = `Acta_${meeting.minutes.metadata.title.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.pdf`
  doc.save(fileName)
}

export const buildActaPdfBlob = async (meeting: Meeting): Promise<{ blob: Blob; filename: string } | null> => {
  const doc = await buildActaDoc(meeting)
  if (!doc || !meeting?.minutes) return null
  const blob = (doc as any).output('blob') as Blob
  const filename = `Acta_${meeting.minutes.metadata.title.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.pdf`
  return { blob, filename }
}
