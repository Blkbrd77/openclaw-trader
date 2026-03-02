# Jira vs GitHub Issues — OpenClaw Project Evaluation

**Date:** 2026-03-02
**Context:** Solo developer building an AI stock trading system on Raspberry Pi.
Currently using Jira (KAN board) with 38 issues across 7 work packages.

---

## Current Jira Usage

| Metric | Value |
|--------|-------|
| Total issues | 38 (7 epics, 31 stories) |
| Completed | 30 (79%) |
| In Progress | 3 |
| Backlog | 5 |
| Board type | Kanban (5 columns) |
| Automation | REST API via jira-tools.py |
| Cost | Free tier (up to 10 users) |

## Feature Comparison

| Capability | Jira (Free) | GitHub Issues (Free) |
|------------|-------------|----------------------|
| **Issue tracking** | Full (epics, stories, subtasks, bugs) | Issues + labels (flat or milestone-based) |
| **Board view** | Built-in Kanban/Scrum boards | GitHub Projects (board view) |
| **Custom workflows** | 5-column workflow (Idea to Done) | Status columns in Projects |
| **Epics / hierarchy** | Native epic to story to subtask | Manual via labels or tasklists |
| **Sprint planning** | Built-in sprint management | Milestones (less structured) |
| **Automation** | Jira Automation rules + REST API | GitHub Actions + REST/GraphQL API |
| **CI integration** | Webhooks, manual linking | Native (commits close issues, PR links) |
| **Code linking** | Manual or via GitHub for Jira app | Automatic (branch to issue to PR to merge) |
| **Mobile app** | Yes (full-featured) | Yes (basic) |
| **Roadmap view** | Timeline view (free tier) | Projects roadmap view |
| **Custom fields** | Yes | Limited (Projects custom fields) |
| **JQL / search** | Powerful JQL query language | Basic search + filters |
| **User limit** | 10 users free | Unlimited collaborators (public repo) |

## What Jira Does Better

1. **Structured hierarchy** — Epics, Stories, Subtasks maps naturally to Work Packages. GitHub Issues are flat unless you manually layer structure with labels/milestones.

2. **JQL** — Queries like "project = KAN AND parent = KAN-39 AND status != Done" are powerful. GitHub search is more limited.

3. **Sprint/velocity tracking** — If you move to time-boxed sprints, Jira has built-in burndown charts and velocity reports.

4. **Custom workflows** — The 5-column Kanban board with transition rules is easy to enforce. GitHub Projects can replicate this but requires more manual setup.

## What GitHub Issues Does Better

1. **Code integration is seamless** — "Fixes #12" in a commit message auto-closes the issue. Branch names auto-link. PR descriptions reference issues natively. With Jira, you need the GitHub for Jira app or manual linking.

2. **Single platform** — Code, issues, CI, PRs, wiki, and releases all in one place. No context-switching between Jira and GitHub.

3. **Lower friction for contributors** — If OpenClaw ever goes open-source or adds collaborators, GitHub Issues has zero onboarding friction. Jira requires account creation and project access.

4. **GitHub Projects v2** — Board views, custom fields, roadmaps, and automation workflows have gotten significantly better. Covers 90% of what a small team needs.

5. **API simplicity** — gh issue create, gh issue list, gh project commands work out of the box. No separate auth tokens or REST endpoint differences.

## OpenClaw-Specific Assessment

### Current Pain Points with Jira
- **Context switching** — PRs are on GitHub, tickets are on Jira. Linking is manual.
- **Two auth systems** — Maintaining Jira API token + GitHub token + separate automation scripts.
- **Overkill for solo dev** — Not using sprints, story points, or team features. The Kanban board could be replicated in GitHub Projects.
- **jira-tools.py maintenance** — Custom REST API wrapper needed; gh CLI covers GitHub Issues natively.

### What You'd Lose Moving to GitHub Issues
- **JQL power queries** — GitHub search is less expressive.
- **Epic hierarchy** — Would need to use labels (e.g. wp-6, wp-7) or tasklists to group stories.
- **Board polish** — Jira's Kanban board is more mature than GitHub Projects.

### What You'd Gain
- **Auto-linking everything** — A commit message like "Add CI pipeline (fixes #12)" closes the issue, links to the PR, shows in the timeline. Zero manual work.
- **One fewer tool** — Drop Jira API token, jira-tools.py, and the Jira cron/automation layer.
- **Simpler contributor onboarding** — If you ever bring on a second developer or open-source the project.

## Recommendation

**For now: Stay on Jira through WP-7 completion.** The project is 79% done with a working Kanban board and automation. Migrating mid-project adds risk for minimal gain.

**For the next project (or post-launch iteration): Use GitHub Issues + Projects.** The native code integration alone justifies it for a solo developer or small team. The hierarchy gap is manageable with labels and milestones.

**Migration path if you decide to switch:**
1. Create GitHub Project board with matching columns (Idea, To Do, In Progress, In Review, Done)
2. Use gh CLI to bulk-create issues from remaining Jira tickets
3. Add labels for work package grouping (wp-6, wp-7)
4. Archive the Jira KAN board (keep for reference)

## Quick Reference

| If you need... | Use |
|----------------|-----|
| Enterprise PM, multiple teams, sprints | Jira |
| Solo dev / small team, code-first workflow | GitHub Issues + Projects |
| Open source project | GitHub Issues (always) |
| Complex reporting / velocity tracking | Jira |
| Minimal toolchain, maximum integration | GitHub Issues |
