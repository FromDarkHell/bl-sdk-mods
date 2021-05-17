import unrealsdk
import math
from Mods import ModMenu
from typing import Dict, Tuple, List

# Requirement checking for those who have not installed UserFeedback
try:
    from Mods import UserFeedback

    if UserFeedback.VersionMajor < 1:
        raise RuntimeError("UserFeedback version is too old, need at least v1.5!")
    if UserFeedback.VersionMajor == 1 and UserFeedback.VersionMinor < 5:
        raise RuntimeError("UserFeedback version is too old, need at least v1.5!")
except (ImportError, RuntimeError, NameError) as ex:
    import webbrowser

    url = "https://apple1417.github.io/bl2/didntread/?m=Skill%20Saver&uf=v1.5"
    if isinstance(ex, (RuntimeError, NameError)):
        url += "&update"
    webbrowser.open(url)
    raise ex

"""
Returns the blacklisted skills for the given character
Pretty much only Gaige & Krieg have blacklisted skills as they both use hidden skills which are still stored in the skill tree objects themselves.
"""


def GetSkillIndexBlackList(CharacterClass: str) -> List[int]:
    skillIndexBlacklist = []

    # Ignore ""hidden"" skills
    if CharacterClass == "Mechromancer":
        skillIndexBlacklist = [24]
    elif CharacterClass == "Psycho":
        skillIndexBlacklist = [13, 37, 38]
    return skillIndexBlacklist


"""Returns a tuple of the character class and the current build object"""


def GetCharClassAndSkillTree() -> Tuple[str, unrealsdk.UObject]:
    PC = unrealsdk.GetEngine().GamePlayers[0].Actor
    currentBuild, characterClass = None, None
    # Check if the player is loaded
    if PC.CharacterClass is not None and PC.PlayerSkillTree is not None:
        currentBuild = PC.PlayerSkillTree.Skills
        characterClass = PC.CharacterClass.GetName()
    # Get the cached save game for the player
    elif PC.GetCachedSaveGame() is not None:
        characterClass = PC.GetCachedSaveGame().PlayerClassDefinition.GetName()
        currentBuild = PC.GetCachedSaveGame().SkillData
    # Return nothing otherwise
    if currentBuild is None or characterClass is None:
        return ("", None)
    # Certain classes have some different names from their CharacterClass
    if characterClass == "CharClass_LilacPlayerClass":
        characterClass = "Psycho"
    elif characterClass == "charclass_doppelganger":
        characterClass = "Doppelganger"
    characterClass = characterClass.replace("CharClass_", "")
    return (characterClass, currentBuild)


"""Saves the skill tree to the global instance's skill options"""


def SaveSkillTree() -> None:
    unrealsdk.Log("[SkillSaver] Saving skill tree...")

    def _GetResult(Message: str) -> None:
        # Don't even bother trying to add all white space names
        if Message.isspace() or Message == "None":
            return

        global instance
        CharacterClass, SkillTreeData = GetCharClassAndSkillTree()
        # Error Checking
        if CharacterClass == "" or SkillTreeData is None:
            return

        skillIndexBlacklist = GetSkillIndexBlackList(CharacterClass)

        # The build stored as a string (really just an array of skill points)
        # Note that this does include the action skill as well (in case you want a build without an action skill I guess)
        build = ""
        skillIndex = 0
        for skill in SkillTreeData:
            if skillIndex not in skillIndexBlacklist:
                build += str(skill.Grade)
            skillIndex += 1
        unrealsdk.Log(f'[SkillSaver] Saving tree ({build}) for {CharacterClass} with build name "{Message}"')

        # Update the skill map, **will overwrite duplicates**
        instance.SkillMap.CurrentValue[CharacterClass].update({Message: build})

        # Save the settings as manually updating it like this does not save it
        ModMenu.SettingsManager.SaveModSettings(instance)

    # Create a text box for the player to enter their name
    inputBox = UserFeedback.TextInputBox("Enter Skill Tree Name:", PausesGame=True)
    inputBox.OnSubmit = _GetResult  # type: ignore[assignment]
    inputBox.Show()


