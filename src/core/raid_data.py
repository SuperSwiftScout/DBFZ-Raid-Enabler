"""Raid boss data and lookup functions."""

# Character code to name mapping
CHARACTER_CODES = {
    "AAA": "(Empty Slot)",
    "AEN": "Android 18",
    "ASN": "Android 16",
    "AVP": "Android 17",
    "BDN": "Bardock",
    "BRS": "Broly (Z)",
    "BSN": "Beerus",
    "BUK": "Kid Buu",
    "BUN": "Majin Buu",
    "CEN": "Cell",
    "CLF": "Cooler",
    "EST": "Broly (DBS)",
    "FRN": "Frieza",
    "GBR": "Goku Black (SS Rosé)",
    "GFF": "Gogeta (SS4)",
    "GHT": "Gohan (Teen)",
    "GHU": "Gohan (Adult)",
    "GKB": "Goku Black",
    "GKN": "Goku (Saiyan Saga)",
    "GKS": "Goku (SS)",
    "GNN": "Captain Ginyu",
    "GTL": "Gotenks",
    "HTN": "Hit",
    "JNN": "Janemba",
    "JRN": "Jiren",
    "KFS": "Kefla",
    "KRN": "Krillin",
    "MGS": "Goku (Ultra Instinct)",
    "MTN": "Master Roshi",
    "NHY": "Gogeta (SSGSS)",
    "NPN": "Nappa",
    "OSM": "Super Baby 2",
    "PCN": "Piccolo",
    "SGN": "Goku (SSGSS)",
    "TNN": "Tien",
    "TON": "Android 21",
    "TOP": "Android 21 (Lab Coat)",
    "TRS": "Trunks",
    "VDN": "Videl",
    "VGB": "Vegeta (SSGSS)",
    "VGN": "Vegeta (Saiyan Saga)",
    "VGS": "Vegeta (SS)",
    "VTB": "Vegito (SSGSS)",
    "YMN": "Yamcha",
    "ZMB": "Zamasu (Fused)",
}

# Main boss character for each raid (from BattleNo 6, Char1)
RAID_MAIN_BOSS = {
    1: "FRN",
    2: "CEN",
    3: "BUK",
    4: "HTN",
    5: "BSN",
    6: "TON",
    7: "YMN",
    8: "BRS",
    9: "BDN",
    10: "VTB",
    11: "ZMB",
    12: "GKN",
    13: "VGN",
    14: "AVP",
    15: "CLF",
    16: "JRN",
    17: "VDN",
    18: "SGN",
    19: "JNN",
    20: "NHY",
    21: "EST",
    22: "TRS",
    23: "GBR",
    24: "GTL",
    25: "GHU",
    26: "GHU",
    27: "GKS",
    28: "PCN",
    29: "KRN",
    30: "GKN",
    31: "BSN",
    32: "KFS",
    33: "MGS",
    34: "MTN",
    35: "GFF",
    36: "OSM",
    37: "TOP",
    38: "GFF",
}

# All characters that appear in each raid (derived from RaidEventTable)
RAID_CHARACTERS = {
    1: ["FRN", "GNN", "NPN"],
    2: ["CEN"],
    3: ["BUK"],
    4: ["HTN"],
    5: ["BSN", "GKB", "VGB"],
    6: ["AEN", "ASN", "BUK", "BUN", "CEN", "FRN", "GKS", "TNN", "TON", "VGS", "YMN"],
    7: ["KRN", "TNN", "YMN"],
    8: ["BRS"],
    9: ["BDN"],
    10: ["GKB", "TRS", "VGB", "VGN", "VTB"],
    11: ["GBR", "ZMB"],
    12: ["GKN", "KRN", "PCN"],
    13: ["NPN", "VGN"],
    14: ["AEN", "ASN", "AVP"],
    15: ["CLF", "FRN"],
    16: ["JRN"],
    17: ["GHU", "GTL", "VDN"],
    18: ["GKB", "GKN", "GKS", "SGN"],
    19: ["BUK", "CEN", "FRN", "JNN"],
    20: ["GKB", "GKN", "GKS", "NHY", "VGB", "VGN", "VGS", "VTB"],
    21: ["BRS", "EST", "FRN"],
    22: ["AEN", "AVP", "CEN", "FRN", "GBR", "TRS", "ZMB"],
    23: ["GBR", "ZMB"],
    24: ["GKS", "GTL", "PCN"],
    25: ["GHT", "GHU", "GTL", "TRS"],
    26: ["ASN", "GHT", "GHU", "GKS", "PCN", "VDN"],
    27: ["AEN", "AVP", "FRN", "GHU", "GKB", "GKS", "KRN", "PCN", "TNN", "VGB"],
    28: ["GHT", "GKN", "GKS", "KRN", "PCN"],
    29: ["GKN", "KRN", "TNN", "YMN"],
    30: ["GKN", "KRN", "PCN", "TNN", "YMN"],
    31: ["BSN", "GBR", "GKB", "VGB", "VTB", "ZMB"],
    32: ["HTN", "KFS"],
    33: ["BSN", "GKB", "GKN", "JRN", "MGS"],
    34: ["BUK", "CEN", "GBR", "GHT", "GHU", "GKB", "GKN", "GKS", "KRN", "MTN", "NHY", "SGN", "VTB", "YMN"],
    35: ["GFF", "GTL", "KFS", "NHY", "VTB", "ZMB"],
    36: ["AEN", "BDN", "BRS", "GHU", "KRN", "OSM", "TRS", "VDN"],
    37: ["AEN", "ASN", "AVP", "CEN", "TON", "TOP"],
    38: ["BRS", "BSN", "BUK", "CEN", "CLF", "EST", "FRN", "GFF", "GKS", "HTN", "JNN", "JRN", "MGS", "NHY", "TRS", "VGB", "VGS", "VTB", "ZMB"],
}

