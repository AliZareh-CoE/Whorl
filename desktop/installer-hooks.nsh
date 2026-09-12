; Atlas NSIS installer hooks (#242).
;
; The bundled server (atlas-server.exe) can still be running when the user reinstalls/updates,
; holding its files open — which makes the installer fail with "Error opening file for
; writing". Stop it before copying files (install) and before deleting them (uninstall), so an
; update over a running app just works. /T also ends child processes; errors are ignored if
; nothing is running.

!macro NSIS_HOOK_PREINSTALL
  nsExec::Exec 'taskkill /F /T /IM atlas-server.exe'
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::Exec 'taskkill /F /T /IM atlas-server.exe'
!macroend
