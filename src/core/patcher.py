"""Binary patching engine for DBFZ executable."""

from pathlib import Path
from typing import Any, Dict, Tuple
from utils.errors import PatchError
from utils.logger import logger


class BinaryPatcher:
    """Handles binary pattern matching and patching for DBFZ executable."""

    @staticmethod
    def replace_pattern(exe_data: bytearray, pattern: str, new_bytes: bytes) -> int:
        """
        Scan for hex pattern and replace with new bytes.

        Args:
            exe_data: Full executable as mutable bytearray
            pattern: Space-separated hex pattern (e.g., "8B 81 C4 53 1D 00")
                    Supports "??" wildcard for any byte
            new_bytes: Replacement bytes

        Returns:
            Offset where pattern was found and replaced, or -1 if not found
        """
        # Split pattern into individual bytes
        pattern_bytes = pattern.split(' ')
        pattern_len = len(pattern_bytes)

        # Scan through executable
        for i in range(len(exe_data) - pattern_len + 1):
            found = True

            # Check if pattern matches at current position
            for j, pattern_byte in enumerate(pattern_bytes):
                # Wildcard matches any byte
                if pattern_byte == "??":
                    continue

                # Check if byte matches
                if int(pattern_byte, 16) != exe_data[i + j]:
                    found = False
                    break

            # If pattern found, replace and return offset
            if found:
                exe_data[i:i + len(new_bytes)] = new_bytes
                logger.info(f"Pattern '{pattern}' found and replaced at offset 0x{i:X}")
                return i

        # Pattern not found
        logger.warning(f"Pattern '{pattern}' not found in executable")
        return -1

    @staticmethod
    def create_raid_patches(raid_index: int) -> Dict[str, Tuple[str, bytes]]:
        """
        Generate all patch configurations for a given raid.

        Args:
            raid_index: Raid number (1-38)

        Returns:
            Dictionary with patch names as keys and (pattern, replacement) tuples:
            {
                'get_raid': (pattern, replacement_bytes),
                'set_raid': (pattern, replacement_bytes),
                'raid_status': (pattern, replacement_bytes)
            }
        """
        # Convert raid index to little-endian 4-byte format
        raid_bytes = raid_index.to_bytes(4, byteorder='little')

        # Patch 1: Get Raid
        # Original: mov eax, [rcx+0x1D53C4]
        # Replace: mov eax, <raid_index>; nop
        get_pattern = "8B 81 C4 53 1D 00"
        get_replacement = bytearray([0xB8]) + raid_bytes + bytearray([0x90])

        # Patch 2: Set Raid
        # Replace with: mov dword ptr [r8+0x04], <raid_index>; nop x3
        set_pattern = "66 0F 73 DA 08 66 41 0F 7E 50 04 F2 0F 11 4C"
        set_replacement = (
            bytearray([0x41, 0xC7, 0x40, 0x04]) +
            raid_bytes +
            bytearray([0x90, 0x90, 0x90])
        )

        # Patch 3: Raid Status
        # Original: cmp dword ptr [rax+0x10], 2; je +0x10
        # Replace: cmp eax, eax; nop x2 (always sets ZF, bypasses check)
        status_pattern = "83 78 10 02 74 10"
        status_replacement = bytearray([0x39, 0xC0, 0x90, 0x90])

        # Patch 4: FCup Popup Skip
        # Original: 45 33 C0 48 8D 8B C0 10 00 00 E8 66 B8 FA FF
        # Replace with: NOP the popup CALL to prevent FCup popup softlock
        skip_fcup_caller_pattern = "45 33 C0 48 8D 8B C0 10 00 00 E8 66 B8 FA FF"
        skip_fcup_caller_replacement = bytes([
            0x45, 0x33, 0xC0,                          # XOR R8D, R8D
            0x48, 0x8D, 0x8B, 0xC0, 0x10, 0x00, 0x00,  # LEA RCX, [RBX+0x10c0]
            0x90, 0x90, 0x90, 0x90, 0x90               # NOP x5 (skip popup CALL)
        ])

        # Patch 5: Partybattle Popup Skip
        # Original: E8 AC 5E FF FF 84 C0 74 2A -> CALL + TEST + JZ
        # Replace with: Change JZ to JMP to prevent Partybattle popup softlock
        skip_partybattle_pattern = "E8 AC 5E FF FF 84 C0 74 2A"
        skip_partybattle_replacement = bytes([
            0xE8, 0xAC, 0x5E, 0xFF, 0xFF,  # CALL FUN_14048ccb0
            0x84, 0xC0,                    # TEST AL, AL
            0xEB, 0x2A                     # JMP +0x2a (always skip)
        ])

        return {
            'get_raid': (get_pattern, bytes(get_replacement)),
            'set_raid': (set_pattern, bytes(set_replacement)),
            'raid_status': (status_pattern, bytes(status_replacement)),
            'skip_fcup_caller': (skip_fcup_caller_pattern, skip_fcup_caller_replacement),
            'skip_partybattle': (skip_partybattle_pattern, skip_partybattle_replacement),
        }

    def patch_executable(self, exe_path: Path, raid_index: int) -> Dict[str, Any]:
        """
        Apply all three patches to executable.

        Args:
            exe_path: Path to executable file to patch
            raid_index: Raid number (1-38)

        Returns:
            Dictionary with results:
            {
                'success': bool,
                'offsets': {'get_raid': int, 'set_raid': int, 'raid_status': int},
                'errors': [str]
            }

        Raises:
            PatchError: If file cannot be read/written
        """
        logger.info(f"Starting patch process for raid {raid_index} on {exe_path}")

        # Read executable
        try:
            exe_data = bytearray(exe_path.read_bytes())
        except Exception as e:
            logger.error(f"Failed to read executable: {e}")
            raise PatchError(f"Cannot read executable: {e}")

        # Generate patches
        patches = self.create_raid_patches(raid_index)
        results = {
            'success': True,
            'offsets': {},
            'errors': []
        }

        # Apply each patch
        for patch_name, (pattern, replacement) in patches.items():
            logger.info(f"Applying {patch_name} patch...")
            offset = self.replace_pattern(exe_data, pattern, replacement)

            if offset < 0:
                results['success'] = False
                error_msg = f"{patch_name} pattern scan failed"
                results['errors'].append(error_msg)
                logger.error(error_msg)
            else:
                results['offsets'][patch_name] = offset
                logger.info(f"{patch_name} patch applied at offset 0x{offset:X}")

        # Write patched executable if all patches succeeded
        if results['success']:
            try:
                exe_path.write_bytes(exe_data)
                logger.info(f"Patched executable written successfully")
            except Exception as e:
                logger.error(f"Failed to write patched executable: {e}")
                raise PatchError(f"Cannot write executable: {e}")
        else:
            logger.error("Patching failed - executable not modified")

        return results

    def verify_patch(self, exe_path: Path, raid_index: int) -> bool:
        """
        Verify that a patch was applied correctly by checking for raid bytes.

        Args:
            exe_path: Path to executable to verify
            raid_index: Expected raid number

        Returns:
            True if patch appears valid, False otherwise
        """
        try:
            exe_data = exe_path.read_bytes()
            raid_bytes = raid_index.to_bytes(4, byteorder='little')

            # Look for the raid bytes in the expected patch pattern
            # (after 0xB8 from the "mov eax, immediate" instruction)
            search_pattern = bytes([0xB8]) + raid_bytes + bytes([0x90])

            return search_pattern in exe_data
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
