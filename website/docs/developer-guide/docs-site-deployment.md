---
id: docs-site-deployment
title: Docs Site Deployment
description: How the YYC3 Hermes Agent fork deploys its docs site and brand assets to GitHub Pages
---

# Docs Site Deployment

This repository is a fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
It publishes its own docs site at **https://agent.yyc3.vip** (GitHub Pages, custom domain) under the
**YYC3 Hermes Agent** brand, while keeping upstream attribution intact.

## Two deployment chains

| | Upstream `deploy-site.yml` | Fork `deploy-pages.yml` |
| --- | --- | --- |
| Trigger | Push to `main` (website paths) | Push to `main` (`website/**`, `pubilc/**`, workflow file) + `workflow_dispatch` |
| Gate | `github.repository == 'NousResearch/hermes-agent'` | `github.repository == 'YYC-Cube/YYC3-Hermes-Agent'` |
| Auth | GitHub App token | Built-in `GITHUB_TOKEN` |
| Skills index | Crawls the live skills library | Reuses the upstream index via CDN GET (`hermes-agent.nousresearch.com/docs/api/skills-index.json`), falls back to `{"skills": []}` |
| Custom domain | — | `pubilc/CNAME` staged at artifact root |
| URL shape | `/docs/` baseUrl | Domain root (`baseUrl: '/'`) |

The fork workflow never calls upstream-generated assets that require the App token; the CDN
re-use keeps the skills catalog fresh with zero API cost.

## Build & stage locally

```bash
cd website
npm ci
npm run build          # outputs build/ (zh-Hans nested, en at root)
```

`deploy-pages.yml` stages the language-prefixed build plus `llms.txt` into `_site/` at the
domain root and copies `pubilc/CNAME` to `_site/CNAME`, then uploads via
`actions/upload-pages-artifact` and deploys with `actions/configure-pages` +
`actions/deploy-pages`. Custom domain + "Enforce HTTPS" are configured in the repo's
Pages settings.

## Brand assets

All icons derive from `pubilc/yyc3-icons/` (iOS, Android, macOS, Windows, tvOS, watchOS sets).

| Target | Source | Notes |
| --- | --- | --- |
| `apps/desktop/assets/icon.icns` | `macos/AppIcon.iconset` | `iconutil -c icns` |
| `apps/desktop/assets/icon.ico` | `windows/windows/icon-256.png` | Pillow `save(format='ICO', sizes=[(16,16)...(256,256)])` — multi-frame |
| `apps/desktop/assets/icon.png`, `apps/desktop/public/apple-touch-icon.png` | `macos/.../icon_512x512@2x.png` | 1024px |
| `web/public/favicon.ico`, `website/static/img/favicon.ico` | `windows/windows/icon-256.png` | Same ICO recipe as desktop |
| `website/static/img/logo.png`, `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png` | icon sets | `website/docusaurus.config.ts` references them |

`electron-builder` resolves `"icon": "assets/icon"` by prefix, so the `.icns`/`.ico`/`.png`
triple replaces the upstream icons without config changes. The desktop app's runtime identity
(`productName: Hermes`, `appId: com.nousresearch.hermes`, protocol handler) intentionally
stays upstream — renaming it would break auto-update and deep links.
