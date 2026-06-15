; Atlas NSIS installer hooks (#242).
;
; The bundled server (atlas-server.exe) and the Postgres it starts (postgres.exe) can still be
; running when the user reinstalls/updates, holding pg\bin\postgres.exe and atlas-server.exe
; open — which makes the installer fail with "Error opening file for writing". Stop those
; processes before copying files (install) and before deleting them (uninstall), so an update
; over a running app just works. /T also ends child processes; errors are ignored if none run.

!macro NSIS_HOOK_PREINSTALL
  nsExec::Exec 'taskkill /F /T /IM atlas-server.exe'
  nsExec::Exec 'taskkill /F /T /IM postgres.exe'
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::Exec 'taskkill /F /T /IM atlas-server.exe'
  nsExec::Exec 'taskkill /F /T /IM postgres.exe'
!macroend
