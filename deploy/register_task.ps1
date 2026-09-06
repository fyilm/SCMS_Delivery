# 注册 Windows 任务计划：每日定时执行 SCMS 数据管道（ETL + 质量 + 对账）
# 用法（PowerShell，管理员或当前用户）：
#   .\deploy\register_task.ps1
param(
    [string]$TaskName = "SCMS_Delivery_Pipeline",
    [string]$Time = "02:00"
)

$Root = Split-Path -Parent $PSScriptRoot
$cmd = "cd '$Root'; uv run python deploy/run_pipeline.py"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "已注册任务计划：$TaskName（每天 $Time）"
Write-Host "查看：Get-ScheduledTask -TaskName $TaskName"
