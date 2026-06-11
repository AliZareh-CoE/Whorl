# MCP LaTeX tools (beyond-Overleaf B4) — plan of record, executed cycle 114

Parallel planning agent (cycle 113→114). Owner idea #24 beyond-Overleaf B4.

## Verdict: ~zero new Django
manuscript-files CRUD + ManuscriptViewSet compile/compile-status already exist in DRF.
Only gap: word-count was classic-only → added a read-only `word-count` @action on
ManuscriptViewSet (faithful port of word_count_view, reuses writing.wordcount).

## Tools (all wrap /api/v1/, X-API-Key auth via AtlasViewSet)
list_manuscripts(project) · get_manuscript(id) · list_manuscript_files(id) ·
read_manuscript_file(file_id) · write_manuscript_file(id, path, content) [create-or-update
by path] · set_main_file(file_id) · compile_manuscript(id) · get_compile_status(id) ·
get_compile_diagnostics(id) · compile_and_wait(id, timeout) · latex_word_count(id).

## Key facts verified in code
- latex_source↔main-file alias is bidirectional+automatic; compile reads source_text()
  (main file). MCP writes files via manuscript-files; never touches latex_source. No drift.
- compile returns 202 immediately (huey: Redis in prod, immediate in dev). compile_and_wait
  polls compile-status paced by the HTTP round-trip + a datetime deadline — NO time import,
  so client.py imports stay ⊆ {os, datetime, httpx} (AST test holds).
- compile-status returns NO ETag → never cached → every poll fresh.
- successful compile auto-snapshots a revision (history for free).

## Sharp edges
async poll (compile_and_wait default + explicit pair); alias (write main file only); auth
(AtlasViewSet key-auth); diagnostics already structured [{level,file,line,message}];
create-vs-update by path client-side; single-main invariant (set only is_main:true);
assets not exposed (text edit→compile loop only; figures = later slice).

## Verified live (cycle 114)
Drove the MCP client against the running app: get_manuscript → write broken main.tex →
compile_and_wait → status failed + diagnostic (line 3 Undefined control sequence) →
write fixed main.tex → recompile → ok + PDF → word count. Full edit→compile→fix loop green.
