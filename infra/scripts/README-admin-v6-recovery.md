# Local administrator V6 recovery

This runbook is only for a local `eyesonu` database that already recorded
`V6__admin_roles_and_status.sql` before the official candidate-event V6 was
merged. It preserves application rows and administrator role/status values.

Do not use these scripts against a shared dev, staging, or production database.
Do not use `flyway repair`: it would make Flyway accept the official V6 without
actually applying the candidate-event schema.

## Required sequence

1. Stop the normal backend and keep it unreachable until the sequence finishes.
2. Create and verify an external `mysqldump` of the complete `eyesonu` schema.
3. Run `reconcile-local-admin-v6-before-flyway.sql` with the MySQL CLI.
4. Build a clean JAR and run it with `server.port=-1`, which retains the servlet
   security context without opening an HTTP listener. Disable bootstrap and
   RabbitMQ listeners for this one process:

   ```powershell
   $settings = @{}
   Get-Content -LiteralPath "infra/.env" | ForEach-Object {
     $line = $_.Trim()
     if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
       $parts = $line.Split('=', 2)
       $settings[$parts[0].Trim()] = $parts[1].Trim()
     }
   }
   $settings.GetEnumerator() | ForEach-Object {
     Set-Item -Path ("Env:" + $_.Key) -Value $_.Value
   }
   $env:EYESONU_AUTH_BOOTSTRAP_ENABLED = "false"

   Push-Location "apps/backend-api/eyesonu"
   .\mvnw.cmd clean package -DskipTests
   $jar = Get-ChildItem -LiteralPath "target" -Filter "eyesonu-*.jar" |
     Where-Object { $_.Name -notlike "*.original" } |
     Select-Object -First 1 -ExpandProperty FullName
   java.exe -jar $jar `
     --spring.profiles.active=local `
     --server.port=-1 `
     --spring.rabbitmq.listener.simple.auto-startup=false `
     --spring.rabbitmq.listener.direct.auto-startup=false
   Pop-Location
   ```

   Wait until the logs report `Successfully applied 2 migrations` and
   `Tomcat started on port -1`. Confirm the process owns no `LISTENING` socket,
   then terminate it before continuing. Flyway must record:

   - V6: `V6__realtime_candidate_event_model.sql`
   - V7: `V7__admin_roles_and_status.sql`
5. Stop the migration-only process before accepting any traffic.
6. Run `reconcile-local-admin-v6-after-flyway.sql` with the MySQL CLI.
7. Verify application row counts, active `SUPER_ADMIN` count, candidate-event
   tables, and V6/V7 Flyway history before starting the normal backend.

Both SQL files use the MySQL client's `DELIMITER` command. Do not execute them
through a generic JDBC statement runner.

## Partial failure handling

The scripts fail closed but are intentionally one-shot because MySQL DDL commits
implicitly. Never drop the backup table or blindly rerun a failed step.

| Observed state | Action |
| --- | --- |
| Backup table absent; local administrator V6 history present | The pre-step did not change the schema. Fix the reported precondition and retry. |
| Backup table present; `admins.role/enabled` and old V6 history present | Stop and inspect the failed pre-step. Restore the external dump if the exact state is unclear. |
| Backup table present; `admins.role/enabled` absent; old V6 history present | The DDL completed but history cleanup did not. Verify the backup, then remove only the exact old V6 row before continuing. |
| Backup table present; no V6 history; `candidates.image_s3_key` still present; `crop_object_key` and candidate-event tables absent | The pre-step completed and no official V6 attempt began. Run only the `server.port=-1` Flyway step. |
| Backup table present; no V6 history; candidate schema differs from the preceding row | An official V6 attempt may have failed partially. Do not retry; restore the verified external dump. |
| Backup table present; official V6 and administrator V7 present | Run the post-step once. |
| Backup table absent; official V6 and administrator V7 present | Recovery completed successfully. |

If any state differs from this table, stop and restore the verified external dump
rather than modifying Flyway history speculatively.
