# Trusted launcher transport. Only this controller selects Runner arguments.
$script:CopilotHarnessRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:CopilotRepositoryRoot = if ($env:ROBOT_LEARNING_CAMPAIGN_ROOT) {
    $env:ROBOT_LEARNING_CAMPAIGN_ROOT
} else {
    $script:CopilotHarnessRoot
}
$script:RunnerPublicationFailureExitCode = 3

function Get-CopilotOperationState {
    param([Parameter(Mandatory)]$State)

    $session = $State.scientific_session
    $availability = Get-RunnerOperationAvailability -State $State
    return @{
        campaign_id = [string]$State.campaign.id
        session_id = if ($session) { [string]$session.id } else { $null }
        backend_session_id = if ($session) { [string]$session.backend_session_id } else { $null }
        session_kind = if ($session) { [string]$session.kind } else { $null }
        operation_event_count = @($State.operation_events).Count
        completed_operations = @(if ($session) { $session.operation_ids })
        allowed_operations = @($availability.allowed_operations)
        checkpoint_required = [bool]$availability.checkpoint_required
        transition = $availability.checkpoint_reason
        next_question = $availability.next_question
        model_roles = $State.model_roles
        pending = if ($State.pending_operation) {
            @{
                id = $State.pending_operation.id
                progress = $State.pending_operation.progress
                failure = $State.pending_operation.failure
                request_fingerprint = $State.pending_operation.request_fingerprint
                metadata_path = "/pending"
            }
        } else { $null }
        terminal = $State.terminal_state
        resources = Get-CampaignResourceSummary -State $State
        brief = "campaigns/brief.md"
    }
}

function Read-CopilotControlMessage {
    param([int]$TimeoutSeconds = 0)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $read = $script:CopilotReader.ReadLineAsync()
    while (-not $read.Wait(100)) {
        if ($TimeoutSeconds -gt 0 -and [DateTime]::UtcNow -ge $deadline) {
            throw "Copilot controller readiness timed out."
        }
        if (
            (Test-CampaignStopRequested) -and
            [DateTime]::UtcNow -ge $script:StopDeadline
        ) {
            $script:StopDeadlineExceeded = $true
            throw "Copilot controller cooperative stop deadline expired."
        }
        if ($script:CopilotProcess.HasExited) {
            throw "Copilot runtime exited with code $($script:CopilotProcess.ExitCode)."
        }
    }
    $line = $read.GetAwaiter().GetResult()
    if (-not $line) {
        throw "Copilot control channel closed; durable Runner state must be recovered."
    }
    return ConvertFrom-Json -InputObject $line -Depth 100
}

function Send-CopilotControlMessage {
    param([Parameter(Mandatory)]$Message)
    $script:CopilotWriter.WriteLine(
        (ConvertTo-Json -InputObject $Message -Depth 100 -Compress)
    )
    $script:CopilotWriter.Flush()
}

function Get-RunnerSubmissionError {
    $errorText = if ($script:ProcessStderr) {
        $script:ProcessStderr
    } else { $script:ProcessOutput }
    $lines = @($errorText -split '\r?\n' | Where-Object { $_.Trim() })
    if ($lines.Count) {
        return ($lines -join [Environment]::NewLine).Trim()
    }
    return "Runner failed without an error message; transaction state is preserved."
}

function Start-PersistentCopilotRuntime {
    if (Test-CampaignStopRequested) {
        return
    }
    if ($script:CopilotProcess) {
        if ($script:CopilotProcess.HasExited) {
            throw "The owned Copilot runtime stopped; refusing an in-run replacement."
        }
        return
    }
    Enter-TrustedMutableInvocation
    if (-not $script:StopRequestPath) {
        $stopDirectory = Join-Path $script:CopilotRepositoryRoot ".copilot\controller-stops"
        [void][System.IO.Directory]::CreateDirectory($stopDirectory)
        $script:StopRequestPath = Join-Path $stopDirectory "$([guid]::NewGuid()).stop"
    }
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback, 0
    )
    $listener.Start()
    $token = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = (Get-Command uv -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    $startInfo.WorkingDirectory = $script:CopilotRepositoryRoot
    $startInfo.UseShellExecute = $false
    $startInfo.Environment["ROBOT_RESEARCH_STOP_REQUEST"] = $script:StopRequestPath
    foreach ($argument in @(
        "run", "--project", $script:CopilotHarnessRoot, "--group", "researcher",
        "python", "-m", "runner.copilot.copilot_adapter",
        "--controller-port", "$($listener.LocalEndpoint.Port)",
        "--controller-token", $token, "--model", $Model, "--reasoning", $Reasoning
    )) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    $script:CopilotProcess = [System.Diagnostics.Process]::new()
    $script:CopilotProcess.StartInfo = $startInfo
    try {
        if (-not $script:CopilotProcess.Start()) {
            throw "Could not start the owned Copilot runtime."
        }
        $accept = $listener.AcceptTcpClientAsync()
        $deadline = [DateTime]::UtcNow.AddSeconds(120)
        while (-not $accept.Wait(100)) {
            if (Test-CampaignStopRequested) {
                return
            }
            if (
                $script:CopilotProcess.HasExited -or
                [DateTime]::UtcNow -ge $deadline
            ) {
                throw "Copilot runtime did not connect to its launcher."
            }
        }
        $script:CopilotConnection = $accept.GetAwaiter().GetResult()
        $stream = $script:CopilotConnection.GetStream()
        $encoding = [System.Text.UTF8Encoding]::new($false)
        $script:CopilotReader = [System.IO.StreamReader]::new($stream, $encoding)
        $script:CopilotWriter = [System.IO.StreamWriter]::new($stream, $encoding)
        $hello = Read-CopilotControlMessage -TimeoutSeconds 120
        if ($hello.type -ne "ready" -or $hello.token -cne $token) {
            throw "Copilot controller authentication or runtime readiness failed."
        }
    }
    finally {
        $listener.Stop()
    }
}

