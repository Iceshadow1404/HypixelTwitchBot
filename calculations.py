import constants
from utils import LevelingData


def _get_xp_for_target_level(leveling_data: LevelingData, target_level: int) -> float:
    """Calculates the total cumulative XP required to COMPLETE a target level.
    Uses the Catacombs XP table.
    Target level is 1-based (e.g., target_level=50 means completing level 50).
    """
    if not leveling_data['catacombs_xp']:
        print("[WARN][Calc] Catacombs XP table not loaded for _get_xp_for_target_level.")
        return float('inf') # Return infinity if data is missing

    xp_table = leveling_data['catacombs_xp']
    target_level_index = target_level - 1 # Convert 1-based level to 0-based index

    if target_level_index < 0:
        return 0.0 # Cannot complete level 0 or less

    # Ensure index doesn't go out of bounds for slicing
    max_index = len(xp_table)
    if target_level_index >= max_index:
         print(f"[WARN][Calc] Target level {target_level} exceeds Catacombs XP table length ({len(xp_table)}). Using XP for max level.")
         # Sum the entire table if target level is beyond max level
         total_xp = sum(xp_table)
         return float(total_xp)

    # Sum XP required for levels 1 through target_level (indices 0 through target_level_index)
    # Slicing [:index+1] goes up to and includes the index.
    total_xp = sum(xp_table[:target_level_index + 1])
    print(f"[DEBUG][Calc] XP to complete Level {target_level} (sum index 0 to {target_level_index}): {total_xp:,.0f}") # Added debug
    return float(total_xp)


def calculate_skill_level(leveling_data: LevelingData, xp: float, skill_name: str, member_data: dict | None = None) -> float:
    """Calculates the level of a skill based on XP, considering level caps and special skills."""
    if not leveling_data['xp_table']:
        return 0.0

    # Determine base max level (usually 50 or 60)
    base_max_level = leveling_data['level_caps'].get(skill_name, 50)
    xp_table_to_use = leveling_data['xp_table'] # Use standard XP table

    # Calculate effective max level considering special rules
    effective_max_level = base_max_level
    if skill_name == 'taming' and member_data:
        pets_data = member_data.get('pets_data', {}).get('pet_care', {})
        sacrificed_count = len(pets_data.get('pet_types_sacrificed', []))
        effective_max_level = 50 + min(sacrificed_count, 10) # Cap bonus at +10
    elif skill_name == 'farming' and member_data:
        jacobs_perks = member_data.get('jacobs_contest', {}).get('perks', {})
        farming_level_cap_bonus = jacobs_perks.get('farming_level_cap', 0)
        effective_max_level = 50 + farming_level_cap_bonus

    # Calculate total XP required for the effective max level
    total_xp_for_max = sum(xp_table_to_use[:effective_max_level]) # Sum only up to the effective cap

    # If XP meets or exceeds the requirement for the max level, return max level
    if xp >= total_xp_for_max:
        return float(effective_max_level)

    # Find level based on XP progression
    total_xp_required = 0
    level = 0
    # Iterate only up to the XP required for levels below the effective max
    for i, required_xp in enumerate(xp_table_to_use):
        if i >= effective_max_level: # Stop if we exceed the effective max level index
             break
        total_xp_required += required_xp
        if xp >= total_xp_required:
            level += 1
        else:
            # Calculate progress towards the next level
            current_level_xp = total_xp_required - required_xp
            next_level_xp_needed = required_xp
            if next_level_xp_needed > 0:
                progress = (xp - current_level_xp) / next_level_xp_needed
                # Ensure progress doesn't make level exceed effective max
                calculated_level = level + progress
                return min(calculated_level, float(effective_max_level))
            else: # Avoid division by zero if xp table is malformed
                return min(float(level), float(effective_max_level))

    # If loop finishes, player is exactly max level or below
    return min(float(level), float(effective_max_level))


