import random
import hashlib
from typing import List
from light_map.common_types import NamingStyle


# Name lists
NAMES_AMERICAN = [
    "Adam", "Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hank", "Ivy",
    "Jack", "Kelly", "Liam", "Mia", "Noah", "Olivia", "Paul", "Quinn", "Rose", "Sam",
    "Tom", "Ursula", "Victor", "Wendy", "Xavier", "Yvonne", "Zack"
]

NAMES_SCI_FI = [
    "Aethel", "Balthazar", "Calyx", "Drexel", "Epsilon", "Faze", "Gideon", "Hyperion", "Ion", "Juno",
    "Kael", "Lyra", "Mimas", "Nova", "Orion", "Phaedra", "Quasar", "Rigel", "Sirius", "Triton",
    "Umbriel", "Vega", "Warp", "Xeno", "Ymir", "Zion"
]

NAMES_FANTASY = [
    "Aragorn", "Boromir", "Celeborn", "Dain", "Elrond", "Faramir", "Galadriel", "Hama", "Isildur", "Jorin",
    "Kili", "Legolas", "Mithrandir", "Narya", "Oin", "Peregrin", "Radagast", "Saruman", "Theoden", "Ulmo",
    "Varda", "Wulf", "Xar", "Yavanna", "Zirak"
]


def generate_token_name(
    aruco_id: int,
    map_name: str = "",
    style: NamingStyle = NamingStyle.SCI_FI
) -> str:
    """
    Generates a stable, temporary name for an unknown token based on the map name and ArUco ID.
    """
    if style == NamingStyle.NUMBERED:
        return f"Unknown Token #{aruco_id}"

    # Create a stable seed using map name and ArUco ID
    seed_str = f"{map_name}:{aruco_id}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(seed)

    if style == NamingStyle.AMERICAN:
        name_list = NAMES_AMERICAN
    elif style == NamingStyle.SCI_FI:
        name_list = NAMES_SCI_FI
    elif style == NamingStyle.FANTASY:
        name_list = NAMES_FANTASY
    else:
        return f"Unknown Token #{aruco_id}"

    base_name = rng.choice(name_list)
    
    # Optional: add a suffix to ensure more uniqueness if needed, 
    # but for now just picking from the list is fine as per requirements.
    # To avoid collisions with the same name, we could use the ArUco ID as well.
    return f"{base_name} ({aruco_id})"
