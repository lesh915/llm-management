param (
    [Parameter(Mandatory=$false, Position=0)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Command = "status"
)

switch ($Command) {
    "start" {
        & "$PSScriptRoot\scripts\start.ps1"
    }
    "stop" {
        & "$PSScriptRoot\scripts\stop.ps1"
    }
    "status" {
        & "$PSScriptRoot\scripts\status.ps1"
    }
    "restart" {
        & "$PSScriptRoot\scripts\stop.ps1"
        & "$PSScriptRoot\scripts\start.ps1"
    }
}
