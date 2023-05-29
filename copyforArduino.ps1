# Arduino expects Sketches to be in a folder with the name of the sketch file, and the sketch file needs to have the .ino extension
# This quickly copies the firmware source files and renames main.cpp to achieve this.
# USAGE : 
# Just running with no parameters will use some defaults and prompt the user to change them if needed.
# 
# EXAMPLE : ./copyforArduino.ps1
# 
# If required, it's possible to pass the following parameters on the command line :
#   ParentDir : Overrides the default parent destination directory.  (Defaults to Documents\Arduino) 
#   SketchName : Overrides the default sketch name and directory name that will be created.  (Defaults to inkplate-weather-cal)
#   NoOverride : Stops the script prompting to override the destination and sketch names.  It's helpful to set to TRUE if you're passing in parameters directly on the command line in order to save it prompting for them again  (Defaults to FALSE)
# 
# EXAMPLE : .\copyforArduino.ps1 -ParentDir "D:/Arduino" -SketchName WeatherBoard -NoOverride True
# 
param (
    [string]$ParentDir,    
    [string]$SketchName = "inkplate-weather-cal",
    [switch]$NoOverride = $false
)

if (!$ParentDir) {
    Write-Host "No ParentDir was passed, building a default..."
    $ParentDir = [environment]::getfolderpath(“mydocuments”)
    Write-Host "    Got documents folder as $ParentDir ..."
    $ParentDir += "/Arduino"
    Write-Host "    Assuming Arduino folder is $ParentDir ..."
    Write-Host "Sketch directory will be copied into $ParentDir !"
}

if (!$NoOverride) {
    $overrideSketchName = Read-Host -Prompt "Please provide the SketchName or press ENTER to use default ($SketchName) : "
    if ($overrideSketchName) {$SketchName = $overrideSketchName}
    $overrideParentDir = Read-Host -Prompt "Please provice the parent directory to copy into or press ENTER to use default ($ParentDir) : "
    if ($overrideParentDir) {$ParentDir = $overrideParentDir}
}
Write-Host "ParentDir is : $ParentDir "
Write-Host "SketchName is : $SketchName"
$TargetDir = "$ParentDir/$SketchName"
if (Test-Path $TargetDir) {
    Write-Host -ForegroundColor DarkRed "The TargetDir ($TargetDir) already exists - ABORTING!"
    Exit
}
Write-Host -NoNewline "Copying src directory to $TargetDir..."
try{
    Copy-Item -Path .\src -Destination $TargetDir -Recurse -errorAction stop
    Write-Host -ForegroundColor green "done!"
}
catch {
    Write-Host -ForegroundColor white -BackgroundColor DarkRed "FAILED!"
    Write-Host "    $_"
    Exit
}

Write-Host -NoNewline "Renaming $TargetDir/main.cpp to $TargetDir/main.ino..."
try {
    Move-Item -Path "$TargetDir/main.cpp" -Destination "$TargetDir/main.ino" -errorAction stop
    Write-Host -ForegroundColor green "done!"
}
catch {
    Write-Host -ForegroundColor white -BackgroundColor DarkRed "FAILED!"
    Write-Host "    $_"
}
