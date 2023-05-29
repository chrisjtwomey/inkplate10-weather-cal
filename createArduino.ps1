# Arduino expects Sketches to be in a folder with the name of the sketch file, and the sketch file needs to have the .ino extension
# This quickly copies the firmware source files and renames main.cpp to achieve this.

Write-Host -NoNewline "Copying src directory to main..."
Copy-Item -Path .\src -Destination .\main -Recurse
Write-Host "done!"
Write-Host -NoNewline "Renaming main/main.cpp to main/main.ino..."
Move-Item -Path ./main/main.cpp -Destination ./main/main.ino 
Write-Host "done!"
