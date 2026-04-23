import os
import imghdr
import hashlib
from typing import BinaryIO
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Encryption key should be stored securely in environment variables
ENCRYPTION_KEY = os.environ.get('EVIDENCE_ENCRYPTION_KEY')
if ENCRYPTION_KEY:
    # Convert base64 key back to bytes
    ENCRYPTION_KEY = base64.urlsafe_b64decode(ENCRYPTION_KEY.encode())
else:
    ENCRYPTION_KEY = None


def allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file_type(file: BinaryIO, filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        header = file.read(4)
        file.seek(0)
        return header == b"%PDF"
    elif ext in {"png", "jpg", "jpeg"}:
        kind = imghdr.what(file)
        file.seek(0)
        return kind in {"png", "jpeg"}
    return False


def get_file_size(file: BinaryIO) -> int:
    pos = file.tell()
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(pos)
    return size


def compute_sha256(file: BinaryIO) -> str:
    file.seek(0)
    sha256 = hashlib.sha256()
    while chunk := file.read(8192):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


def encrypt_file_data(data: bytes) -> tuple[bytes, str]:
    """Encrypt file data and return encrypted data with key info."""
    if not ENCRYPTION_KEY:
        return data, "unencrypted"
    
    try:
        fernet = Fernet(ENCRYPTION_KEY)
        encrypted_data = fernet.encrypt(data)
        return encrypted_data, "encrypted"
    except Exception:
        # Fallback to unencrypted if encryption fails
        return data, "encryption_failed"


def decrypt_file_data(encrypted_data: bytes, encryption_status: str) -> bytes:
    """Decrypt file data based on encryption status."""
    if encryption_status != "encrypted" or not ENCRYPTION_KEY:
        return encrypted_data
    
    try:
        fernet = Fernet(ENCRYPTION_KEY)
        return fernet.decrypt(encrypted_data)
    except Exception:
        # Return original data if decryption fails
        return encrypted_data


def basic_malware_scan(file: BinaryIO) -> bool:
    # Try clamav_client if available, else fallback to basic scan
    try:
        from clamav_client import get_scanner
        scanner = get_scanner()
        file.seek(0)
        result = scanner.scan_stream(file.read())
        file.seek(0)
        # result: {'stream': {'status': 'FOUND', 'virus': 'Eicar-Test-Signature'}}
        if result and isinstance(result, dict):
            stream_result = result.get('stream')
            if stream_result and stream_result.get('status') == 'FOUND':
                return False
        return True
    except Exception:
        pass
    # Fallback: basic scan
    file.seek(0)
    data = file.read(4096)
    file.seek(0)
    if b"<script" in data or b"MZ" in data:  # MZ = PE header (Windows exe)
        return False
    return True
