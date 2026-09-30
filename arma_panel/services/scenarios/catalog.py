"""Known scenarios.

VANILLA_SCENARIOS holds the Bohemia/vanilla scenarios, used as a fallback when
the dedicated server install can't be scanned (e.g. SERVER_DIR misconfigured).
When the server install IS scannable, dynamic discovery from its addons
folder supersedes this list.
"""

VANILLA_SCENARIOS = [
    # Everon
    {"id": "{ECC61978EDCC2B5A}Missions/23_Campaign.conf",              "name": "Conflict — Everon"},
    {"id": "{C700DB41F0C546E1}Missions/23_Campaign_NorthCentral.conf", "name": "Conflict — Northern Everon"},
    {"id": "{28802845ADA64D52}Missions/23_Campaign_SWCoast.conf",      "name": "Conflict — Southern Everon"},
    {"id": "{94992A3D7CE4FF8A}Missions/23_Campaign_Western.conf",      "name": "Conflict — Western Everon"},
    {"id": "{FDE33AFE2ED7875B}Missions/23_Campaign_Montignac.conf",    "name": "Conflict — Montignac"},
    {"id": "{0220741028718E7F}Missions/23_Campaign_HQC_Everon.conf",   "name": "Conflict: HQ Commander — Everon"},
    {"id": "{59AD59368755F41A}Missions/21_GM_Eden.conf",               "name": "Game Master — Everon"},
    {"id": "{DFAC5FABD11F2390}Missions/26_CombatOpsEveron.conf",       "name": "Combat Ops — Everon"},
    # Capture & Hold
    {"id": "{3F2E005F43DBD2F8}Missions/CAH_Briars_Coast.conf",         "name": "Capture & Hold — Briars Coast"},
    {"id": "{F1A1BEA67132113E}Missions/CAH_Castle.conf",               "name": "Capture & Hold — Montfort Castle"},
    {"id": "{589945FB9FA7B97D}Missions/CAH_Concrete_Plant.conf",       "name": "Capture & Hold — Concrete Plant"},
    {"id": "{9405201CBD22A30C}Missions/CAH_Factory.conf",              "name": "Capture & Hold — Almara Factory"},
    {"id": "{1CD06B409C6FAE56}Missions/CAH_Forest.conf",               "name": "Capture & Hold — Simon's Wood"},
    {"id": "{7C491B1FCC0FF0E1}Missions/CAH_LeMoule.conf",              "name": "Capture & Hold — Le Moule"},
    {"id": "{6EA2E454519E5869}Missions/CAH_Military_Base.conf",        "name": "Capture & Hold — Camp Blake"},
    # Showcase / SP
    {"id": "{C47A1A6245A13B26}Missions/SP01_ReginaV2.conf",            "name": "Elimination"},
    {"id": "{0648CDB32D6B02B3}Missions/SP02_AirSupport.conf",          "name": "Air Support"},
    # Arland
    {"id": "{C41618FD18E9D714}Missions/23_Campaign_Arland.conf",       "name": "Conflict — Arland"},
    {"id": "{68D1240A11492545}Missions/23_Campaign_HQC_Arland.conf",   "name": "Conflict: HQ Commander — Arland"},
    {"id": "{2BBBE828037C6F4B}Missions/22_GM_Arland.conf",             "name": "Game Master — Arland"},
    {"id": "{DAA03C6E6099D50F}Missions/24_CombatOps.conf",             "name": "Combat Ops — Arland"},
    # Kolguyev
    {"id": "{F45C6C15D31252E6}Missions/27_GM_Cain.conf",               "name": "Game Master — Kolguyev"},
    {"id": "{BB5345C22DD2B655}Missions/23_Campaign_HQC_Cain.conf",     "name": "Conflict: HQ Commander — Kolguyev"},
    {"id": "{CB347F2F10065C9C}Missions/CombatOpsCain.conf",            "name": "Combat Ops — Kolguyev"},
    {"id": "{2B4183DF23E88249}Missions/CAH_Morton.conf",               "name": "Capture & Hold — Morton"},
    # Operation Omega
    {"id": "{10B8582BAD9F7040}Missions/Scenario01_Intro.conf",         "name": "Operation Omega 01: Over The Hills And Far Away"},
    {"id": "{1D76AF6DC4DF0577}Missions/Scenario02_Steal.conf",         "name": "Operation Omega 02: Radio Check"},
    {"id": "{D1647575BCEA5A05}Missions/Scenario03_Villa.conf",         "name": "Operation Omega 03: Light In The Dark"},
    {"id": "{6D224A109B973DD8}Missions/Scenario04_Sabotage.conf",      "name": "Operation Omega 04: Red Silence"},
    {"id": "{FA2AB0181129CB16}Missions/Scenario05_Hill.conf",          "name": "Operation Omega 05: Cliffhanger"},
]
# Add a "source" tag so the UI can group by origin.
for _m in VANILLA_SCENARIOS:
    _m.setdefault("source", "vanilla")


# Friendly display names for scenarios discovered via .rdb (which only gives
# us the filename, not the publisher's display name). Used as an override when
# the .rdb scan finds a known scenario ID. Anything not listed here falls back
# to the cleaned-up filename derived from the path.
SCENARIO_NAME_OVERRIDES = {
    # RHS — Status Quo
    "{AAD43C10045857C1}Missions/RHS_Conflict.conf":              ("Conflict — Everon (RHS)",                 64),
    "{B694A77592CB69E0}Missions/RHS_ConflictWithoutAIs.conf":    ("Conflict — Everon, no AI (RHS)",          64),
    "{9909DB7ECEA05535}Missions/RHS_Conflict_East.conf":         ("Conflict — Everon East (RHS)",            40),
    "{2F5DD5ACC14120A9}Missions/RHS_Conflict_NorthCentral.conf": ("Conflict — Everon North Central (RHS)",   64),
    "{57B154A20B8B283E}Missions/RHS_Conflict_SWCoast.conf":      ("Conflict — Everon SW Coast (RHS)",        64),
    "{367A7800D147878A}Missions/RHS_Conflict_West.conf":         ("Conflict — Everon West (RHS)",            40),
    "{7577640CD42A00BD}Missions/RHS_Conflict_Arland.conf":       ("Conflict — Arland (RHS)",                 64),
    "{C5EAD55037EB4751}Missions/RHS_CombatOps_MSV.conf":         ("Combat Ops — Arland, MSV vs FIA (RHS)",   16),
    "{D10B11A71A36FCF5}Missions/RHS_CombatOps_USMC_vs_MSV.conf": ("Combat Ops — Arland, USMC vs MSV (RHS)",  16),
    "{68A6FBF43B801FF6}Missions/RHS_ShowcaseBasic.conf":         ("Showcase Mission (RHS)",                   6),
    "{217436B52D34E4BD}Missions/RHS_Showcase_GM.conf":           ("Showcase Mission, Game Master (RHS)",     36),
}


def apply_name_override(scenario):
    """If we have a curated friendly name for this scenario ID, use it."""
    override = SCENARIO_NAME_OVERRIDES.get(scenario["id"])
    if override:
        scenario["name"] = override[0]
        if override[1] and not scenario.get("player_count"):
            scenario["player_count"] = override[1]
    return scenario