def calculate_hotm_level(leveling_data: LevelingData, xp: float) -> float:
    """Calculates the Heart of the Mountain level based on cumulative XP per level.
    Assumes 'hotm_brackets' in leveling_data contains XP needed for each level.
    """
    # print(f"\n[DEBUG][Calc][HotM] Calculating HotM Level for XP: {xp:,.0f}") # Start Calculation Log (Removed)
    if 'hotm_brackets' not in leveling_data or not leveling_data['hotm_brackets']:
        print("[WARN][Calc][HotM] HOTM XP requirements (hotm_brackets) not loaded.")
        return 0.0

    xp_per_level = leveling_data['hotm_brackets']
    max_level = len(xp_per_level) # Max level is determined by the length of the list
    # print(f"[DEBUG][Calc][HotM] Max Level (based on brackets): {max_level}") # Removed

    # Calculate total XP needed for max level
    total_xp_for_max = sum(xp_per_level)
    # print(f"[DEBUG][Calc][HotM] Total XP for Max Level: {total_xp_for_max:,.0f}") # Removed

    if xp >= total_xp_for_max:
        # print(f"[DEBUG][Calc][HotM] XP >= Total XP for Max. Returning Max Level: {max_level}") # Removed
        return float(max_level)

    # Find level based on cumulative XP progression
    total_xp_required = 0
    level = 0
    # print("[DEBUG][Calc][HotM] --- Iterating through levels ---") # Removed
    for i, required_xp in enumerate(xp_per_level):
        current_level_xp_threshold = total_xp_required # XP needed to START this level (cumulative sum BEFORE adding current level)
        # level_num_being_checked = i + 1 # Current level number (1-based)
        # print(f"[DEBUG][Calc][HotM] Checking Level {level_num_being_checked}: Needs {required_xp:,.0f} XP. Total XP needed to finish: {total_xp_required + required_xp:,.0f}") # Removed

        total_xp_required += required_xp # XP needed to FINISH this level (cumulative sum AFTER adding current level)

        if xp >= total_xp_required:
            level += 1
        else:
            xp_in_level = xp - current_level_xp_threshold
            xp_needed_for_level = required_xp # This is the amount for the current level (i)

            if xp_needed_for_level > 0:
                progress = xp_in_level / xp_needed_for_level
                final_level = level + progress
                return final_level
            else: # Avoid division by zero
                return float(level)

    return float(level)


def calculate_average_skill_level(leveling_data: LevelingData, profile: dict, player_uuid: str) -> float | None:
    """Calculates the average skill level, excluding cosmetics like Carpentry and Runecrafting if desired."""
    print(f"[DEBUG][Calc] Calculating Skill Average for profile {profile.get('profile_id', 'UNKNOWN')}")
    member_data = profile.get('members', {}).get(player_uuid)
    if not member_data:
        print(f"[WARN][Calc] Member data not found for {player_uuid} in profile.")
        return None

    experience_data = member_data.get('player_data', {}).get('experience', {})
    total_level_estimate = 0
    skills_counted = 0

    print("\n[DEBUG][Calc] Skill Levels:")
    print("-" * 40)

    for skill_name in constants.AVERAGE_SKILLS_LIST: # Use the predefined list
        xp_field = f'SKILL_{skill_name.upper()}'
        skill_xp = experience_data.get(xp_field)

        if skill_xp is not None:
            level = calculate_skill_level(leveling_data, skill_xp, skill_name, member_data)
            total_level_estimate += level
            skills_counted += 1
            print(f"{skill_name.capitalize():<11}: {level:>5.2f} (XP: {skill_xp:,.0f})")
        else:
            # Still count skill as 0 if API doesn't provide XP (e.g., new skill)
            total_level_estimate += 0
            skills_counted += 1
            print(f"{skill_name.capitalize():<11}: {0.00:>5.2f} (XP: Not Available)")

    print("-" * 40)

    if skills_counted > 0:
        average = total_level_estimate / skills_counted
        print(f"[DEBUG][Calc] Skill Average calculated: {average:.4f}")
        return average
    else:
        print("[WARN][Calc] No skills counted for average calculation.")
        return 0.0


