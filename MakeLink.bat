@ECHO OFF

ECHO Enter the name of the mod to make a link to
set /p folderName=Folder Name: 

SET gameDir=J:\Steeeeeeeeeem\steamapps\common\Borderlands 2\Binaries\Win32\Mods\

SET modDir=%gameDir%%folderName%

mklink /J %folderName% "%modDir%"