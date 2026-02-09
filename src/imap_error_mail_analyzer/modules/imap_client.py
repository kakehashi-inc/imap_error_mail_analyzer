"""IMAP client for connecting to mail servers and fetching messages."""

import email
import imaplib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ImapClient:
    """Connects to an IMAP server and fetches email messages."""

    def __init__(self, account):
        self.account = account
        self._conn = None

    def connect(self):
        """Establish connection and authenticate."""
        security = self.account.security.lower()
        host = self.account.host
        port = self.account.port

        if security == "ssl":
            self._conn = imaplib.IMAP4_SSL(host, port)
        else:
            self._conn = imaplib.IMAP4(host, port)
            if security == "starttls":
                self._conn.starttls()

        self._conn.login(self.account.username, self.account.password)
        logger.info("Connected to %s as %s", host, self.account.username)

    def fetch_messages(self, folder, days):
        """Fetch all messages from *folder* that arrived within *days* days.

        Returns a list of ``email.message.Message`` objects.
        """
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        status, _ = self._conn.select(folder, readonly=True)
        if status != "OK":
            logger.warning("Failed to select folder: %s", folder)
            return []

        since = datetime.now() - timedelta(days=days)
        date_str = since.strftime("%d-%b-%Y")

        status, data = self._conn.search(None, f'(SINCE "{date_str}")')
        if status != "OK" or not data[0]:
            logger.info("No messages in %s since %s", folder, date_str)
            return []

        msg_ids = data[0].split()
        logger.info("Found %d message(s) in %s since %s", len(msg_ids), folder, date_str)

        messages = []
        for msg_id in msg_ids:
            status, msg_data = self._conn.fetch(msg_id, "(RFC822)")
            if status == "OK" and msg_data[0] is not None:
                raw = msg_data[0][1]
                messages.append(email.message_from_bytes(raw))

        return messages

    def disconnect(self):
        """Close the IMAP connection gracefully."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:  # pylint: disable=broad-except
                pass
            try:
                self._conn.logout()
            except Exception:  # pylint: disable=broad-except
                pass
            self._conn = None
            logger.info("Disconnected from %s", self.account.host)