RAID_BOSSES = {
    1: "The Emperor Strikes Back",
    2: "The Cell Games Main Event",
    3: "The Might of a Majin",
    4: "Living Legend of Universe 6",
    5: "Universe 7's God of Destruction",
    6: "Ominous Android",
    7: "Leading the Pack",
    8: "Heated, Furious, Ultimate Battle",
    9: "Father of Goku",
    10: "Future Freedom Fighters",
    11: "Foes from a Fearsome Future",
    12: "Pushing Past the Limits",
    13: "Savage Saiyan Showdown",
    14: "Android Assault",
    15: "Cooler's Revenge",
    16: "Beyond the Gods",
    17: "Videl's Training",
    18: "Goku Gauntlet",
    19: "From the Depths of Hell",
    20: "The Ultimate Fusion",
    21: "Power Incarnate",
    22: "Defiant in the Face of Despair",
    23: "A God in Mortal Form",
    24: "Fusion is Child's Play!",
    25: "Defenders of the Future",
    26: "Warm-Hearted Warrior",
    27: "The Best of Universe 7",
    28: "A Once Fearsome Foe",
    29: "Float Like a Crane, Sting Like a... Turtle?",
    30: "Earth's Mightiest",
    31: "The Power of a God",
    32: "First in Female Fusion",
    33: "God Among Gods",
    34: "The Greatest Kamehameha",
    35: "Facing the Fusions",
    36: "Trouble with a Tuffle",
    37: "Elegant Androids",
    38: "Ultimate Zenkai Battle"
}


def get_raid_name(raid_index: int) -> str:
    """
    Get raid boss name by index.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        Raid boss name or "Unknown Raid" if not found
    """
    return RAID_BOSSES.get(raid_index, f"Unknown Raid {raid_index}")


def get_all_raids() -> list[tuple[int, str]]:
    """
    Get all raids as (index, name) tuples for UI display.

    Returns:
        List of (index, name) tuples sorted by index
    """
    return [(idx, name) for idx, name in sorted(RAID_BOSSES.items())]


def is_valid_raid_index(raid_index: int) -> bool:
    """
    Check if raid index is valid.

    Args:
        raid_index: Raid number to validate

    Returns:
        True if valid (1-38), False otherwise
    """
    return raid_index in RAID_BOSSES


def get_character_name(code: str) -> str:
    """
    Get character name from code.

    Args:
        code: 3-letter character code (e.g., "FRN")

    Returns:
        Character name or the code if unknown
    """
    return CHARACTER_CODES.get(code, code)


def get_raid_boss(raid_index: int) -> str:
    """
    Get the main boss character name for a raid.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        Boss character name
    """
    code = RAID_MAIN_BOSS.get(raid_index, "???")
    return get_character_name(code)


def get_raid_boss_code(raid_index: int) -> str:
    """
    Get the main boss character code for a raid.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        Boss character code (e.g., "FRN")
    """
    return RAID_MAIN_BOSS.get(raid_index, "???")


def get_raid_display(raid_index: int) -> str:
    """
    Get formatted raid display string with boss info.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        Formatted string like "1: The Emperor Strikes Back (Frieza)"
    """
    name = get_raid_name(raid_index)
    boss = get_raid_boss(raid_index)
    return f"{raid_index}: {name} ({boss})"


def get_raid_characters(raid_index: int) -> list[str]:
    """
    Get all character names that appear in a raid.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        List of character names
    """
    codes = RAID_CHARACTERS.get(raid_index, [])
    return [get_character_name(code) for code in codes]


def get_raid_characters_str(raid_index: int) -> str:
    """
    Get all characters in a raid as a comma-separated string.

    Args:
        raid_index: Raid number (1-38)

    Returns:
        Comma-separated character names
    """
    return ", ".join(get_raid_characters(raid_index))


def get_all_raids_with_bosses() -> list[tuple[int, str, str, str]]:
    """
    Get all raids as (index, name, boss, characters) tuples for UI display.

    Returns:
        List of (index, raid_name, boss_name, characters_str) tuples sorted by index
    """
    return [
        (idx, name, get_raid_boss(idx), get_raid_characters_str(idx))
        for idx, name in sorted(RAID_BOSSES.items())
    ]
