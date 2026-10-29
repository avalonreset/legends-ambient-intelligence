# Legends Ambient Intelligence

**Status:** public open-source candidate  
**Version:** `0.1.1`  
**Product brand:** Legends Ambient Intelligence (`legends-ambient-intelligence`)  

## Philosophy

**Ambient capture is not a diary app.**

Ambient intelligence turns the surrounding physical and digital environment into useful signal. Passive experimentation, voice sketchpads, and ambient conversations are safely archived, content-addressed, transcribed offline, and distilled into structured candidates for permanent knowledge stores.

## Banished product names

- Life logger
- Legends Life Logger
- lifelogger

## Ecosystem integration

| Role | Package | Responsibility |
|---|---|---|
| Foreground Voice | `hyperyap` | Active keyboard-focused speech-to-text dictation |
| Background Audio | `legends-ambient-intelligence` | Passive capture, deduplication, batch ASR, prompt recovery |
| Knowledge Sink | `legends-empire` | Source-cited markdown vault memory and research evidence |
| Front Door | `cto-legends` | CLI catalog, module environment isolation, and skill routing |

## Operational readiness

```powershell
python -m legends_ambient doctor
```
