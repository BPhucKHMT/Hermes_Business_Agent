param([string]$RepositoryRoot=(Resolve-Path (Join-Path $PSScriptRoot "../..")))
$ErrorActionPreference="Stop"
$manifestPath=Join-Path $RepositoryRoot ".claude\claude-kit.manifest.json"
if(!(Test-Path $manifestPath)){throw "Claude adapter manifest is missing; run sync-claude-kit.ps1"}
$manifest=Get-Content $manifestPath -Raw|ConvertFrom-Json
$canonicalSkills=@(Get-ChildItem "$RepositoryRoot\.agents\skills" -Directory|Where-Object{Test-Path "$($_.FullName)\SKILL.md"})
$canonicalAgents=@(Get-ChildItem "$RepositoryRoot\.agents\agent" -File -Filter '*.md')
$canonicalCommands=@(Get-ChildItem "$RepositoryRoot\.agents\workflows" -File -Filter '*.md')
if($manifest.skills.Count-ne$canonicalSkills.Count){throw "Skill adapter count mismatch: $($manifest.skills.Count)/$($canonicalSkills.Count)"}
if($manifest.agents.Count-ne$canonicalAgents.Count){throw "Agent adapter count mismatch: $($manifest.agents.Count)/$($canonicalAgents.Count)"}
if($manifest.commands.Count-ne$canonicalCommands.Count){throw "Command adapter count mismatch: $($manifest.commands.Count)/$($canonicalCommands.Count)"}
foreach($path in @($manifest.skills)+@($manifest.agents)+@($manifest.commands)){$full=Join-Path $RepositoryRoot $path;if(!(Test-Path $full)){throw "Missing adapter: $path"};$text=Get-Content $full -Raw;if($text-notmatch 'generated-by: .agents/scripts/sync-claude-kit.ps1'){throw "Unmanaged adapter: $path"};$match=[regex]::Match($text,'\.agents/(?:skills|agent|workflows)/[^`\s]+');if(!$match.Success-or!(Test-Path(Join-Path $RepositoryRoot $match.Value))){throw "Broken canonical reference: $path"}}
Get-Content "$RepositoryRoot\.claude\settings.json" -Raw|ConvertFrom-Json|Out-Null
$mcp=Get-Content "$RepositoryRoot\.mcp.json" -Raw|ConvertFrom-Json
if(($mcp|ConvertTo-Json -Depth 10)-match 'YOUR_API_KEY'){throw 'Placeholder secret leaked into .mcp.json'}
"Claude kit verification: pass ($($manifest.skills.Count) skills, $($manifest.agents.Count) agents, $($manifest.commands.Count) commands)."