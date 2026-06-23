$venv = ".\.venv\Lib\site-packages";
Get-ChildItem $venv\_editable_impl_piclient*.pth |
ForEach-Object { 
    ($_ | Get-Content) -replace '\\src\\piclient$', '\src' |
    Set-Content $_.FullName
    Write-Host "Fixed" $_.Name 
}