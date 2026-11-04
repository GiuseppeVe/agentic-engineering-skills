param(
  [Parameter(Mandatory = $true)][string]$Source,
  [Parameter(Mandatory = $true)][string]$Destination
)

$expectedHash = '47edbdFAF27073C47033D1AC7DFEE881BE49E2DCBDA7671D1157300481DDE6DA'
$sourceStream = [System.IO.File]::OpenRead($Source)
$destinationStream = [System.IO.File]::Create($Destination)
$gzipStream = $null
try {
  $gzipStream = [System.IO.Compression.GZipStream]::new(
    $sourceStream,
    [System.IO.Compression.CompressionMode]::Decompress
  )
  $gzipStream.CopyTo($destinationStream)
} finally {
  if ($gzipStream) { $gzipStream.Dispose() }
  $destinationStream.Dispose()
  $sourceStream.Dispose()
}

$hashStream = [System.IO.File]::OpenRead($Destination)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
  $actualHash = [System.BitConverter]::ToString($sha256.ComputeHash($hashStream)).Replace('-', '')
} finally {
  $sha256.Dispose()
  $hashStream.Dispose()
}
if ($actualHash -ne $expectedHash) {
  Remove-Item -LiteralPath $Destination -Force
  throw 'font index checksum mismatch'
}
