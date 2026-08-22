param([string]$RepositoryRoot=(Resolve-Path (Join-Path $PSScriptRoot "../..")))
$ErrorActionPreference="Stop"
$canonical=Join-Path $RepositoryRoot ".agents"
$claude=Join-Path $RepositoryRoot ".claude"
$marker="<!-- generated-by: .agents/scripts/sync-claude-kit.ps1 -->"
function Field($path,$key){$m=Select-String $path -Pattern "^$([regex]::Escape($key)):\s*(.+)$"|Select-Object -First 1;if($m){$m.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")}else{""}}
function Put($path,$text){New-Item -ItemType Directory -Force (Split-Path $path -Parent)|Out-Null;[IO.File]::WriteAllText($path,$text.TrimEnd()+"`n",[Text.UTF8Encoding]::new($false))}
function Prune($dir,$expected){if(Test-Path $dir){Get-ChildItem $dir -Recurse -File -Filter '*.md'|ForEach-Object{if(($expected -notcontains $_.FullName)-and(Get-Content $_.FullName -Raw).Contains($marker)){Remove-Item $_.FullName -Force}}}}
$skills=@();Get-ChildItem "$canonical\skills" -Directory|ForEach-Object{$source="$($_.FullName)\SKILL.md";if(Test-Path $source){$name=Field $source 'name';if(!$name){$name=$_.Name};$description=Field $source 'description';if(!$description){$description="Use when canonical AG Kit skill '$name' applies."};$target="$claude\skills\$($_.Name)\SKILL.md";Put $target @"
---
name: $name
description: "$($description.Replace('"','\"'))"
---
$marker

Read and apply ``.agents/skills/$($_.Name)/SKILL.md`` completely before acting. Canonical file and companions own workflow. Translate tool names to Claude equivalents; stop on unsafe capability gaps.
"@;$skills+=$target}}
Prune "$claude\skills" $skills
$agents=@();Get-ChildItem "$canonical\agent" -File -Filter '*.md'|ForEach-Object{$name=Field $_.FullName 'name';if(!$name){$name=$_.BaseName};$description=Field $_.FullName 'description';if(!$description){$description="Use for canonical $name specialist tasks."};$target="$claude\agents\$($_.Name)";Put $target @"
---
name: $name
description: "$($description.Replace('"','\"'))"
tools: Read, Grep, Glob, Bash, Edit, Write
model: inherit
---
$marker

Read and follow ``.agents/agent/$($_.Name)``. Load every frontmatter skill from ``.agents/skills/<name>/SKILL.md``. Use Claude native agents/tasks/permissions without broadening access; stop on unsafe capability gaps.
"@;$agents+=$target}
Prune "$claude\agents" $agents
$commands=@();Get-ChildItem "$canonical\workflows" -File -Filter '*.md'|ForEach-Object{$description=Field $_.FullName 'description';if(!$description){$description="Run canonical AG Kit workflow $($_.BaseName)."};$target="$claude\commands\$($_.Name)";Put $target @"
---
description: "$($description.Replace('"','\"'))"
argument-hint: "[arguments]"
---
$marker

Read and execute ``.agents/workflows/$($_.Name)``. Arguments: ``$ARGUMENTS``. Load declared agents/skills. Map artifacts/tasks to Claude native primitives while preserving approvals, stop conditions, and verification gates.
"@;$commands+=$target}
Prune "$claude\commands" $commands
$settings=@{hooks=@{PreToolUse=@(@{matcher='Bash';hooks=@(@{type='command';command='node .agents/hooks/validate-tool-call.mjs';timeout=10})})}}|ConvertTo-Json -Depth 10;Put "$claude\settings.json" $settings
Put "$RepositoryRoot\.mcp.json" (@{mcpServers=@{}}|ConvertTo-Json -Depth 4)
$relative={param($p)$p.Substring($RepositoryRoot.Length+1).Replace('\','/')};$manifest=@{schemaVersion='1.0.0';canonicalRoot='.agents';generatedBy='.agents/scripts/sync-claude-kit.ps1';skills=@($skills|ForEach-Object{&$relative $_});agents=@($agents|ForEach-Object{&$relative $_});commands=@($commands|ForEach-Object{&$relative $_})}|ConvertTo-Json -Depth 10;Put "$claude\claude-kit.manifest.json" $manifest
"Claude adapters synced: $($skills.Count) skills, $($agents.Count) agents, $($commands.Count) commands."