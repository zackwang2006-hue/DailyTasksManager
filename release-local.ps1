param(
    [Parameter(Mandatory = $false)]
    [string]$Version
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ============================================================
# 基础路径
# 必须先定义 Root，再使用 Join-Path
# ============================================================

$Root = $PSScriptRoot

$VersionFile = Join-Path $Root "VERSION"
$VersionInfoFile = Join-Path $Root "version_info.txt"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "计划炼金台.spec"
$Iss = Join-Path $Root "installer\计划炼金台.iss"

$ISCC = Join-Path `
    $env:LOCALAPPDATA `
    "Programs\Inno Setup 7\ISCC.exe"

$BuiltExe = Join-Path `
    $Root `
    "dist\计划炼金台\计划炼金台.exe"

$InstallerOutputDir = Join-Path `
    $Root `
    "installer\output"

$InstalledExe = Join-Path `
    $env:LOCALAPPDATA `
    "Programs\计划炼金台\计划炼金台.exe"

$UserDataDir = Join-Path `
    $env:LOCALAPPDATA `
    "计划炼金台"

# ============================================================
# 版本号
# ============================================================

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw "缺少版本来源文件：$VersionFile"
    }

    $Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "版本号必须符合 major.minor.patch 格式，例如 2.0.1。"
}

$Installer = Join-Path `
    $InstallerOutputDir `
    "计划炼金台-Setup-$Version.exe"

# ============================================================
# 辅助函数
# ============================================================

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "缺少$Description：$Path"
    }
}

function Write-VersionInfoFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,

        [Parameter(Mandatory = $true)]
        [string]$AppVersion
    )

    $parts = $AppVersion.Split(".")

    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]

    $content = @"
# UTF-8

VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=($major, $minor, $patch, 0),
        prodvers=($major, $minor, $patch, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "080404B0",
                    [
                        StringStruct("ProductName", "计划炼金台"),
                        StringStruct("FileDescription", "计划炼金台"),
                        StringStruct("InternalName", "计划炼金台"),
                        StringStruct("OriginalFilename", "计划炼金台.exe"),
                        StringStruct("FileVersion", "$AppVersion"),
                        StringStruct("ProductVersion", "$AppVersion"),
                    ],
                )
            ]
        ),
        VarFileInfo(
            [
                VarStruct(
                    "Translation",
                    [0x0804, 1200],
                )
            ]
        ),
    ],
)
"@

    $utf8Bom = New-Object `
        -TypeName System.Text.UTF8Encoding `
        -ArgumentList $true

    [System.IO.File]::WriteAllText(
        $TargetPath,
        $content.TrimStart(),
        $utf8Bom
    )
}

function Test-VersionMatches {
    param(
        [AllowNull()]
        [string]$ActualVersion,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedVersion
    )

    if ([string]::IsNullOrWhiteSpace($ActualVersion)) {
        return $false
    }

    $normalized = $ActualVersion.Trim()

    return (
        $normalized -eq $ExpectedVersion -or
        $normalized -eq "$ExpectedVersion.0"
    )
}

# ============================================================
# 前置检查
# ============================================================

Write-Host "即将发布：计划炼金台 $Version"

Assert-FileExists $Python "虚拟环境解释器"
Assert-FileExists $Spec "PyInstaller spec 文件"
Assert-FileExists $Iss "Inno Setup 安装脚本"
Assert-FileExists $ISCC "Inno Setup 编译器"

Write-VersionInfoFile `
    -TargetPath $VersionInfoFile `
    -AppVersion $Version

Assert-FileExists $VersionInfoFile "Windows 版本信息文件"

$UserDataExistedBefore = Test-Path -LiteralPath $UserDataDir

# ============================================================
# 1/6 清理旧产物
# ============================================================

Write-Host "`n[1/6] 清理旧构建产物"

Remove-Item `
    -LiteralPath (Join-Path $Root "build") `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

Remove-Item `
    -LiteralPath (Join-Path $Root "dist") `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

Remove-Item `
    -LiteralPath $InstallerOutputDir `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

# ============================================================
# 2/6 PyInstaller 构建
# ============================================================

Write-Host "`n[2/6] 使用项目虚拟环境构建 PyInstaller 目录"

Push-Location $Root

