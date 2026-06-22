$BASE = "PiClient"
foreach ($d in @("piclient-core","piclient-cli","piclient-open_challenge","piclient-obstacle_challenge")) { 
    $p = "$BASE\$d\pyproject.toml";
    $bytes = [IO.File]::ReadAllBytes($p);
    if ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [IO.File]::WriteAllBytes($p, $bytes[3..($bytes.Length-1)]);
        Write-Host "Stripped BOM: $d" } else { Write-Host "Clean: $d" 
    } 
}