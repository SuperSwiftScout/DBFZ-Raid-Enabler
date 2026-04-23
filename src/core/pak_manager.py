"""UE4 pak file operations for DBFZ RaidEventTable patching."""

import hashlib
import shutil
import struct
from pathlib import Path
from typing import Optional
from utils.errors import PakError
from utils.logger import logger

RAID_TABLE_ASSET = "RED/Content/Shared/StaticResource/TableData/Raid/RaidEventTable.uasset"
RAID_TABLE_UEXP  = "RED/Content/Shared/StaticResource/TableData/Raid/RaidEventTable.uexp"
PAK_MAGIC = b"\xE1\x12\x6F\x5A"
_FOOTER_READ_SIZE = 512


class PakManager:
    """Handles decryption, extraction, modification, and repacking of DBFZ pak files."""

    def __init__(self, game_root: Path, aes_key: bytes):
        self.pak_path = game_root / "RED" / "Content" / "Paks" / "pakchunk0-WindowsNoEditor.pak"
        self.aes_key = aes_key
        self.backup_path = self.pak_path.with_suffix(".pak.backup")

    def backup_pak(self) -> Path:
        """Create a backup of the original pak if one doesn't exist."""
        if self.backup_path.exists():
            logger.info(f"Pak backup already exists: {self.backup_path}")
            return self.backup_path
        try:
            shutil.copy2(self.pak_path, self.backup_path)
            logger.info(f"Pak backed up to: {self.backup_path}")
            return self.backup_path
        except Exception as e:
            raise PakError(f"Failed to back up pak file: {e}")

    def restore_pak(self) -> bool:
        """Restore the original pak from backup."""
        if not self.backup_path.exists():
            raise PakError("No pak backup found. Cannot restore.")
        try:
            shutil.copy2(self.backup_path, self.pak_path)
            logger.info("Pak restored from backup")
            return True
        except Exception as e:
            raise PakError(f"Failed to restore pak from backup: {e}")

    def apply_custom_raid(self, battles, raid_slot: int = 38):
        """Extract the RaidEventTable uasset+uexp, patch with custom raid data, and reinject."""
        from core.uasset_editor import UAssetEditor

        uasset_bytes = self._extract_file(RAID_TABLE_ASSET)
        uexp_bytes   = self._extract_file(RAID_TABLE_UEXP)
        editor = UAssetEditor(uasset_bytes, uexp_bytes)
        modified_uexp = editor.apply_custom_raid(battles, raid_slot)
        self._inject_file(RAID_TABLE_UEXP, modified_uexp)
        modified_uasset = editor.get_modified_uasset(len(modified_uexp))
        self._inject_file(RAID_TABLE_ASSET, modified_uasset)
        logger.info(f"Custom raid applied to slot {raid_slot}")

    def extract_raid_table(self) -> bytes:
        """Extract the raw RaidEventTable uasset bytes (header only)."""
        return self._extract_file(RAID_TABLE_ASSET)

    def inject_raid_table(self, modified_asset: bytes):
        """Reinject a modified RaidEventTable uasset."""
        self._inject_file(RAID_TABLE_ASSET, modified_asset)

    def _extract_file(self, asset_path: str) -> bytes:
        try:
            from Crypto.Cipher import AES

            footer = self._read_footer()
            index_offset, index_size, pak_version = self._parse_footer(footer)
            logger.info(f"Pak index at 0x{index_offset:X}, size {index_size}")

            encrypted_index = self._read_at(index_offset, index_size)
            cipher = AES.new(self.aes_key, AES.MODE_ECB)
            index_data = cipher.decrypt(self._pad(encrypted_index))[:index_size]

            entry = self._find_asset_in_index(index_data, asset_path, pak_version)
            if entry is None:
                raise PakError(f"{asset_path} not found in pak index.")

            file_offset, file_size, uncompressed_size, is_encrypted, compression_method, local_header_size, _, blocks, _entry_pos = entry
            logger.info(
                f"Entry ({asset_path}): file_offset=0x{file_offset:X} file_size={file_size} "
                f"uncompressed_size={uncompressed_size} compression={compression_method} "
                f"encrypted={is_encrypted} local_header={local_header_size} blocks={len(blocks)}"
            )
            if blocks:
                logger.info(f"Block[0]: 0x{blocks[0][0]:X} -> 0x{blocks[0][1]:X} ({blocks[0][1]-blocks[0][0]} bytes)")

            if compression_method != 0:
                import zlib
                logger.info(f"Decompressing {len(blocks)} blocks (method={compression_method})")
                raw = bytearray()
                for bstart, bend in blocks:
                    bsize = bend - bstart
                    read_size = ((bsize + 15) // 16) * 16 if is_encrypted else bsize
                    block_data = self._read_at(bstart, read_size)
                    if is_encrypted:
                        cipher = AES.new(self.aes_key, AES.MODE_ECB)
                        block_data = cipher.decrypt(block_data)[:bsize]
                    raw.extend(zlib.decompress(block_data))
                result = bytes(raw)[:uncompressed_size]
                logger.info(f"Decompressed {len(result)} bytes from {asset_path}")
                return result

            data_offset = file_offset + local_header_size
            raw = self._read_at(data_offset, file_size)
            if is_encrypted:
                cipher = AES.new(self.aes_key, AES.MODE_ECB)
                raw = cipher.decrypt(self._pad(raw))[:file_size]
            return raw

        except PakError:
            raise
        except Exception as e:
            raise PakError(f"Failed to extract {asset_path}: {e}")

    def _inject_file(self, asset_path: str, modified: bytes):
        """
        Recompress (if needed) and inject a modified file back into the pak in-place.
        """
        try:
            from Crypto.Cipher import AES

            footer = self._read_footer()
            index_offset, index_size, pak_version = self._parse_footer(footer)

            encrypted_index = self._read_at(index_offset, index_size)
            cipher = AES.new(self.aes_key, AES.MODE_ECB)
            index_data = cipher.decrypt(self._pad(encrypted_index))[:index_size]

            entry = self._find_asset_in_index(index_data, asset_path, pak_version)
            if entry is None:
                raise PakError(f"{asset_path} not found in pak index.")

            file_offset, file_size, uncompressed_size, is_encrypted, compression_method, local_header_size, compression_block_size, blocks, entry_pos = entry

            if compression_method != 0:
                import zlib
                if compression_method != 1:
                    raise PakError(
                        f"Unsupported compression method {compression_method}; only zlib (1) is supported."
                    )
                logger.info(f"Recompressing {len(blocks)} blocks (block_size={compression_block_size})")
                for i, (bstart, bend) in enumerate(blocks):
                    original_space = bend - bstart
                    chunk_start = i * compression_block_size
                    chunk = modified[chunk_start:chunk_start + compression_block_size]
                    compressed = self._compress_to_fit(chunk, original_space)
                    if compressed is None:
                        raise PakError(
                            f"Block {i} cannot be compressed to fit in original space "
                            f"({original_space} bytes) with any available compressor."
                        )
                    payload = compressed + b"\x00" * (original_space - len(compressed))
                    if is_encrypted:
                        cipher = AES.new(self.aes_key, AES.MODE_ECB)
                        payload = cipher.encrypt(self._pad(payload))[:original_space]
                    self._write_at(bstart, payload)
                if len(modified) != uncompressed_size:
                    logger.info(
                        f"Updating pak index: uncompressed_size {uncompressed_size} → {len(modified)}"
                    )
                    self._update_index_uncompressed_size(
                        index_offset, index_size, entry_pos, len(modified)
                    )
                logger.info(f"{asset_path} (compressed) injected into pak successfully")
                return

            data_offset = file_offset + local_header_size
            payload = modified
            if is_encrypted:
                cipher = AES.new(self.aes_key, AES.MODE_ECB)
                payload = cipher.encrypt(self._pad(modified))[:file_size]

            self._write_at(data_offset, payload)
            logger.info(f"{asset_path} injected into pak successfully")

        except PakError:
            raise
        except Exception as e:
            raise PakError(f"Failed to inject {asset_path}: {e}")

    def _read_footer(self) -> bytes:
        try:
            with open(self.pak_path, 'rb') as f:
                f.seek(-_FOOTER_READ_SIZE, 2)
                return f.read(_FOOTER_READ_SIZE)
        except Exception as e:
            raise PakError(f"Failed to read pak footer: {e}")

    def _read_at(self, offset: int, size: int) -> bytes:
        try:
            with open(self.pak_path, 'rb') as f:
                f.seek(offset)
                return f.read(size)
        except Exception as e:
            raise PakError(f"Failed to read {size} bytes at 0x{offset:X}: {e}")

    def _write_at(self, offset: int, data: bytes):
        try:
            with open(self.pak_path, 'r+b') as f:
                f.seek(offset)
                f.write(data)
        except Exception as e:
            raise PakError(f"Failed to write {len(data)} bytes at 0x{offset:X}: {e}")

    def _parse_footer(self, footer: bytes) -> tuple[int, int, int]:
        magic_pos = footer.rfind(PAK_MAGIC)
        if magic_pos == -1:
            raise PakError("Pak magic not found in footer — invalid pak file.")
        pak_version  = struct.unpack_from("<I", footer, magic_pos + 4)[0]
        index_offset = struct.unpack_from("<q", footer, magic_pos + 8)[0]
        index_size   = struct.unpack_from("<q", footer, magic_pos + 16)[0]
        logger.info(f"Pak version {pak_version}")
        return index_offset, index_size, pak_version

    def _find_asset_in_index(self, index_data: bytes, asset_path: str, pak_version: int = 3) -> Optional[tuple]:
        pos = 0
        try:
            mount_len = struct.unpack_from("<i", index_data, pos)[0]
            pos += 4
            if mount_len > 0:
                pos += mount_len
            elif mount_len < 0:
                pos += (-mount_len) * 2

            file_count = struct.unpack_from("<I", index_data, pos)[0]
            pos += 4

            for _ in range(file_count):
                name_len = struct.unpack_from("<i", index_data, pos)[0]
                pos += 4
                if name_len > 0:
                    filename = index_data[pos:pos + name_len - 1].decode("utf-8", errors="replace")
                    pos += name_len
                elif name_len < 0:
                    byte_len = (-name_len) * 2
                    filename = index_data[pos:pos + byte_len - 2].decode("utf-16-le", errors="replace")
                    pos += byte_len
                else:
                    continue

                entry_pos          = pos
                file_offset        = struct.unpack_from("<q", index_data, pos)[0]
                file_size          = struct.unpack_from("<q", index_data, pos + 8)[0]
                uncompressed_size  = struct.unpack_from("<q", index_data, pos + 16)[0]
                compression_method = struct.unpack_from("<i", index_data, pos + 24)[0]
                entry_end = pos + 48

                blocks = []
                if compression_method != 0:
                    block_count = struct.unpack_from("<I", index_data, entry_end)[0]
                    for bi in range(block_count):
                        bstart = struct.unpack_from("<q", index_data, entry_end + 4 + bi * 16)[0]
                        bend   = struct.unpack_from("<q", index_data, entry_end + 4 + bi * 16 + 8)[0]
                        if pak_version >= 7:
                            bstart += file_offset
                            bend   += file_offset
                        blocks.append((bstart, bend))
                    entry_end += 4 + block_count * 16

                is_encrypted           = bool(index_data[entry_end]) if entry_end < len(index_data) else False
                local_header_size      = (entry_end - pos) + 5
                compression_block_size = struct.unpack_from("<I", index_data, entry_end + 1)[0] if entry_end + 1 < len(index_data) else 0
                pos = entry_end + 5

                if asset_path.lower() in filename.lower() or filename.lower() in asset_path.lower():
                    logger.info(f"Found asset: {filename}")
                    return (file_offset, file_size, uncompressed_size, is_encrypted,
                            compression_method, local_header_size, compression_block_size, blocks,
                            entry_pos)

        except Exception as e:
            logger.error(f"Index parse error at pos {pos}: {e}")

        return None

    def _update_index_uncompressed_size(
        self, index_offset: int, index_size: int, entry_pos: int, new_uncompressed_size: int
    ):
        from Crypto.Cipher import AES
        padded_size = ((index_size + 15) // 16) * 16
        encrypted_index = self._read_at(index_offset, padded_size)
        cipher = AES.new(self.aes_key, AES.MODE_ECB)
        index_data = bytearray(cipher.decrypt(encrypted_index)[:padded_size])

        struct.pack_into('<q', index_data, entry_pos + 16, new_uncompressed_size)
        new_hash = hashlib.sha1(bytes(index_data[:index_size])).digest()

        cipher = AES.new(self.aes_key, AES.MODE_ECB)
        self._write_at(index_offset, cipher.encrypt(bytes(index_data)))

        with open(self.pak_path, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
        footer = self._read_footer()
        magic_pos = footer.rfind(PAK_MAGIC)
        if magic_pos == -1:
            raise PakError("Pak magic not found in footer when updating index SHA1 hash")
        hash_file_offset = file_size - _FOOTER_READ_SIZE + magic_pos + 24
        self._write_at(hash_file_offset, new_hash)

        logger.info(
            f"Pak index entry {entry_pos}: uncompressed_size \u2192 {new_uncompressed_size}; "
            f"index SHA1 updated at 0x{hash_file_offset:X}"
        )

    @staticmethod
    def _compress_to_fit(data: bytes, max_size: int) -> Optional[bytes]:
        """Return zlib-compressed data fitting within max_size, or None if impossible."""
        import zlib

        best: Optional[bytes] = None
        strategies = (
            zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_FIXED,
            zlib.Z_RLE, zlib.Z_HUFFMAN_ONLY,
        )
        for wbits in range(15, 8, -1):
            for level in range(9, 0, -1):
                for strategy in strategies:
                    for memlevel in (9, 8):
                        try:
                            c = zlib.compressobj(level=level, method=zlib.DEFLATED,
                                                 wbits=wbits, memLevel=memlevel, strategy=strategy)
                            candidate = c.compress(data) + c.flush()
                        except Exception:
                            continue
                        if best is None or len(candidate) < len(best):
                            best = candidate
                        if len(candidate) <= max_size:
                            return candidate

        try:
            import zopfli.zlib  # type: ignore
            candidate = zopfli.zlib.compress(data)
            if best is None or len(candidate) < len(best):
                best = candidate
            if len(candidate) <= max_size:
                return candidate
        except ImportError:
            pass

        if best is not None:
            logger.warning(
                f"Best compression achieved {len(best)} bytes, need ≤{max_size}. "
                f"Install 'zopfli' (pip install zopfli) for better compression."
            )
        return None

    @staticmethod
    def _pad(data: bytes, block_size: int = 16) -> bytes:
        r = len(data) % block_size
        return data if r == 0 else data + b"\x00" * (block_size - r)