try {
    & $Python `
        -m PyInstaller `
        --noconfirm `
        --clean `
        $Spec

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败，退出代码：$LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Assert-FileExists $BuiltExe "PyInstaller 生成的主程序"

# ============================================================
# 3/6 强制写入并验证 exe 版本资源
# ============================================================

Write-Host "`n[3/6] 写入并验证 exe 版本资源"

& $Python `
    -m PyInstaller.utils.cliutils.set_version `
    $VersionInfoFile `
    $BuiltExe

if ($LASTEXITCODE -ne 0) {
    throw "写入 exe 版本资源失败，退出代码：$LASTEXITCODE"
}

$BuiltVersionInfo = (Get-Item -LiteralPath $BuiltExe).VersionInfo

Write-Host "FileVersion：$($BuiltVersionInfo.FileVersion)"
Write-Host "ProductVersion：$($BuiltVersionInfo.ProductVersion)"
Write-Host "ProductName：$($BuiltVersionInfo.ProductName)"
Write-Host "FileDescription：$($BuiltVersionInfo.FileDescription)"

if (-not (
    Test-VersionMatches `
        -ActualVersion $BuiltVersionInfo.FileVersion `
        -ExpectedVersion $Version
)) {
    throw (
        "exe 文件版本不正确：期望 $Version，" +
        "实际 $($BuiltVersionInfo.FileVersion)"
    )
}

if (-not (
    Test-VersionMatches `
        -ActualVersion $BuiltVersionInfo.ProductVersion `
        -ExpectedVersion $Version
)) {
    throw (
        "exe 产品版本不正确：期望 $Version，" +
        "实际 $($BuiltVersionInfo.ProductVersion)"
    )
}

if ($BuiltVersionInfo.ProductName -ne "计划炼金台") {
    throw "exe 产品名称不正确：$($BuiltVersionInfo.ProductName)"
}

if ($BuiltVersionInfo.FileDescription -ne "计划炼金台") {
    throw "exe 文件说明不正确：$($BuiltVersionInfo.FileDescription)"
}

Write-Host "exe 版本资源验证通过。"

# ============================================================
# 4/6 编译安装程序
# 必须放在版本资源写入之后
# ============================================================

Write-Host "`n[4/6] 使用 Inno Setup 7 编译安装程序"

Push-Location $Root

try {
    & $ISCC `
        "/DMyAppVersion=$Version" `
        $Iss

    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 编译失败，退出代码：$LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Assert-FileExists $Installer "Inno Setup 安装程序"

# ============================================================
# 5/6 静默覆盖安装
# ============================================================

Write-Host "`n[5/6] 静默覆盖安装"

$installArguments = @(
    "/SP-"
    "/VERYSILENT"
    "/SUPPRESSMSGBOXES"
    "/NORESTART"
    "/CLOSEAPPLICATIONS"
)

$installProcess = Start-Process `
    -FilePath $Installer `
    -ArgumentList $installArguments `
    -Wait `
    -PassThru

if ($installProcess.ExitCode -ne 0) {
    throw "安装失败，退出代码：$($installProcess.ExitCode)"
}

Assert-FileExists $InstalledExe "安装后的主程序"

if (
    $UserDataExistedBefore -and
    -not (Test-Path -LiteralPath $UserDataDir)
) {
    throw "安装过程异常删除了用户数据目录：$UserDataDir"
}

# 安装完成后再次验证，确保安装器包含的是正确 exe
$InstalledVersionInfo = (Get-Item -LiteralPath $InstalledExe).VersionInfo

if (-not (
    Test-VersionMatches `
        -ActualVersion $InstalledVersionInfo.FileVersion `
        -ExpectedVersion $Version
)) {
    throw (
        "安装版 exe 文件版本不正确：期望 $Version，" +
        "实际 $($InstalledVersionInfo.FileVersion)"
    )
}

if ($InstalledVersionInfo.ProductName -ne "计划炼金台") {
    throw (
        "安装版 exe 产品名称不正确：" +
        "$($InstalledVersionInfo.ProductName)"
    )
}

Write-Host "安装版版本资源验证通过。"

# ============================================================
# 6/6 启动安装版本
# ============================================================

Write-Host "`n[6/6] 启动已安装版本"

Start-Process `
    -FilePath $InstalledExe `
    -WorkingDirectory (Split-Path $InstalledExe)

Write-Host "`n本地发布完成：$Installer"