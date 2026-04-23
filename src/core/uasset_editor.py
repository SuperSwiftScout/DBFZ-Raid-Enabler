"""UE4 DataTable uasset editor for RaidEventTable patching."""

import struct
from typing import Dict, List, Optional
from utils.errors import PakError
from utils.logger import logger
from core.custom_raid import RaidBattle

UE4_MAGIC = 0x9E2A83C1

# UE4 versioning constants
VER_UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 503
VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 488
VER_UE4_64BIT_EXPORTMAP_SERIAL_NUMBERS = 506

# Generous upper bound for one DataTable row (~12 properties × ~37 bytes each)
_ROW_WINDOW = 600


class _Reader:
    """Sequential binary reader with position tracking."""

    def __init__(self, data: bytearray, pos: int = 0):
        self.data = data
        self.pos = pos

    def int32(self) -> int:
        v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def uint32(self) -> int:
        v = struct.unpack_from('<I', self.data, self.pos)[0]
        self.pos += 4
        return v

    def fstring(self) -> str:
        length = self.int32()
        if length == 0:
            return ''
        if length < 0:
            byte_len = (-length) * 2
            s = self.data[self.pos:self.pos + byte_len - 2].decode('utf-16-le', errors='replace')
            self.pos += byte_len
            return s
        s = self.data[self.pos:self.pos + length - 1].decode('utf-8', errors='replace')
        self.pos += length
        return s

    def skip(self, n: int):
        self.pos += n


