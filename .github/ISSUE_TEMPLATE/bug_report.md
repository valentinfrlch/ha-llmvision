---
name: "Bug report"
description: Use this when receiving error messages.
labels: "bug"
body:
- type: markdown
  attributes:
    value: |
      Before you open a new issue, search through the existing issues to see if others have had the same problem.
      The issue template is not a suggestion! Please fill out everything that is asked.
- type: checkboxes
  attributes:
    label: Checklist
    options:
      - label: I'm running the newest version of LLM Vision <https://github.com/valentinfrlch/ha-llmvision/releases/latest>
        required: true
      - label: I have enabled debug logging for the integration.
        required: true
      - label: This issue only contains 1 issue (if you have multiple issues, open one issue for each issue).
        required: true
      - label: This is a bug and not a feature request.
        required: true
      - label: This issue is not a duplicate of currently [open](https://github.com/valentinfrlch/ha-llmvision/issues) issues.
        required: true
      - label: I have filled out the issue template to the best of my ability.
        required: true
- type: textarea
  attributes:
    label: "Describe the issue"
    description: "A clear and concise description of what the issue is."
  validations:
    required: true
- type: textarea
  attributes:
    label: Reproduction steps
    description: "Without steps to reproduce, it will be hard to fix!"
    value: |
      1.
      2.
      3.
      ...
  validations:
    required: true
- type: textarea
  attributes:
    label: "Debug logs"
    description: "To enable debug logs check [debugging section in readme](https://github.com/valentinfrlch/ha-llmvision?tab=readme-ov-file#debugging)."
    render: text
  validations:
    required: true
