# Historical migration fixture

`story-codex-0.2.0.zip` is the unchanged local Story Codex 0.2.0 skill archive retained before the schema 2 migration. Its MIT license is inside the ZIP. It is a test input, not the current installable skill or a newly published GitHub Release.

SHA-256: `efdfd997ecac9564fc737b22df8969c7770858a354084132c7d1ce274486a37e` (29,325 bytes).

`test_long_storage.py` checks this digest before loading the old runtime to create authentic schema 1 books. Keeping the fixture in the repository makes migration unit tests runnable in a fresh checkout; it replaces the test's dependency on ignored local `dist/` content. Historical real-book capacity/migration probes remain separate from these unit tests.
