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

  const doc = new jsPDF()
  const img = await loadLogo()

  addHeaderWithLogo(doc, img, 'Acta de Reunión', meeting.minutes.metadata.date)

  // Meeting title and duration as table (single row)
  let yPos = 30
  const titleDurationRow = [
    'Título',
    meeting.minutes.metadata.title,
    'Duración',
    formatDuration(meeting.minutes.metadata.duration_seconds || 0)
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

  // Participants
  if (meeting.minutes.participants.length > 0) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Participantes', 15, yPos)
    yPos += 5

    const participantData = meeting.minutes.participants.map(p => [
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
  if (meeting.minutes.key_points.length > 0) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Puntos Clave', 15, yPos)
    yPos += 5

    const keyPointsData = meeting.minutes.key_points.map((kp, idx) => [
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

export const exportSummaryToPDF = async (meeting: Meeting) => {
  if (!meeting?.summary_data) return

  const doc = new jsPDF()
  const img = await loadLogo()

  addHeaderWithLogo(doc, img, 'Resumen de Reunión', meeting.minutes?.metadata.date)

  // Meeting title and duration as table (single row)
  let yPos = 30
  const titleDurationRow = [
    'Título',
    meeting.summary_data?.metadata.title || meeting.minutes?.metadata.title || '',
    'Duración',
    formatDuration(meeting.minutes?.metadata.duration_seconds || 0)
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

  // Main Points
  if (meeting.summary_data.main_points.length > 0) {
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.text('Puntos Principales', 15, yPos)
    yPos += 5

    const mainPointsData = meeting.summary_data.main_points.map((point, idx) => [
      `${idx + 1}`,
      point.title,
      point.time || '-'
    ])

    autoTable(doc, {
      startY: yPos,
      head: [['Nº', 'Punto', 'Tiempo']],
      body: mainPointsData,
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
        0: { cellWidth: 15, halign: 'center' },
        2: { cellWidth: 25, halign: 'center' }
      },
      alternateRowStyles: {
        fillColor: [248, 250, 252]
      },
      margin: { left: 15, right: 15 }
    })

    yPos = (doc as any).lastAutoTable.finalY + 10
  }

  // Detailed Summary Sections
  const summary = meeting.summary_data
  if (summary && summary.detailed_summary && summary.main_points) {
    // Iterate through main_points to get the proper order and titles
    summary.main_points.forEach((point, index) => {
      const sectionData = summary.detailed_summary[point.id]
      if (!sectionData) return

      if (yPos > 250) {
        doc.addPage()
        yPos = 20
      }

      doc.setFontSize(12)
      doc.setFont('helvetica', 'bold')
      doc.text(`${index + 1}. ${point.title}`, 15, yPos)
      yPos += 7

      doc.setFontSize(10)
      doc.setFont('helvetica', 'normal')

      // Remove markdown formatting for PDF
      let content = sectionData.content
      content = content.replace(/\*\*\*/g, '') // Remove bold+italic
      content = content.replace(/\*\*/g, '') // Remove bold
      content = content.replace(/\*/g, '') // Remove italic
      content = content.replace(/^- /gm, '• ') // Convert markdown lists to bullets

      const lines = doc.splitTextToSize(content, 180)
      doc.text(lines, 15, yPos)
      yPos += lines.length * 5 + 10
    })
  }

  // Save PDF
  const fileName = `Resumen_${meeting.summary_data.metadata.title.replace(/[^a-z0-9]/gi, '_')}_${new Date().toISOString().split('T')[0]}.pdf`
  doc.save(fileName)
}