def calculate_dungeon_level(leveling_data: LevelingData, xp: float) -> float:
    """Calculates the Catacombs level based on XP, including progress as decimal points."""
    if not leveling_data['catacombs_xp']:
        print("[WARN][Calc] Catacombs XP table not loaded.")
        return 0.0

    max_level = 100  # Catacombs max level
    xp_table = leveling_data['catacombs_xp']

    # Calculate total XP for max level (sum all entries)
    total_xp_for_max = sum(xp_table)

    if xp >= total_xp_for_max:
        return float(max_level)

    total_xp_required = 0
    level = 0
    for i, required_xp in enumerate(xp_table):
        if i >= max_level: # Should not happen if xp_table has 100 entries, but safety check
            break
        current_level_xp_threshold = total_xp_required
        total_xp_required += required_xp

        if xp >= total_xp_required:
            level += 1
        else:
            # Calculate progress within the current level
            xp_in_level = xp - current_level_xp_threshold
            xp_needed_for_level = required_xp
            if xp_needed_for_level > 0:
                progress = xp_in_level / xp_needed_for_level
                return level + progress
            else: # Avoid division by zero
                return float(level)

    # If loop completes, player is exactly level 100 (or table is shorter than 100)
    return float(level)


def calculate_class_level(leveling_data: LevelingData, xp: float) -> float:
    """Calculates the class level based on XP using the Catacombs XP table up to level 50."""
    if not leveling_data['catacombs_xp']:
        print("[WARN][Calc] Catacombs XP table not loaded for class calculation.")
        return 0.0

    max_class_level = 50
    # Use only the first 50 entries from the Catacombs XP table for class levels
    xp_table = leveling_data['catacombs_xp'][:max_class_level]

    total_xp_for_max_class_level = sum(xp_table)

    if xp >= total_xp_for_max_class_level:
        return float(max_class_level)

    total_xp_required = 0
    level = 0
    for i, required_xp in enumerate(xp_table):
        # No need to check i >= max_class_level due to slicing xp_table
        current_level_xp_threshold = total_xp_required
        total_xp_required += required_xp

        if xp >= total_xp_required:
            level += 1
        else:
            xp_in_level = xp - current_level_xp_threshold
            xp_needed_for_level = required_xp
            if xp_needed_for_level > 0:
                progress = xp_in_level / xp_needed_for_level
                return level + progress
            else:
                return float(level)

    # If loop completes, player is exactly level 50
    return float(level)


def calculate_slayer_level(leveling_data: LevelingData, xp: float, boss_key: str) -> int:
    """Calculates the integer slayer level for a specific boss based on XP thresholds."""
    if 'slayer_xp' not in leveling_data or boss_key not in leveling_data['slayer_xp']:
        print(f"[WARN][Calc] Slayer XP thresholds not loaded for boss: {boss_key}")
        return 0

    thresholds = leveling_data['slayer_xp'][boss_key]
    max_level = len(thresholds) # Max level is length of thresholds list
    level = 0

    # Find the current level based on thresholds
    for i in range(max_level):
        if xp >= thresholds[i]:
            level = i + 1 # Level is index + 1
        else:
            break # Stop checking once a threshold isn't met

    # Return only the integer level
    return level


def format_price(price: int | float) -> str:
    """Formats a price into a shorter form (e.g., 1.3m instead of 1,300,000)."""
    price = float(price) # Ensure float for division
    if price >= 1_000_000_000:
        return f"{price / 1_000_000_000:.1f}b"
    elif price >= 1_000_000:
        return f"{price / 1_000_000:.1f}m"
    elif price >= 1_000:
        return f"{price / 1_000:.1f}k"
    else:
        return f"{price:.0f}" # Display small numbers as integers