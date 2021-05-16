import unrealsdk
import os
import json
import sys
from glob import glob
from Mods import ModMenu
from typing import Dict, List, Any


class CustomSkins(ModMenu.SDKMod):
    Name: str = "Custom Skins"
    Author: str = "FromDarkHell"
    Description: str = "A simple mod allowing you to have custom character skins, all selectable!<br>Hit R in this menu to reload your skins<br>Press O to open your skin folder"
    Version: str = "1.0.0"

    # Sadly this mod can only really support BL2 as TPS doesn't support on the fly skin editing which is a not cool move
    SupportedGames: ModMenu.Game = ModMenu.Game.BL2
    Types: ModMenu.ModTypes = ModMenu.ModTypes.Content
    SaveEnabledState: ModMenu.EnabledSaveType = ModMenu.EnabledSaveType.LoadOnMainMenu

    # All of the supported characters / folder names
    SupportedCharacters: List[str] = ["Zer0", "Maya", "Salvador", "Krieg", "Gaige", "Axton"]

    # {"Object Name": {"VectorParameterValues": "value", "TextureParameterValues": ""}}
    DefaultSkins: Dict[str, Dict[str, str]] = {}
    SettingsInputs: Dict[str, str] = {"Enter": "Enable", "R": "Refresh Skins", "O": "Open Skins"}

    SkinnedCharacters: Dict[str, List[str]] = {}

    def InitializePackages(self) -> None:
        CharactersToClassName = {
            "Zer0": "Assassin",
            "Maya": "Siren",
            "Salvador": "Mercenary",
            "Krieg": "Psycho",
            "Gaige": "Mechro",
            "Axton": "Soldier",
            "Runner": "Runner",
            "Technical": "BanditTech",
        }

        # Only load packages related to the skinned characters
        customizationPackages = []
        for character in self.skinnedCharacters:
            # Ignore non-
            if len(self.skinnedCharacters[character]) > 0:
                className = CharactersToClassName[character]
                customizationPackages += glob(f"../../WillowGame/CookedPCConsole/CD_{className}_*.upk")
                customizationPackages += glob(f"../../DLC/*/Compat/Content/CD_{className}_*.upk")

        for package in customizationPackages:
            packageName = os.path.splitext(os.path.basename(package))[0]

            # unrealsdk.Log(f"    [CustomSkins] -- Loading Package: {packageName}")

            # Get just the file name and then load the respective UPK for it
            unrealsdk.LoadPackage(packageName)

    def InitializeSkinSettings(self) -> None:
        # Reset options, as we use a += later on in the code and this'll avoid weird issues
        self.Options = []

        # Read all of the skin files and get the absolute path of their file name
        skinFiles = [os.path.normpath(x) for x in glob("Mods/CustomSkins/Skins/*/*.*")]

        # Add all of the characters into the list, it just makes for cleaner code
        self.skinnedCharacters: Dict[str, List[str]] = {}
        for character in self.SupportedCharacters:
            self.skinnedCharacters.update({character: []})

        # Read in valid files and get their respective characters
        for skinFile in skinFiles:
            with open(skinFile, "r", encoding="utf-8") as openF:
                modText = openF.read()
                character = skinFile.rsplit("\\")[-2]
                # Ignore invalid files
                if "\nset " not in modText or character not in self.SupportedCharacters:
                    unrealsdk.Log(f"    [CustomSkins] {skinFile} does not follow the specified format!")
                    continue
                # Add the file for the given character
                self.skinnedCharacters[character] += [skinFile]
        unrealsdk.Log(f"[CustomSkins] Skinned Characters: {self.skinnedCharacters}")

        # Add options now
        for character in self.skinnedCharacters:
            # Ignore characters w/o any skins
            if len(self.skinnedCharacters[character]) == 0:
                continue
            # Get just the file name
            allFileNames = [os.path.splitext(os.path.basename(x))[0] for x in self.skinnedCharacters[character]]
            characterOptions = []
            for x in allFileNames:
                # Create a new boolean option for the skin file
                charOption = ModMenu.Options.Boolean(x, f'Enables/Disables the skins stored in "{x}"', False)
                # Store the character name, this allows us to have duplicate file names but for differing characters

                charOption.Character = character  # type: ignore[attr-defined]

                # Add to the available options for characters
                characterOptions += [charOption]
            self.Options += [ModMenu.Options.Nested(character, f"Custom Skins for {character}", characterOptions)]

    def RestoreSkinSettings(self) -> None:
        # This function is necessary in order to restore settings from nested settings
        unrealsdk.Log("[CustomSkins] Restoring skin settings from settings.json")
        if not os.path.exists("Mods/CustomSkins/settings.json"):
            return

        with open("Mods/CustomSkins/settings.json") as jsonFile:
            settings = json.load(jsonFile)
            # Ignore situations where we have no settings
            if "Options" not in settings:
                return
            settings = settings["Options"]
            for char in self.SupportedCharacters:
                # Ignore characters w/o any settings or custom skins
                if char not in settings or char not in [x.Caption for x in self.Options]:
                    continue
                # Get the char object in the list of options
                charOptions = [x for x in self.Options if x.Caption == char][0]
                for file in settings[char]:
                    # Ignore files which do not exist anymore
                    if file not in [x.Caption for x in charOptions.Children]:  # type: ignore[attr-defined]
                        continue
                    # Get the object pertaining to the given file
                    charOption = [x for x in charOptions.Children if file == x.Caption][0]  # type: ignore[attr-defined]
                    # Call ModOptionChanged so that way we update it
                    self.ModOptionChanged(charOption, settings[char][file])
                    # A ternary operator between "Off" and "On"
                    charOption.CurrentValue = charOption.Choices[int(settings[char][file])]

    def Enable(self) -> None:
        # Add the skin files to the settings for easy config
        self.InitializeSkinSettings()

        # Load all skin packages, this'll just be easier personally
        self.InitializePackages()

        # We have to do the options restoration ourself due to backwards compatability weirdness
        self.RestoreSkinSettings()

        # We wait before calling super().Enable() as we programmatically add to Options which is a bit weird
        super().Enable()

    def Disable(self) -> None:
        super().Disable()

        for skin in self.DefaultSkins:
            unrealsdk.Log(f"[CustomSkins] Restoring skin {skin} back to default")
            self.RestoreSkinToDefault(skin)
        self.DefaultSkins = {}

    def RestoreSkinToDefault(self, matObj: str) -> None:

        """Turns a python style array into a UE3 accepted `set` string"""

        def setCommandizeString(string: str) -> str:
            result = (
                string.replace(": ", "=")
                .replace("{", "(")
                .replace("}", ")")
                .replace("[", "(")
                .replace("]", ")")
                .replace("'", '"')
            )
            # This is a bit of a janky fix but its a bit more safer and annoying than doing more advanced string manipulation
            if "Texture2D" in result:
                result = result.replace("Texture2D ", "Texture2D'").replace(", E", "', E")
            return result

        """Modifies a property via UE3's `set` command"""

        def ModifyProperty(self: CustomSkins, obj: str, propName: str) -> None:
            val = setCommandizeString(self.DefaultSkins[matObj][propName])
            setCmd = f"set {obj} {propName} {val}"
            unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(setCmd, False)

        ModifyProperty(self, matObj, "VectorParameterValues")
        ModifyProperty(self, matObj, "TextureParameterValues")
        ModifyProperty(self, matObj, "ScalarParameterValues")

    def ModOptionChanged(self, option: ModMenu.Options.Base, new_value: Any) -> None:
        unrealsdk.Log(f"[CustomSkins] Changing {option.Caption} for character: {option.Character}")  # type: ignore[attr-defined]

        # All skin file names etc for the given
        characterSkins = self.skinnedCharacters[option.Character]  # type: ignore[attr-defined]

        # A bit unwieldy but it seems to work, we check the non-extension vs extension
        filePath = [x for x in characterSkins if os.path.splitext(os.path.basename(x))[0] == option.Caption][0]

        if not os.path.exists(filePath):
            unrealsdk.Log(f"    [CustomSkins] Unable to find file for {option.Caption}")
            return

        materialObjects = []
        with open(filePath, "r", encoding="utf-8") as openF:
            modText = openF.read()
            for materialObject in [x.split(" ")[0] for x in modText.split("\nset ")[1:]]:
                if materialObject.startswith("CD_"):
                    materialObjects += [materialObject]

        reloadedPackages = False
        for matObj in materialObjects:
            # Get UObject from the skin object name
            obj = unrealsdk.FindObject("MaterialInstanceConstant", matObj)

            # Avoid non available objects
            if obj is None:
                if reloadedPackages:
                    continue
                # Initialize the package as a quick attempt
                reloadedPackages = True
                # Reload all customization packages
                self.InitializePackages()
                unrealsdk.Log("    [CustomSkins] Unable to find object, trying to reload object...")
                # Retry this time
                obj = unrealsdk.FindObject("MaterialInstanceConstant", matObj)
                # We failed again, must not be an actual MIC object.
                if obj is None:
                    unrealsdk.Log(f"        [CustomSkins] Still could not find object -- {matObj} // {obj}")
                    continue

            # Keep our object alive
            unrealsdk.KeepAlive(obj)

            # Revert the object back to the defaults
            if not new_value and matObj in self.DefaultSkins:
                self.RestoreSkinToDefault(matObj)
                continue

            # Add to the default skins, casted to a string
            # You can't leave the default FArray as that'll get updated with the exec (hence crash)
            # Instead we pull from a python like string to a UE3 string and then run `set`
            self.DefaultSkins.setdefault(
                matObj,
                {
                    "VectorParameterValues": str(obj.VectorParameterValues),
                    "TextureParameterValues": str(obj.TextureParameterValues),
                    "ScalarParameterValues": str(obj.ScalarParameterValues),
                },
            )

        # Run the file if we are enabling
        if new_value:
            execPath = os.path.join("Win32", filePath)
            unrealsdk.GetEngine().GamePlayers[0].Actor.ConsoleCommand(f'exec "{execPath}"', False)

    def SettingsInputPressed(self, action: str) -> None:
        # Some versions of the SDK call `SettingsInputPressed` on pause
        if unrealsdk.GetEngine().GetCurrentWorldInfo().GetMapName(True) != "menumap":
            return

        # Refreshing the skins is practically just disabling and then enabling
        if action == "Refresh Skins":
            # Add the skin files to the settings for easy config
            self.InitializeSkinSettings()
            # Load all skin packages, this'll just be easier personally
            self.InitializePackages()
            # We have to do the options restoration ourself due to backwards compatability weirdness
            self.RestoreSkinSettings()
        elif action == "Open Skins":
            # Open to "Win32/Mods/CustomSkins/Skins"
            os.startfile(os.path.join(os.path.dirname(sys.executable), "Mods", "CustomSkins", "Skins"))
        else:
            # Enable / Disable
            super().SettingsInputPressed(action)


instance = CustomSkins()

# Simple boilerplate for hot reloading
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
