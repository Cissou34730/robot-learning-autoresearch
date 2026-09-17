# The exclusion identity shared by the research launcher and the reset wrapper.
#
# Both entry points rewrite the campaign artifacts underneath one checkout, so
# they must never run at the same time in the same worktree. Two different
# worktrees own separate artifacts, sessions and mappings, so the exclusion is
# scoped to the worktree rather than to the whole machine: a second checkout no
# longer blocks the first, and neither can strand the other behind a stale lock.
#
# A mutex name cannot contain a path separator, so the canonical worktree path
# is hashed. The hash also fixes the name's length and keeps two spellings of
# the same directory from producing two different identities.

function Get-WorktreeMutexName {
    param(
        [Parameter(Mandatory)][string]$Worktree
    )
    $resolved = (Resolve-Path -LiteralPath $Worktree).ProviderPath
    $canonical = $resolved.Replace('\', '/').TrimEnd([char]'/')
    if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
        # Windows paths are case-insensitive: one directory, one identity.
        $canonical = $canonical.ToLowerInvariant()
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($canonical))
    }
    finally {
        $sha.Dispose()
    }
    $hex = [System.BitConverter]::ToString($digest).Replace('-', '').Substring(0, 16)
    return "Local\RobotLearningAutoresearch-$hex"
}
