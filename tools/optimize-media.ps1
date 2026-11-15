param(
    [Parameter(Mandatory = $true)]
    [string]$UploadsDirectory,
    [string]$ManifestPath = (Join-Path $PSScriptRoot '..\data\media-manifest.json'),
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..'),
    [int]$MaxDimension = 1400,
    [long]$Quality = 76
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$uploads = (Resolve-Path -LiteralPath $UploadsDirectory).Path
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$jpegEncoder = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
    Where-Object { $_.MimeType -eq 'image/jpeg' } |
    Select-Object -First 1

if (-not $jpegEncoder) {
    throw 'A JPEG encoder is not available on this system.'
}

$encoderParameters = New-Object System.Drawing.Imaging.EncoderParameters(1)
$encoderParameters.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
    [System.Drawing.Imaging.Encoder]::Quality,
    $Quality
)

try {
    foreach ($item in $manifest) {
        $relativeSource = [System.IO.Path]::GetFullPath(
            (Join-Path $uploads $item.source)
        )
        if (-not $relativeSource.StartsWith(
            $uploads + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Media source escapes the uploads directory: $($item.source)"
        }
        if (-not (Test-Path -LiteralPath $relativeSource -PathType Leaf)) {
            throw "Media source is missing: $relativeSource"
        }

        $destination = Join-Path $OutputDirectory $item.target
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

        if ($item.operation -eq 'copy') {
            Copy-Item -LiteralPath $relativeSource -Destination $destination -Force
            continue
        }

        $sourceImage = $null
        $bitmap = $null
        $graphics = $null
        try {
            $sourceImage = [System.Drawing.Image]::FromFile($relativeSource)
            if ($item.operation -eq 'first-frame') {
                $sourceImage.SelectActiveFrame(
                    [System.Drawing.Imaging.FrameDimension]::Time,
                    0
                ) | Out-Null
            }

            $scale = [Math]::Min(
                1.0,
                $MaxDimension / [double][Math]::Max(
                    $sourceImage.Width,
                    $sourceImage.Height
                )
            )
            $width = [Math]::Max(1, [int][Math]::Round($sourceImage.Width * $scale))
            $height = [Math]::Max(1, [int][Math]::Round($sourceImage.Height * $scale))
            $bitmap = New-Object System.Drawing.Bitmap($width, $height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.DrawImage($sourceImage, 0, 0, $width, $height)
            $bitmap.Save($destination, $jpegEncoder, $encoderParameters)
        }
        finally {
            if ($graphics) { $graphics.Dispose() }
            if ($bitmap) { $bitmap.Dispose() }
            if ($sourceImage) { $sourceImage.Dispose() }
        }
    }
}
finally {
    $encoderParameters.Dispose()
}

Write-Output ("Processed {0} archived image files." -f $manifest.Count)
