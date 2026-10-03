"""Send lab reports by email, through the Gmail API.

Trimmed out of a borrowed email-classification service. What remains is the
send path, attachment handling, and the OAuth handshake they depend on;
reading, searching, reply threading, classification and the vector store that
came with the original are gone.

Credentials come from a Google Cloud OAuth client. The first run opens a
browser for consent and writes a token; later runs reuse and silently refresh
it.
"""

import base64
import logging
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Send only. The original also requested readonly and modify, which this needs
# none of — a token that cannot read the mailbox is a smaller thing to leak.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Defaults sit beside this module. The original resolved parents[4], which
# pointed outside the project it was copied into.
_DEFAULT_DIR = Path(__file__).resolve().parent

# Gmail rejects messages over 25 MB. Base64 inflates attachments by about a
# third, so the raw-bytes ceiling is lower than the advertised limit.
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024

# An attachment is a path, or a path paired with the name the recipient sees.
# The pair form matters for stored reports: they are saved as
# "<uuid>__original-name.pdf", and nobody wants that landing in their inbox.
Attachment = Union[str, Path, Tuple[Union[str, Path], str]]


class EmailSender:
    """Sends mail, with optional file attachments, as the authenticated account."""

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        self.credentials_path = Path(
            credentials_path or os.getenv("GMAIL_CREDENTIALS_PATH", _DEFAULT_DIR / "credentials.json")
        ).resolve()
        self.token_path = Path(
            token_path or os.getenv("GMAIL_TOKEN_PATH", _DEFAULT_DIR / "token.json")
        ).resolve()
        self.service = None

    def connect(self) -> None:
        """Authenticate and build the Gmail client. Call once before sending."""
        creds = None

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), GMAIL_SCOPES)
            except Exception as exc:
                logger.warning("Could not load token file %s: %s", self.token_path, exc)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    logger.error("Token refresh failed: %s", exc)
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(f"OAuth credentials not found: {self.credentials_path}")
                # Opens a browser. Fine for a desktop or first-time setup, but
                # it will hang a headless server — mint the token locally and
                # ship token.json instead.
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)

            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail authentication successful")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[Sequence[Attachment]] = None,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send a message, optionally as HTML and optionally with files attached.

        When `html_body` is given it is sent alongside `body` as alternatives:
        clients show the HTML, and plain-text readers still get something
        legible rather than markup.

        Each attachment is a path, or a (path, display_name) pair when the name
        on disk is not the name the recipient should see.

        Returns False if Gmail rejects the message. Problems with the
        attachments themselves raise instead: a report that silently failed to
        attach is worse than one that failed loudly.
        """
        if self.service is None:
            raise RuntimeError("connect() must be called before send_email()")

        message = self._build_message(to, subject, body, cc, bcc, attachments, html_body)

        try:
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            self.service.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info("Email sent to %s with %d attachment(s)", to, len(attachments or []))
            return True

        except HttpError as error:
            logger.error("Error sending email: %s", error)
            return False

    def _build_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str],
        bcc: Optional[str],
        attachments: Optional[Sequence[Attachment]],
        html_body: Optional[str] = None,
    ):
        # The two renderings are alternatives of one another, so they belong in
        # a multipart/alternative. Attaching the HTML next to the PDF instead
        # would make clients show it as a second attachment.
        if html_body:
            content = MIMEMultipart("alternative")
            # Least-preferred first: clients pick the last part they can render.
            content.attach(MIMEText(body))
            content.attach(MIMEText(html_body, "html"))
        else:
            content = MIMEText(body)

        # A message with no attachments stays as that content rather than being
        # wrapped in a mixed multipart with one child.
        if attachments:
            message = MIMEMultipart()
            message.attach(content)
            for item in attachments:
                self._attach_file(message, *self._split(item))
        else:
            message = content

        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc
        return message

    @staticmethod
    def _split(item: Attachment) -> Tuple[Path, Optional[str]]:
        if isinstance(item, (tuple, list)):
            path, display_name = item
            return Path(path), display_name
        return Path(item), None

    @staticmethod
    def _attach_file(message: MIMEMultipart, path: Path, display_name: Optional[str]) -> None:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")

        size = path.stat().st_size
        if size > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"{path.name} is {size / 1024 / 1024:.1f} MB; the limit is "
                f"{MAX_ATTACHMENT_BYTES / 1024 / 1024:.0f} MB before base64 encoding."
            )

        # Guessed from the extension so a PDF arrives as a PDF rather than an
        # unnamed binary blob. An encoding means a compressed wrapper such as
        # .pdf.gz, where the inner type is not what should be declared.
        content_type, encoding = mimetypes.guess_type(path.name)
        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)

        part = MIMEBase(maintype, subtype)
        part.set_payload(path.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=display_name or path.name)
        message.attach(part)

    def send_report(
        self,
        to: str,
        report_path: Union[str, Path],
        display_name: Optional[str] = None,
        patient_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> bool:
        """Share one stored lab report, with a subject and body already written.

        `display_name` is worth passing for stored reports, whose filenames
        carry a generated id prefix.
        """
        who = f" for {patient_name}" if patient_name else ""

        paragraphs = [f"Attached is the lab report{who}."]
        if note:
            paragraphs.append(note.strip())
        paragraphs.append(
            "This message was sent from the Clinical Lab Result Analyzer.\n"
            "Clinical decision support — informational only, not a diagnosis."
        )

        return self.send_email(
            to=to,
            subject=f"Lab report{who}",
            body="\n\n".join(paragraphs),
            attachments=[(report_path, display_name)],
        )
