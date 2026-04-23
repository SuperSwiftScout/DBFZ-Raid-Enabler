"""Custom exceptions for DBFZ Raid Enabler."""


class DBFZRaidError(Exception):
    """Base exception for all application errors."""
    pass


class SteamNotFoundError(DBFZRaidError):
    """Raised when Steam installation cannot be detected."""
    pass


class GameNotFoundError(DBFZRaidError):
    """Raised when DBFZ installation cannot be located."""
    pass


class BackupError(DBFZRaidError):
    """Raised when backup operations fail."""
    pass


class PatchError(DBFZRaidError):
    """Raised when binary patching fails."""
    pass


class EACError(DBFZRaidError):
    """Raised when EAC operations fail."""
    pass


class ShortcutError(DBFZRaidError):
    """Raised when shortcut creation fails."""
    pass


class AESKeyError(DBFZRaidError):
    """Raised when AES key validation fails or key is unavailable."""
    pass


class PakError(DBFZRaidError):
    """Raised when pak file operations fail."""
    pass
