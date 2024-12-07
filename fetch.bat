@echo OFF

scp mikey:C:\tools\Ninja.7z .
scp mikey:C:\tools\LLVM.7z .
7z x -aoa Ninja.7z
7z x -aoa LLVM.7z
del Ninja.7z
del LLVM.7z