class UAssetEditor:
    """
    Patches a UE4 DataTable in place.

    The uasset contains the package header and name table.
    The uexp contains the serialized DataTable rows.
    Only modifies existing field values — output uexp is always the same size as input.
    """

    def __init__(self, uasset_bytes: bytes, uexp_bytes: bytes):
        self.data = bytearray(uasset_bytes)
        self.uexp_data = bytearray(uexp_bytes)
        self.names: List[str] = []
        self._name_to_idx: Dict[str, int] = {}
        self._ue4_version: int = 0
        self._serial_size_offset: int = 0
        self._serial_size_is_int64: bool = False
        self._parse_header()
        self._parse_name_table()

    def _parse_header(self):
        r = _Reader(self.data)

        magic = r.uint32()
        if magic != UE4_MAGIC:
            raise PakError(f"Not a valid UE4 asset (magic={magic:#010x})")

        legacy = r.int32()
        if legacy != -4:
            r.skip(4)  # LegacyUE3Version

        self._ue4_version = r.int32()
        r.skip(4)  # FileVersionLicensee

        if legacy <= -2:
            n = r.int32()
            for _ in range(n):
                if legacy == -2:
                    r.skip(4)
                elif legacy <= -6:
                    r.skip(20)
                    r.fstring()
                else:
                    r.skip(20)

        r.skip(4)    # TotalHeaderSize
        r.fstring()  # FolderName
        r.skip(4)    # PackageFlags

        self._name_count = r.int32()
        self._name_offset = r.int32()

        if self._ue4_version == 0 or self._ue4_version >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES:
            r.skip(8)

        _export_count = r.int32()
        export_offset = r.int32()

        has_template = self._ue4_version == 0 or self._ue4_version >= VER_UE4_TemplateIndex_IN_COOKED_EXPORTS
        pre_serial = 4 + 4 + (4 if has_template else 0) + 4 + 8 + 4
        self._serial_size_offset = export_offset + pre_serial
        self._serial_size_is_int64 = (
            self._ue4_version != 0 and self._ue4_version >= VER_UE4_64BIT_EXPORTMAP_SERIAL_NUMBERS
        )

        logger.debug(f"UE4 asset version {self._ue4_version}, name table at {self._name_offset:#x} ({self._name_count} entries)")
        logger.debug(f"Export at {export_offset:#x}; SerialSize at {self._serial_size_offset:#x} ({'int64' if self._serial_size_is_int64 else 'int32'})")
        if self._name_offset < 0 or self._name_offset >= len(self.data):
            raise PakError(
                f"Name table offset {self._name_offset} is out of range for asset of size {len(self.data)}. "
                f"Header bytes: {bytes(self.data[:64]).hex()}"
            )

    def _parse_name_table(self):
        r = _Reader(self.data, self._name_offset)
        has_hashes = self._ue4_version == 0 or self._ue4_version >= 504
        for _ in range(self._name_count):
            name = r.fstring()
            if has_hashes:
                r.skip(4)
            self.names.append(name)
        self._name_to_idx = {n: i for i, n in enumerate(self.names)}
        logger.debug(f"Parsed {len(self.names)} name table entries")

    def apply_custom_raid(self, battles: List[RaidBattle], raid_slot: int = 38) -> bytes:
        """Patch all DataTable rows for raid_slot. Returns modified uexp bytes."""
        if len(battles) != 7:
            raise PakError(f"Expected 7 battles, got {len(battles)}")

        event_id_idx  = self._require('EventID')
        battle_no_idx = self._require('BattleNo')
        int_prop_idx  = self._require('IntProperty')
        str_prop_idx  = self._require('StrProperty')

        field_idx = {
            f: self._require(f)
            for f in ('Char1', 'Char2', 'Char3', 'Lv1', 'Lv2', 'Lv3', 'Skill_Num', 'BG', 'BGM')
        }

        row_positions = self._find_event_id_rows(event_id_idx, int_prop_idx, raid_slot)
        if len(row_positions) != 7:
            raise PakError(
                f"Expected 7 rows for raid slot {raid_slot}, found {len(row_positions)}. "
                f"The asset structure may have changed."
            )

        all_patches = []  # list of (offset, old_bytes, new_bytes)

        for row_start in row_positions:
            row_end = row_start + _ROW_WINDOW

            battle_no = self._read_int_prop(row_start, row_end, battle_no_idx, int_prop_idx)
            if battle_no is None:
                raise PakError(f"Could not read BattleNo in row at {row_start:#x}")
            if not 0 <= battle_no < 7:
                raise PakError(f"Unexpected BattleNo {battle_no} in row at {row_start:#x}")

            b = battles[battle_no]

            for fname, val in [('Lv1', b.level), ('Lv2', b.level), ('Lv3', b.level),
                                ('Skill_Num', b.skill_num)]:
                vpos = self._find_prop_value_pos(row_start, row_end, field_idx[fname], int_prop_idx)
                if vpos is None:
                    raise PakError(f"IntProperty '{fname}' not found in row at {row_start:#x}")
                old = bytes(self.uexp_data[vpos:vpos + 4])
                new = struct.pack('<i', val)
                all_patches.append((vpos, old, new))

            # Str properties
            for fname, val in [('Char1', b.char1), ('Char2', b.char2), ('Char3', b.char3),
                                ('BG', b.background), ('BGM', b.bgm)]:
                all_patches.extend(
                    self._collect_str_patches(row_start, row_end, field_idx[fname], str_prop_idx, val)
                )

        all_patches.sort(key=lambda p: p[0], reverse=True)
        for offset, old, new in all_patches:
            actual = bytes(self.uexp_data[offset:offset + len(old)])
            if actual != old:
                raise PakError(
                    f"Patch sanity check failed at {offset:#x}: "
                    f"expected {old.hex()}, got {actual.hex()}"
                )
            self.uexp_data = (
                self.uexp_data[:offset] + bytearray(new) + self.uexp_data[offset + len(old):]
            )

        logger.info(
            f"Patched {len(row_positions)} rows for raid slot {raid_slot} "
            f"(uexp size: {len(self.uexp_data)} bytes)"
        )
        return bytes(self.uexp_data)

    def get_modified_uasset(self, new_uexp_size: int) -> bytes:
        """Return uasset bytes with the export SerialSize updated to match new_uexp_size."""
        UEXP_TRAILING_TAG = 4
        new_serial = new_uexp_size - UEXP_TRAILING_TAG
        fmt = '<q' if self._serial_size_is_int64 else '<i'
        uasset = bytearray(self.data)
        old_serial = struct.unpack_from(fmt, uasset, self._serial_size_offset)[0]
        struct.pack_into(fmt, uasset, self._serial_size_offset, new_serial)
        logger.info(
            f"uasset SerialSize updated ({'int64' if self._serial_size_is_int64 else 'int32'}): "
            f"{old_serial} \u2192 {new_serial} at offset 0x{self._serial_size_offset:X}"
        )
        return bytes(uasset)

    def _require(self, name: str) -> int:
        """Return name table index, raising PakError if absent."""
        idx = self._name_to_idx.get(name)
        if idx is None:
            prop_names = [n for n in self.names if 'roperty' in n]
            logger.error(f"Required name '{name}' not found. Available *Property names: {prop_names}")
            raise PakError(f"Required name '{name}' not found in asset name table")
        return idx

    def _find_event_id_rows(self, event_id_idx: int, int_prop_idx: int, value: int) -> List[int]:
        """Return byte offsets of all EventID == value IntProperty tags in uexp."""
        pattern = (
            struct.pack('<ii', event_id_idx, 0) +   # FName EventID
            struct.pack('<ii', int_prop_idx, 0) +    # FName IntProperty
            struct.pack('<i', 4) +                   # int32 size = 4
            struct.pack('<i', 0) +                   # int32 array_index = 0
            struct.pack('<B', 0) +                   # uint8 HasPropertyGuid = 0
            struct.pack('<i', value)                 # int32 value
        )
        positions = []
        search = bytes(self.uexp_data)
        pos = 0
        while True:
            idx = search.find(pattern, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
        return positions

    def _find_prop_value_pos(
        self,
        row_start: int,
        row_end: int,
        prop_name_idx: int,
        prop_type_idx: int,
    ) -> Optional[int]:
        """Return the byte offset of a tagged property's value within [row_start, row_end]."""
        search = (
            struct.pack('<ii', prop_name_idx, 0) +
            struct.pack('<ii', prop_type_idx, 0)
        )
        data_bytes = bytes(self.uexp_data)
        idx = data_bytes.find(search, row_start, row_end)
        if idx == -1:
            return None

        value_pos = idx + 24

        is_modern = self._ue4_version == 0 or self._ue4_version >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG
        if is_modern:
            if value_pos >= len(self.uexp_data):
                return None
            has_guid = self.uexp_data[value_pos]
            value_pos += 1
            if has_guid:
                value_pos += 16  # skip FGuid

        return value_pos

    def _read_int_prop(
        self,
        row_start: int,
        row_end: int,
        prop_name_idx: int,
        int_prop_idx: int,
    ) -> Optional[int]:
        pos = self._find_prop_value_pos(row_start, row_end, prop_name_idx, int_prop_idx)
        if pos is None:
            return None
        return struct.unpack_from('<i', self.uexp_data, pos)[0]

    def _collect_str_patches(self, row_start: int, row_end: int,
                              prop_name_idx: int, str_prop_idx: int,
                              new_value: str) -> list:
        """Return (offset, old_bytes, new_bytes) patch tuples for a StrProperty FString and its Size field."""
        tag_search = struct.pack('<ii', prop_name_idx, 0) + struct.pack('<ii', str_prop_idx, 0)
        tag_start = bytes(self.uexp_data).find(tag_search, row_start, row_end)
        if tag_start == -1:
            raise PakError(f"StrProperty (name_idx={prop_name_idx}) not found in row at {row_start:#x}")

        size_pos     = tag_start + 16
        has_guid_pos = tag_start + 24

        is_modern = self._ue4_version == 0 or self._ue4_version >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG
        if is_modern:
            has_guid  = self.uexp_data[has_guid_pos]
            fstring_pos = has_guid_pos + 1 + (16 if has_guid else 0)
        else:
            fstring_pos = has_guid_pos

        old_char_count = struct.unpack_from('<i', self.uexp_data, fstring_pos)[0]
        if old_char_count <= 0:
            raise PakError(f"Unexpected FString charCount {old_char_count} at {fstring_pos:#x}")

        old_fstring = bytes(self.uexp_data[fstring_pos:fstring_pos + 4 + old_char_count])
        new_encoded = new_value.encode('utf-8') + b'\x00'
        new_fstring = struct.pack('<i', len(new_encoded)) + new_encoded

        patches = []
        if old_fstring != new_fstring:
            patches.append((fstring_pos, old_fstring, new_fstring))
        old_size_bytes = bytes(self.uexp_data[size_pos:size_pos + 4])
        new_size_bytes = struct.pack('<i', 4 + len(new_encoded))
        if old_size_bytes != new_size_bytes:
            patches.append((size_pos, old_size_bytes, new_size_bytes))
        return patches

    def _write_int_prop(
        self,
        row_start: int,
        row_end: int,
        prop_name_idx: int,
        int_prop_idx: int,
        new_value: int,
    ):
        pos = self._find_prop_value_pos(row_start, row_end, prop_name_idx, int_prop_idx)
        if pos is None:
            raise PakError(f"IntProperty (name_idx={prop_name_idx}) not found in row at {row_start:#x}")
        struct.pack_into('<i', self.uexp_data, pos, new_value)
