# Collect aggregate Claude Code usage without reading or emitting conversation text.
$ErrorActionPreference = "Stop"
$now = [DateTimeOffset]::UtcNow
$cutoff = $now.AddDays(-7)
$records = @{}
$earliest = $null

Get-ChildItem "$env:USERPROFILE\.claude\projects" -Recurse -Filter *.jsonl -ErrorAction SilentlyContinue | ForEach-Object {
    foreach ($line in Get-Content $_.FullName) {
        try { $entry = $line | ConvertFrom-Json } catch { continue }
        if ($entry.type -ne "assistant" -or -not $entry.message.usage) { continue }
        $key = if ($entry.requestId) { [string]$entry.requestId } elseif ($entry.uuid) { [string]$entry.uuid } else { continue }
        try { $timestamp = [DateTimeOffset]::Parse([string]$entry.timestamp) } catch { continue }
        $usage = $entry.message.usage
        $total = [long]$usage.input_tokens + [long]$usage.output_tokens +
                 [long]$usage.cache_read_input_tokens + [long]$usage.cache_creation_input_tokens
        if (-not $records.ContainsKey($key) -or $total -gt $records[$key].Total) {
            $records[$key] = [pscustomobject]@{ Timestamp = $timestamp; Total = $total }
        }
        if ($null -eq $earliest -or $timestamp -lt $earliest) { $earliest = $timestamp }
    }
}

if ($records.Count -eq 0) { throw "No Claude Code usage records found" }
$lifetime = [long](($records.Values | Measure-Object -Property Total -Sum).Sum)
$rolling = [long](($records.Values | Where-Object Timestamp -ge $cutoff | Measure-Object -Property Total -Sum).Sum)
[ordered]@{
    observed_at = $now.ToString("o")
    tracking_since = $earliest.ToString("o")
    total_tokens = $lifetime
    rolling_7d_tokens = $rolling
} | ConvertTo-Json -Compress