"""Restores the selected skill tree from the chosen option (currently selected character)"""


def RestoreSkillTree() -> None:
    global instance

    # Get player controller
    PC = unrealsdk.GetEngine().GamePlayers[0].Actor
    # Get the current character class and skill tree
    CharacterClass, SkillTree = GetCharClassAndSkillTree()

    # Error Check
    if CharacterClass == "" or SkillTree is None:
        return

    # Get the respec cost (includes percentage of option) and then floor it (we'll be forgiving :P)
    respecCost = math.floor(PC.GetSkillTreeResetCost() * (instance.RespecCost.CurrentValue / 100))

    # Don't charge the player just to spec, especially if they're already not specced
    if PC.PlayerReplicationInfo.GeneralSkillPoints == 0:
        respecCost = 0

    """ Saves the selected skill tree from the passed option box button"""

    def _OnSelectSkillTree(button: UserFeedback.OptionBoxButton) -> None:
        selectedBuild = instance.SkillMap.CurrentValue[CharacterClass][button.Name]
        unrealsdk.Log(f"[SkillSaver] Restoring skills to {button.Name} (Build = {selectedBuild}) (Cost: {respecCost})")

        skillIndexBlacklist = GetSkillIndexBlackList(CharacterClass)

        # Add the skill points back that we have removed
        PC.PlayerReplicationInfo.GeneralSkillPoints += PC.ResetSkillTree(True, False)

        # Get the individual skill point values, stored as a list
        specList = list(selectedBuild)
        removedIndexes = 0

        for skill in SkillTree:
            if skill.Index not in skillIndexBlacklist:
                skillGrade = int(specList[skill.Index - removedIndexes])
                for x in range(skillGrade):
                    PC.ServerUpgradeSkill(skill.Definition)
            else:
                removedIndexes += 1

        # Set the skill points equal to the remaining amount of skill points
        # There's surely a better, less janky way of doing this, but it works :/
        # actionSkillUnlock = (2, 4)[ModMenu.Game.GetCurrent() == ModMenu.Game.BL2]

        # Charge the player the amount for the respec cost (only if they can afford it)
        if respecCost <= PC.PlayerReplicationInfo.GetCurrencyOnHand(0) and respecCost > 0:
            PC.PlayerReplicationInfo.AddCurrencyOnHand(0, -1 * respecCost)

    buttons = []
    # Add a box button for every skill tree saved for the given character
    for skillTree in instance.SkillMap.CurrentValue[CharacterClass]:
        buttons += [UserFeedback.OptionBoxButton(Name=skillTree)]

    optionBox = UserFeedback.OptionBox(
        Title="Skill Tree Selection",
        Caption=f"Select a skill tree for the {CharacterClass} to restore to",
        Buttons=buttons,
    )
    # Set the callback
    optionBox.OnPress = _OnSelectSkillTree  # type: ignore[assignment]
    optionBox.Update()
    optionBox.Show()


"""Prompts the player to delete a given skill tree"""


def DeleteSkillTrees() -> None:
    global instance
    CharacterClass, SkillTree = GetCharClassAndSkillTree()
    # Error Check
    if CharacterClass == "" or SkillTree is None:
        return

    """ A callback for the option box for deleting skill trees, will delete the selected option"""

    def _DeleteSavedTree(button: UserFeedback.OptionBoxButton) -> None:
        # Pop the build value (remove it)
        buildValue = instance.SkillMap.CurrentValue[CharacterClass].pop(button.Name)
        unrealsdk.Log(f"[SkillSaver] Deleting {button.Name} (Build = {buildValue}) for {CharacterClass}")
        # Save settings as manually updating that dict does not save it
        ModMenu.SettingsManager.SaveModSettings(instance)

    buttons = []
    for skillTree in instance.SkillMap.CurrentValue[CharacterClass]:
        # Block the user from deleting "None"
        if skillTree == "None":
            continue
        # Add a button for each skill tree
        buttons += [UserFeedback.OptionBoxButton(Name=skillTree)]
    # Create an option box for the user
    optionBox = UserFeedback.OptionBox(
        Title="Skill Tree Deletion", Caption="Select a skill tree to delete", Buttons=buttons
    )
    # Set the callback
    optionBox.OnPress = _DeleteSavedTree  # type: ignore[assignment]
    optionBox.Update()
    optionBox.Show()


