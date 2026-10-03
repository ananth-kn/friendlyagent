import os
import base64
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )

            creds = flow.run_local_server(port=8080)

        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)

    return build(
        "gmail",
        "v1",
        credentials=creds
    )


def decode_data(data):
    return base64.urlsafe_b64decode(data).decode(
        "utf-8",
        errors="replace"
    )


def extract_body(message):
    """
    Extract plain-text body from a Gmail message.
    Handles nested MIME structures.
    """

    def walk_parts(parts):

        for part in parts:

            mime_type = part.get("mimeType", "")
            body = part.get("body", {})

            if mime_type == "text/plain" and body.get("data"):
                return decode_data(body["data"])

            if part.get("parts"):
                result = walk_parts(part["parts"])

                if result:
                    return result

        return ""

    payload = message.get("payload", {})

    # Simple non-multipart email
    body = payload.get("body", {})

    if body.get("data"):
        return decode_data(body["data"])

    # Multipart email
    return walk_parts(payload.get("parts", []))


def get_header(headers, name):
    """
    Get a specific email header.
    """

    for header in headers:

        if header["name"].lower() == name.lower():
            return header["value"]

    return ""


def get_unread_emails(service, max_results=50):
    """
    Fetch unread Gmail messages and return structured email data.
    """

    results = service.users().messages().list(
        userId="me",
        q="is:unread category:primary",
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])

    emails = []

    for item in messages:

        message_id = item["id"]

        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        payload = message.get("payload", {})

        headers = payload.get("headers", [])

        subject = get_header(headers, "Subject")
        sender = get_header(headers, "From")
        date = get_header(headers, "Date")

        body = extract_body(message)

        attachments = extract_attachment_metadata(payload)

        emails.append({
            "id": message_id,
            "sender": sender,
            "subject": subject,
            "date": date,
            "body": body,
            "attachments": attachments
        })

    return emails


def extract_attachment_metadata(payload):
    """
    Find attachment filenames and MIME types recursively.
    Does NOT download the attachments.
    """

    attachments = []

    def walk_parts(parts):

        for part in parts:

            filename = part.get("filename")

            if filename:

                attachments.append({
                    "filename": filename,
                    "mime_type": part.get("mimeType"),
                    "attachment_id": part.get(
                        "body", {}
                    ).get("attachmentId")
                })

            if part.get("parts"):
                walk_parts(part["parts"])

    walk_parts(payload.get("parts", []))

    return attachments


def download_attachment(
    service,
    message_id,
    attachment_id,
    filename
):
    """
    Download a specific Gmail attachment.
    """

    os.makedirs("downloads", exist_ok=True)

    attachment = service.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=attachment_id
    ).execute()

    data = base64.urlsafe_b64decode(
        attachment["data"]
    )

    filepath = os.path.join(
        "downloads",
        filename
    )

    with open(filepath, "wb") as f:
        f.write(data)

    return filepath


def download_assignment_attachments(service, assignment):
    """
    Download only the attachments selected by the LLM.
    """

    message_id = assignment["email_id"]
    wanted_files = set(assignment["relevant_attachments"])

    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    payload = message.get("payload", {})

    downloaded = []

    def walk_parts(parts):
        for part in parts:
            filename = part.get("filename")

            if filename and filename in wanted_files:
                attachment_id = part.get(
                    "body", {}
                ).get("attachmentId")

                if attachment_id:
                    path = download_attachment(
                        service,
                        message_id,
                        attachment_id,
                        filename
                    )

                    downloaded.append(path)

            if part.get("parts"):
                walk_parts(part["parts"])

    walk_parts(payload.get("parts", []))

    return downloaded