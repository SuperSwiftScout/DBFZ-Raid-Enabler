"""AES key management for DBFZ pak file decryption."""

from pathlib import Path
from utils.errors import AESKeyError
from utils.logger import logger

_PAK_MAGIC = b"\xE1\x12\x6F\x5A"

# Hardcoded AES-256 key for DBFZ v1.50 pak files.
# If extraction fails after a game update, the user is prompted for the new key.
HARDCODED_KEY = bytes.fromhex("6239755730524B4E593931626538484E334C656D6936386A36587369326C3766")


def get_aes_key(pak_path: Path) -> bytes:
    """
    Return the AES key for pak decryption.

    Checks the pak file is valid, then returns the hardcoded key.
    If the key is wrong the extraction step will raise PakError.
    """
    if not _is_valid_pak(pak_path):
        raise AESKeyError(f"Not a valid UE4 pak file: {pak_path}")

    logger.info("Pak file validated, using hardcoded AES key")
    return HARDCODED_KEY


def validate_user_key(key_str: str, pak_path: Path) -> bytes:
    """
    Parse a user-supplied AES key string and return the key bytes.

    Accepts hex format (with or without 0x prefix) or raw 32-char ASCII.
    Only validates format and length — correctness is verified during extraction.
    """
    key_str = key_str.strip()

    try:
        if key_str.lower().startswith("0x"):
            key = bytes.fromhex(key_str[2:])
        elif all(c in "0123456789abcdefABCDEF" for c in key_str) and len(key_str) == 64:
            key = bytes.fromhex(key_str)
        else:
            key = key_str.encode("ascii")
    except (ValueError, UnicodeEncodeError):
        raise AESKeyError("Invalid key format. Provide a 64-char hex string or 32-char ASCII key.")

    if len(key) != 32:
        raise AESKeyError(f"Key must be 32 bytes, got {len(key)}.")

    if not _is_valid_pak(pak_path):
        raise AESKeyError(f"Not a valid UE4 pak file: {pak_path}")

    return key


def _is_valid_pak(pak_path: Path) -> bool:
    """Check that the file ends with the UE4 pak magic bytes in the footer."""
    try:
        with open(pak_path, 'rb') as f:
            f.seek(-512, 2)
            tail = f.read(512)
        return _PAK_MAGIC in tail
    except Exception as e:
        logger.error(f"Failed to read pak file: {e}")
        return False
