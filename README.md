# System Design Repository

## Purpose

This repository is a collaborative space for contributors to submit system design proposals covering both High-Level Design (HLD) and Low-Level Design (LLD). Each proposal should include diagrams, code snippets, testing instructions, and optional HTML visualization.

The goal is to maintain a consistent, high-quality collection of design solutions that are easy to review, learn from, and extend.

## Repository Structure

Each design submission should be placed in its own folder under the repository root. A suggested structure is:

- `design-name/`
  - `hld/`
    - `hld-design.pdf`
  - `lld/`
    - `lld-models.pdf`
    - `lld-services.pdf`
  - `code/`
    - `README.md`
    - source files for the snippet
  - `visualization/` (optional)
    - `index.html`
    - assets/

If your design only needs one subfolder for HLD or LLD, organize it clearly and keep the repository structure easy to follow.

## Submission Requirements

Every PR against `main` should include the following items:

1. Excalidraw PDF of the LLD data models and services
   - Include one or more PDF exports that show entity relationships, service boundaries, and detailed component interactions.

2. Working, well-organized folder containing code snippets
   - The code should reflect the design problem being solved.
   - Keep sample code concise, readable, and easy to run.
   - Prefer a dedicated `code/` subfolder for related files.

3. Excalidraw PDF of the HLD
   - Provide a high-level architecture diagram showing system components, deployment, data flow, and integration points.

4. A `README.md` explaining how to test the snippet
   - Include setup steps, dependencies, commands to run, and expected behavior.
   - The README should make testing straightforward for reviewers.

5. Bonus: HTML visualization
   - Optional but encouraged.
   - Use `visualization/index.html` or a similar file to provide interactive or rendered design visuals.

## Contribution Guidelines

Follow these guidelines when creating a new design proposal:

- Create a new folder with a descriptive name for your design problem.
- Keep design files, code, and documentation grouped together.
- Use PDF exports from Excalidraw for any architecture or model diagrams.
- Ensure code samples are runnable and include instructions.
- Keep commits clean, incremental, and easy to review.
- Use verbose commit messages that clearly explain what changed and why.
- Keep file names consistent, simple, and lowercase when possible.
- Avoid large binary files unless necessary; PDFs are acceptable for diagrams.

## Local Setup

To work with this repository locally:

1. Clone the repository:

```bash
git clone <repository-url>
cd system-design
```

2. Create a branch for your work using the pattern `{github_username}/{design_problem}`:

```bash
git checkout -b <github_username>/<design_problem>
```

3. Add your design proposal in a new directory.

4. Commit your changes and push your branch:

```bash
git add .
git commit -m "Add system design proposal for <topic>"
git push origin feature/<short-description>
```

## PR Checklist

Before raising a PR against `main`, verify that you have:

- [ ] Added a dedicated folder for your design proposal
- [ ] Included an HLD Excalidraw PDF
- [ ] Included an LLD Excalidraw PDF for data models and services
- [ ] Added a working code snippet folder
- [ ] Added a `README.md` for testing your snippet
- [ ] Optionally added HTML visualization for your design
- [ ] Verified the code sample runs locally and the instructions are accurate
- [ ] Confirmed the PR is against the `main` branch and uses a feature branch for work

## Testing Your Submission

Each proposal must include clear testing instructions in its own `README.md`. A strong testing document should include:

- Required dependencies
- Installation or setup commands
- How to execute the example
- Expected output or behavior
- Any environment variables or configuration needed

Example testing instructions:

````markdown
# Testing

1. Install dependencies:
   ```bash
   npm install
   ```
````

2. Run the example:
   ```bash
   node index.js
   ```
3. Confirm output:
   - The service should start on port 3000
   - Request `/health` and verify status 200

```

## HTML Visualization (Bonus)

If you include HTML-based visualization, please place it in a logical folder such as `visualization/`.

Recommended contents:

- `visualization/index.html`
- supporting CSS/JS assets
- a short `README.md` or comments explaining how to open and view the visualization

HTML visualization can help reviewers see the architecture or flow in an interactive way.

## Review Process

When submitting a PR:

- Target the `main` branch from a feature branch.
- Provide a concise PR description summarizing the design goal and what is included.
- Reference any related issues or discussion if available.
- Keep the PR focused on a single design submission.

## Best Practices

- Use clear naming conventions and consistent folder layout.
- Keep diagrams updated and aligned with your code examples.
- Prefer minimal, executable examples instead of large or incomplete prototypes.
- Explain assumptions and trade-offs in your design documentation.

## License

This repository is intended for collaborative learning and contribution. If desired, add a license file or clarify the preferred licensing model in a follow-up update.
```
