import os
import smtplib
import ssl
from typing import List, Dict, Optional
from email.message import EmailMessage


class SMTPEmailer:
    def __init__(self) -> None:
        # Configuration via environment variables
        self.smtp_host = os.getenv('SMTP_HOST') or os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT') or '587')
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_pass = os.getenv('SMTP_PASS')
        self.from_addr = os.getenv('SMTP_FROM') or self.smtp_user
        # STARTTLS enabled by default; set SMTP_STARTTLS=false to disable
        self.starttls = (os.getenv('SMTP_STARTTLS', 'true').lower() != 'false')
        self.timeout_seconds = int(os.getenv('SMTP_TIMEOUT', '30'))

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_port and self.smtp_user and self.smtp_pass and self.from_addr)

    def _open_smtp(self) -> smtplib.SMTP:
        """Open and return an authenticated SMTP connection."""
        context = ssl.create_default_context()
        smtp = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout_seconds)
        smtp.ehlo()
        if self.starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if self.smtp_user and self.smtp_pass:
            smtp.login(self.smtp_user, self.smtp_pass)
        return smtp

    def send_html_bulk(self, subject: str, html_body: str, recipients: List[str]) -> Dict[str, List[str]]:
        """Send an HTML email (no attachments) to multiple recipients."""
        delivered: List[str] = []
        failed: List[str] = []
        if not recipients:
            return {"delivered": delivered, "failed": failed}
        smtp = None
        try:
            smtp = self._open_smtp()
            for rcpt in recipients:
                try:
                    msg = EmailMessage()
                    msg['From'] = self.from_addr
                    msg['To'] = rcpt
                    msg['Subject'] = subject
                    # Provide a plain-text fallback for clients that don't render HTML
                    msg.set_content("Este mensaje contiene contenido en HTML.")
                    msg.add_alternative(html_body or "", subtype='html')
                    smtp.send_message(msg, to_addrs=[rcpt])
                    delivered.append(rcpt)
                except Exception as e:
                    print(f"Failed to send email to {rcpt}: {e}")
                    failed.append(rcpt)
        finally:
            try:
                if smtp:
                    smtp.quit()
            except Exception:
                pass
        return {"delivered": delivered, "failed": failed}

    def send_pdf_bulk(self, subject: str, pdf_bytes: bytes, filename: str, recipients: List[str], html_body: Optional[str] = None) -> Dict[str, List[str]]:
        """Send an email with a PDF attachment to multiple recipients."""
        delivered: List[str] = []
        failed: List[str] = []
        if not recipients:
            return {"delivered": delivered, "failed": failed}
        if not html_body:
            html_body = "<p>Adjunto encontrarás el acta de la reunión.</p>"

        smtp = None
        try:
            smtp = self._open_smtp()
            for rcpt in recipients:
                try:
                    msg = EmailMessage()
                    msg['From'] = self.from_addr
                    msg['To'] = rcpt
                    msg['Subject'] = subject
                    msg.set_content("Adjuntamos un archivo PDF con el acta de la reunión.")
                    msg.add_alternative(html_body, subtype='html')
                    # Attach PDF
                    msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=filename)
                    smtp.send_message(msg, to_addrs=[rcpt])
                    delivered.append(rcpt)
                except Exception as e:
                    print(f"Failed to send email to {rcpt}: {e}")
                    failed.append(rcpt)
        finally:
            try:
                if smtp:
                    smtp.quit()
            except Exception:
                pass
        return {"delivered": delivered, "failed": failed}


# Backward compatibility alias
ResendEmailer = SMTPEmailer
