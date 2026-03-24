# Contributing to Dingo ClawHub Skill

## How to contribute

1. Fork the [Dingo repository](https://github.com/MigoXLab/dingo)
2. Edit skill files in `clawhub/` (`SKILL.md`, `_meta.json`)
3. Test locally by placing `SKILL.md` in your `~/.openclaw/skills/` directory
4. Submit a pull request

## What to update

- **SKILL.md**: Add new evaluators, update config examples, fix instructions
- **_meta.json**: Update version, tags, or dependency info

## Guidelines

- Keep instructions concise — the agent's context window is limited
- Always include working config examples for new features
- Test with both rule-based and LLM-based evaluators
- Update the evaluator tables when new evaluators are added to Dingo

## Questions?

Open an issue on [GitHub](https://github.com/MigoXLab/dingo/issues) or join us on [Discord](https://discord.gg/Jhgb2eKWh8).