"""Allow the user to manage their skill tree setup (Save / Restore / Delete)"""


def ManageSkillTrees() -> None:
    unrealsdk.Log("[SkillSaver] Managing Skill Trees")

    # Simple dictionary to map option to function
    ActionMap = {
        "Restore Skill Tree": RestoreSkillTree,
        "Save Skill Tree": SaveSkillTree,
        "Delete Skill Tree": DeleteSkillTrees,
    }

    """ Calls the given function for the selected option box button """

    def _OnSelectOption(button: UserFeedback.OptionBoxButton) -> None:
        # Call the function for the given button
        ActionMap[button.Name]()

    # Create a button for each of the options in the ActionMap
    optionBox = UserFeedback.OptionBox(
        Title="Manage Skill Trees",
        Caption="Select the action you want to do!",
        Buttons=[UserFeedback.OptionBoxButton(x) for x in ActionMap],
    )
    # Set the callback
    optionBox.OnPress = _OnSelectOption  # type: ignore[assignment]
    optionBox.Update()
    optionBox.Show()


class SkillSaver(ModMenu.SDKMod):
    Name: str = "Skill Saver"
    Author: str = "FromDarkHell"
    Description: str = "Allows you to be able to save your current skill spec with ease and then restore back to it!"
    Version: str = "1.0.0"
    SupportedGames: ModMenu.Game = ModMenu.Game.BL2 | ModMenu.Game.TPS  # Either BL2 or TPS; bitwise OR'd together
    Types: ModMenu.ModTypes = ModMenu.ModTypes.Utility | ModMenu.ModTypes.Gameplay
    SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadWithSettings

    Keybinds = [ModMenu.Keybind("Manage Skill Layouts", "F3", OnPress=ManageSkillTrees)]

    def __init__(self) -> None:
        # Creates the option for the respec cost
        self.RespecCost = ModMenu.Options.Slider(
            "Skill Respec Cost",
            "Changes the cost of changing skill specs (Percentage of respec cost)<br>0% = Free // 100% = Full Cost",
            0,
            0,
            100,
            5,
        )

        # Value for the start of the Skill Map
        # Store it in a separate variable for clarity
        StartingValue = {}

        # Pick from the list of valid characters based off of the game
        Characters = (
            ["Prototype", "Enforcer", "Gladiator", "Lawbringer", "Baroness", "Doppelganger"],
            ["Mercenary", "Soldier", "Assassin", "Siren", "Mechromancer", "Psycho"],
        )[int(ModMenu.Game.GetCurrent() == ModMenu.Game.BL2)]

        for Character in Characters:
            # Add the default no skill specs
            StartingValue.update({Character: {"None": "0" * 40}})

        # The Skill Map is where we store the build strings for every character
        self.SkillMap: ModMenu.Options.Hidden[Dict[str, Dict[str, str]]] = ModMenu.Options.Hidden(
            "SkillMap", StartingValue=StartingValue
        )

        # Set the options back up
        self.Options = [self.RespecCost, self.SkillMap]


instance = SkillSaver()

# Simple snippet for hot reloading (Credit: apple1417)
if __name__ == "__main__":
    unrealsdk.Log(f"[{instance.Name}] Manually loaded")
    for mod in ModMenu.Mods:
        if mod.Name == instance.Name:
            if mod.IsEnabled:
                mod.Disable()
            ModMenu.Mods.remove(mod)
            unrealsdk.Log(f"[{instance.Name}] Removed last instance")

            # Fixes inspect.getfile()
            instance.__class__.__module__ = mod.__class__.__module__
            break

ModMenu.RegisterMod(instance)
