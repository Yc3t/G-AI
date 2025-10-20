from io import BytesIO
from typing import Dict, Any
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as canvas_module
import os


BRAND_COLOR = colors.HexColor('#17345C')  # hsl(222, 72%, 21%)


class HeaderCanvas(canvas_module.Canvas):
    """Custom canvas with header on every page"""
    def __init__(self, *args, logo_path=None, date_str='', **kwargs):
        super().__init__(*args, **kwargs)
        self.logo_path = logo_path
        self.date_str = date_str

    def showPage(self):
        self.draw_header()
        super().showPage()

    def draw_header(self):
        """Draw header with logo on left, title centered, and date on right"""
        self.saveState()

        page_width = letter[0]
        page_height = letter[1]

        # Logo on the left
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.drawImage(self.logo_path, 15, page_height - 35, width=2*inch, height=0.6*inch, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Could not add logo: {e}")

        # Title centered
        self.setFont('Helvetica-Bold', 18)
        self.setFillColor(BRAND_COLOR)
        title = "Acta de Reunión"
        title_width = self.stringWidth(title, 'Helvetica-Bold', 18)
        self.drawString((page_width - title_width) / 2, page_height - 25, title)

        # Date on the right
        if self.date_str:
            self.setFont('Helvetica-Bold', 18)
            self.setFillColor(BRAND_COLOR)
            self.drawRightString(page_width - 15, page_height - 25, self.date_str)

        # Separator line
        self.setStrokeColor(colors.black)
        self.setLineWidth(0.3)
        self.line(15, page_height - 38, page_width - 15, page_height - 38)

        self.restoreState()


def generate_acta_pdf(minutes_data: Dict[str, Any]) -> bytes:
    """Generate PDF bytes for meeting acta (minutes)"""
    buffer = BytesIO()

    # Extract date for header
    metadata = minutes_data.get('metadata', {})
    meeting_date = metadata.get('date', '')
    date_str = ''
    if meeting_date:
        try:
            date_obj = datetime.fromisoformat(meeting_date.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%d/%m/%Y')
        except Exception:
            pass

    # Logo path - look in same directory as this script
    logo_path = os.path.join(os.path.dirname(__file__), 'frumecar-ext.png')

    # Create document with custom canvas
    def get_canvas(buffer):
        return HeaderCanvas(buffer, pagesize=letter, logo_path=logo_path, date_str=date_str)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.9*inch,  # More space for header
        bottomMargin=0.5*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )

    # Container for PDF elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=BRAND_COLOR,
        spaceAfter=6,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    normal_style = styles['Normal']

    # Meeting metadata table (Title and Duration in one row) - matching frontend exactly
    meeting_title = metadata.get('title', 'Sin título')
    duration_secs = metadata.get('duration_seconds', 0)
    duration_str = f"{duration_secs // 60}m {duration_secs % 60}s"

    metadata_table_data = [
        ['Título', meeting_title, 'Duración', duration_str],
    ]

    metadata_table = Table(metadata_table_data, colWidths=[0.8*inch, 3.8*inch, 0.8*inch, 1*inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), BRAND_COLOR),
        ('BACKGROUND', (2, 0), (2, 0), BRAND_COLOR),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('TEXTCOLOR', (2, 0), (2, 0), colors.white),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.3*inch))

    # Participants section
    participants = minutes_data.get('participants', [])
    if participants:
        elements.append(Paragraph("Participantes", heading_style))
        elements.append(Spacer(1, 0.1*inch))

        participant_data = [['Nombre', 'Email']]
        for p in participants:
            name = p.get('name', '')
            email = p.get('email', '-')
            participant_data.append([name, email])

        participant_table = Table(participant_data, colWidths=[2.8*inch, 3.6*inch])
        participant_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.98, 0.99)]),
        ]))
        elements.append(participant_table)
        elements.append(Spacer(1, 0.25*inch))

    # Key Points section
    key_points = minutes_data.get('key_points', [])
    if key_points:
        elements.append(Paragraph("Puntos Clave", heading_style))
        elements.append(Spacer(1, 0.1*inch))

        key_points_data = [['Nº', 'Descripción']]
        for idx, kp in enumerate(key_points, 1):
            title = kp.get('title', '')
            key_points_data.append([str(idx), title])

        key_points_table = Table(key_points_data, colWidths=[0.5*inch, 6*inch])
        key_points_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.98, 0.99)]),
        ]))
        elements.append(key_points_table)
        elements.append(Spacer(1, 0.25*inch))

    # Tasks and Objectives section (task + description only)
    tasks = minutes_data.get('tasks_and_objectives', [])
    if isinstance(tasks, list) and tasks:
        elements.append(Paragraph("Tareas y Objetivos", heading_style))
        elements.append(Spacer(1, 0.1*inch))

        tasks_data = [["Tarea/Objetivo", "Descripción"]]
        for it in tasks:
            if not isinstance(it, dict):
                continue
            task = it.get('task', '')
            desc = it.get('description', '')
            tasks_data.append([task, desc])

        tasks_table = Table(tasks_data, colWidths=[2.5*inch, 4.1*inch])
        tasks_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.98, 0.99)]),
        ]))
        elements.append(tasks_table)
        elements.append(Spacer(1, 0.25*inch))

    # Custom Sections
    custom_sections = minutes_data.get('custom_sections', [])
    for section in custom_sections:
        section_title = section.get('title', '')
        section_content = section.get('content', '')

        elements.append(Paragraph(section_title, heading_style))
        elements.append(Spacer(1, 0.05*inch))
        elements.append(Paragraph(section_content, normal_style))
        elements.append(Spacer(1, 0.2*inch))

    # Build PDF with custom canvas
    doc.build(elements, canvasmaker=lambda *args, **kwargs: HeaderCanvas(*args, logo_path=logo_path, date_str=date_str, **kwargs))

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