function Invoke-CopilotOperationSubmission {
    param(
        [Parameter(Mandatory)]$Message,
        [Parameter(Mandatory)]$Binding
    )

    Enter-TrustedMutableInvocation
    $state = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
    $response = @{
        type = "operation_result"
        invocation_id = $Binding.invocation_id
        call_id = $Message.call_id
        status = "rejected"
        error = $null
        state = Get-CopilotOperationState -State $state
    }
    if (Test-CampaignStopRequested) {
        $response.status = "interrupted"
        $response.error = "Campaign stop requested."
        return $response
    }
    if (
        $Message.invocation_id -cne $Binding.invocation_id -or
        $Message.session_id -cne $Binding.session_id -or
        $Message.campaign_id -cne $Binding.campaign_id -or
        $state.campaign.id -cne $Binding.campaign_id -or
        -not $state.scientific_session -or
        $state.scientific_session.backend_session_id -cne $Binding.session_id -or
        $state.scientific_session.id -cne $Binding.scientific_session_id -or
        $state.terminal_state
    ) {
        $response.status = "session_ended"
        $response.error = "Submission does not belong to the active bounded session."
        return $response
    }
    if ($Message.event_count -ne @($state.operation_events).Count) {
        $response.status = "recovery_required"
        $response.error = "Runner state changed; recover durable state before submitting again."
        return $response
    }
    if ($state.pending_operation -and (
        -not $state.pending_operation.failure -or
        $state.pending_operation.progress -in @("result_ready", "completed")
    )) {
        $response.status = "recovery_required"
        $response.error = "Accepted transaction requires controller recovery, not another submission."
        return $response
    }

    $payload = ConvertTo-Json -InputObject $Message.request -Depth 100 -Compress
    $exitCode = Invoke-Runner -Arguments @("--check-operation-input") `
        -InputText $payload -CaptureOutput
    $validation = $script:ProcessOutput.Trim()
    if (Test-CampaignStopRequested) {
        $response.status = "interrupted"
        $response.error = $validation
        return $response
    }
    if ($exitCode -ne 0) {
        $response.error = $validation
        return $response
    }
    if ($null -eq $Message.request) {
        $exitCode = Invoke-Runner -Arguments @("--reaccept-pending") -StreamOutput
        if ($exitCode -eq 0) {
            $exitCode = Invoke-Runner -Arguments @("--execute-pending") -StreamOutput
        }
    }
    else {
        Enter-TrustedMutableInvocation
        [System.IO.File]::WriteAllText(
            (Join-Path $script:CopilotRepositoryRoot "pi_workspace\operation_request.json"),
            $payload, [System.Text.UTF8Encoding]::new($false)
        )
        $exitCode = Invoke-Runner -StreamOutput
    }
    $errorDetail = Get-RunnerSubmissionError
    $current = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
    $response.state = Get-CopilotOperationState -State $current
    $newCompleted = @($current.operation_events |
        Select-Object -Skip @($state.operation_events).Count |
        Where-Object { $_.status -eq "completed" })
    $response.operation_id = if ($current.pending_operation) {
        $current.pending_operation.id
    } elseif ($newCompleted.Count) { $newCompleted[-1].id } else { $null }
    if (
        $exitCode -eq $script:RunnerPublicationFailureExitCode -or
        $current.pending_operation.progress -in @("result_ready", "completed") -or
        ($exitCode -ne 0 -and $newCompleted.Count -gt 0)
    ) {
        $response.status = "publication_fatal"
        $response.error = $errorDetail
    }
    elseif (Test-CampaignStopRequested) {
        $response.status = "interrupted"
        $response.error = "Runner interrupted; its pending/completed transaction is preserved."
    }
    elseif ($exitCode -ne 0) {
        $response.status = if ($current.pending_operation.failure) {
            "implementation_error"
        } else { "controller_fatal" }
        $response.error = if ($current.pending_operation.failure) {
            [string]$current.pending_operation.failure
        } else { $errorDetail }
        if ($response.status -eq "implementation_error") {
            $measurements = @($current.pending_operation.data.measurements)
            $completedCount = @($current.pending_operation.data.partial_results).Count
            if ($current.pending_operation.kind -eq "measurement" -and
                $completedCount -lt $measurements.Count) {
                $response.accepted_measurement = $measurements[$completedCount]
            }
            Update-ResearchBrief
        }
    }
    else {
        Update-ResearchBrief
        $response.status = if (
            -not $current.scientific_session -or $current.terminal_state
        ) { "session_ended" } else { "completed" }
        $response.result = Get-LatestSessionResult -State $current
    }
    return $response
}

function Invoke-PersistentCopilotSession {
    param(
        [Parameter(Mandatory)][string[]]$SessionArguments,
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)]$State,
        [switch]$Preliminary
    )

    Start-PersistentCopilotRuntime
    if (Test-CampaignStopRequested) {
        return 130
    }
    $binding = @{
        type = "session"
        invocation_id = [guid]::NewGuid().ToString()
        session_id = $script:PISessionId
        scientific_session_id = if ($Preliminary) { $null } else { $State.scientific_session.id }
        campaign_id = [string]$State.campaign.id
        arguments = @($SessionArguments) + @($Prompt)
        state = Get-CopilotOperationState -State $State
    }
    Send-CopilotControlMessage -Message $binding
    while ($true) {
        $message = Read-CopilotControlMessage
        if ($message.invocation_id -cne $binding.invocation_id) {
            throw "Copilot returned a message for a different logical invocation."
        }
        if ($message.type -eq "session_result") {
            $script:CopilotSessionOutcome = $message
            return [int]$message.exit_code
        }
        if ($message.type -ne "operation" -or $Preliminary) {
            throw "Unexpected control message from the bounded Copilot session."
        }
        try {
            $response = Invoke-CopilotOperationSubmission -Message $message -Binding $binding
        }
        catch {
            $response = @{
                type = "operation_result"
                invocation_id = $binding.invocation_id
                call_id = $message.call_id
                status = "controller_fatal"
                error = $_.Exception.Message
            }
        }
        Send-CopilotControlMessage -Message $response
    }
}

function Assert-CopilotSessionOutcome {
    if ($script:PIExitCode -ne 0) {
        throw "Copilot bounded session failed: $($script:CopilotSessionOutcome.error)"
    }
    if ($script:CopilotSessionOutcome.status -ne "session_ended") {
        throw "Copilot bounded session ended without a checkpoint or terminal commitment."
    }
}

function Stop-PersistentCopilotRuntime {
    if (-not $script:CopilotProcess) {
        return
    }
    try {
        if (-not $script:CopilotProcess.HasExited) {
            if (-not $script:CopilotWriter -and (Test-CampaignStopRequested)) {
                # No session command could have been sent without a channel.
                # Cancel only the owned bootstrap tree, not a scientific session.
                $graceMs = 5000
                if ($script:StopDeadline) {
                    $graceMs = [int][Math]::Max(0, [Math]::Min(
                        $graceMs, ($script:StopDeadline - [DateTime]::UtcNow).TotalMilliseconds
                    ))
                }
                if (-not $script:CopilotProcess.WaitForExit($graceMs)) {
                    $script:CopilotProcess.Kill($true)
                    if (-not $script:CopilotProcess.WaitForExit(5000)) {
                        throw "Owned Copilot bootstrap did not exit after cancellation."
                    }
                }
                return
            }
            if ($script:CopilotWriter) {
                try {
                    Send-CopilotControlMessage -Message @{ type = "shutdown" }
                }
                catch {
                    # Channel loss still requires stopping only the owned process.
                }
            }
            if (-not $script:CopilotProcess.WaitForExit(45000)) {
                $script:CopilotProcess.Kill($true)
                $script:CopilotProcess.WaitForExit()
                throw "Owned Copilot runtime exceeded its cooperative shutdown deadline."
            }
        }
    }
    finally {
        if ($script:CopilotWriter) { $script:CopilotWriter.Dispose() }
        if ($script:CopilotReader) { $script:CopilotReader.Dispose() }
        if ($script:CopilotConnection) { $script:CopilotConnection.Dispose() }
        $script:CopilotProcess.Dispose()
        $script:CopilotProcess = $null
    }
}
