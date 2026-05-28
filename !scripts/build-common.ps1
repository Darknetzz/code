function Get-DiscoveredPythonProjectNames {
    param([string]$PythonRoot)

    Get-ChildItem -Path $PythonRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'dist') } |
        Select-Object -ExpandProperty Name |
        Sort-Object
}

function Get-DiscoveredRustProjectNames {
    param([string]$RustRoot)

    Get-ChildItem -Path $RustRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'Cargo.toml') } |
        Select-Object -ExpandProperty Name |
        Sort-Object
}

function Get-PythonEntryScripts {
    param(
        [string]$ProjectPath,
        [string]$ProjectName
    )

    $scripts = [System.Collections.Generic.List[string]]::new()
    $standard = Join-Path -Path $ProjectPath -ChildPath "$ProjectName.py"
    if (Test-Path -LiteralPath $standard) {
        $scripts.Add($standard) | Out-Null
    }

    $distPath = Join-Path -Path $ProjectPath -ChildPath 'dist'
    if (Test-Path -LiteralPath $distPath) {
        Get-ChildItem -Path $distPath -Filter '*.exe' -File |
            ForEach-Object {
                $stem = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                $candidate = Join-Path -Path $ProjectPath -ChildPath "$stem.py"
                if ((Test-Path -LiteralPath $candidate) -and -not $scripts.Contains($candidate)) {
                    $scripts.Add($candidate) | Out-Null
                }
            }
    }

    if ($scripts.Count -eq 0) {
        Get-ChildItem -Path $ProjectPath -Filter '*.py' -File |
            Where-Object { $_.Name -notlike '_*' } |
            ForEach-Object { $scripts.Add($_.FullName) | Out-Null }
    }

    return ,$scripts.ToArray()
}

function Get-PythonExePath {
    param(
        [string]$ProjectPath,
        [string]$EntryScript
    )
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($EntryScript)
    Join-Path -Path $ProjectPath -ChildPath "dist\$stem.exe"
}

function Get-PythonSourceFiles {
    param([string]$ProjectPath)

    $excludeTopLevel = @('dist', 'build', '__pycache__', '.venv', '.venv-build')

    Get-ChildItem -Path $ProjectPath -Recurse -File | Where-Object {
        $relative = $_.FullName.Substring($ProjectPath.Length).TrimStart('\', '/')
        $parts = $relative -split '[\\/]'
        if ($parts[0] -in $excludeTopLevel) { return $false }
        if ($parts -contains '__pycache__') { return $false }
        if ($_.Extension -eq '.pyc' -or $_.Name -like '*.spec.bak') { return $false }

        ($_.Extension -in '.py', '.spec') -or ($_.Name -eq 'requirements.txt')
    }
}

function Test-PythonTargetNeedsBuild {
    param(
        [string]$ProjectPath,
        [string]$ExePath
    )

    if (-not (Test-Path -LiteralPath $ExePath)) {
        return $true
    }

    $exeTime = (Get-Item -LiteralPath $ExePath).LastWriteTimeUtc
    $sourceFiles = Get-PythonSourceFiles -ProjectPath $ProjectPath

    foreach ($sourceFile in $sourceFiles) {
        if ($sourceFile.LastWriteTimeUtc -gt $exeTime) {
            return $true
        }
    }

    return $false
}
