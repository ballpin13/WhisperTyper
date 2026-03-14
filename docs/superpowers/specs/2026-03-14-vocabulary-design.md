# Ordlista för Whisper — Designspecifikation

## Syfte

Ge användaren möjlighet att ange ord och termer som Whisper ska känna igen korrekt vid transkribering. Löser problemet att Whisper kan feltolka namn, facktermer och domänspecifika ord.

## Lösning

En fritextruta i Inställningar-fliken där användaren skriver ord (ett per rad). Orden skickas som `initial_prompt` till faster-whisper vid varje transkribering, vilket ger modellen kontext att matcha ljudet mot rätt ord.

## Config

- Nytt fält `vocabulary` i `DEFAULT_CONFIG`: tom lista `[]`
- Lagras i `config.json` som `"vocabulary": ["Kubernetes", "Sveavägen", "PostgreSQL"]`
- `ConfigManager` får två nya metoder:
  - `get_vocabulary() -> list[str]` — returnerar ordlistan
  - `set_vocabulary(words: list[str])` — sparar ordlistan

## UI — Inställningar-fliken

Ny sektion **"Ordlista"** placerad direkt efter Whisper-sektionen (modell/språk/enhet).

Innehåll:
- Sektionslabel: **"Ordlista"** (samma styling som övriga: Segoe UI 11pt bold, #333)
- Hjälptext: *"Ange ord som Whisper ska känna igen, ett per rad"* (liten grå text)
- `QPlainTextEdit` — fri redigering, ett ord/term per rad, max höjd 120px
- **"Spara"**-knapp under textrutan

Samma card-styling som övriga sektioner (vit bakgrund, #e0e0e0 border, 8px radius, 12px padding).

## Engine

I `transcribe()`-anropet (`engine.py`):
- Läs ordlistan via `self.config.get_vocabulary()`
- Om listan inte är tom: bygg en kommaseparerad sträng och skicka som `initial_prompt`
- Om listan är tom: skicka ingen `initial_prompt`

```python
vocab = self.config.get_vocabulary()
initial_prompt = ", ".join(vocab) if vocab else None

segments, info = self.model.transcribe(
    tmp_path,
    language=lang,
    beam_size=1,
    condition_on_previous_text=True,
    initial_prompt=initial_prompt,
)
```

## Avgränsningar

- Ingen kategorisering eller profiler — en enda global lista
- Påverkar bara Whisper-transkribering, inte AI-redigering
- Ingen import/export
- Ingen validering av orden (användaren ansvarar för korrekt stavning)

## Filer som ändras

| Fil | Ändring |
|-----|---------|
| `config.py` | Lägg till `vocabulary` i `DEFAULT_CONFIG`, nya metoder |
| `ui/tab_settings.py` | Ny "Ordlista"-sektion i UI |
| `engine.py` | Skicka `initial_prompt` i `transcribe()` |
