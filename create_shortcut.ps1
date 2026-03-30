# Power News DJ - デスクトップショートカット作成スクリプト
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartBat   = Join-Path $ScriptDir "start.bat"
$Desktop    = [Environment]::GetFolderPath("Desktop")
$Shortcut   = Join-Path $Desktop "Power News DJ.lnk"

$WshShell   = New-Object -ComObject WScript.Shell
$Lnk        = $WshShell.CreateShortcut($Shortcut)
$Lnk.TargetPath       = $StartBat
$Lnk.WorkingDirectory = $ScriptDir
$Lnk.WindowStyle      = 7          # 最小化で起動（コンソールを目立たせない）
$Lnk.Description      = "Power News DJ - 電力・蓄電池ニュースアグリゲーター"
$Lnk.IconLocation     = "shell32.dll,14"   # 地球アイコン
$Lnk.Save()

Write-Host "ショートカットを作成しました: $Shortcut" -ForegroundColor Green
