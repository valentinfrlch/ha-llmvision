# Contributing to LLM Vision

Thank you for your interest in contributing to **LLM Vision**! All kinds of contributions are welcome, whether you're fixing a bug, adding translations, or adding new features.

---

## Getting Started
>[!TIP]
>Check beta versions and other branches first, before you start working on a new fix/feature. Your fix or feature might already exist!

1. **Fork** the repository and clone it locally.
2. Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes, test them thoroughly (run the tests in `/tests`, and commit with clear, descriptive messages.
4. Open a **Pull Request** against the latest `vX.Y.Z-beta` branch with a summary of what you've changed and why.

---

## Getting Help

If you're unsure about something, have questions about the codebase, or need guidance on how to approach a contribution, don't hesitate to reach out on **[Discord](https://discord.gg/wuFeMfCMRB)**. We're always happy to answer questions and provide support.

You can also check the [Discussions](https://github.com/valentinfrlch/ha-llmvision/discussions) tab for technical questions or browse the [Documentation](https://llm-vision.gitbook.io/getting-started) for context on how things work.

---

## Code Guidelines

- Follow the existing code style and structure.
- Keep changes focused: one feature or fix per PR where possible.
- Include comments where the intent isn't immediately obvious.
- Use type hints to indicate the variable type.
- Run all tests in `/tests`.
- Test your changes against a working Home Assistant instance before submitting.

---

## Use of AI

AI tools are acceptable for **debugging**: using them to understand errors, trace logic, or look up API behavior is fine. However, **purely AI-generated or "vibe-coded" pull requests will not be accepted** and will be closed by maintainers without review.

All contributed code should reflect genuine understanding of what it does and why.

---

## Reporting Bugs & Feature Requests

Please use [GitHub Issues](https://github.com/valentinfrlch/ha-llmvision/issues/new/choose) for bug reports and feature requests rather than pull requests. Check existing issues before opening a new one, and include debug logs for bug reports (debugging can be enabled on the integration's settings page).

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache-2.0 License](LICENSE).
