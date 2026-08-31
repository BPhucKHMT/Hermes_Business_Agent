---
name: tiktok
description: "Manage official TikTok Content Posting API integration, query creator profile info, stage video post drafts (Tier 2), and publish video posts with confirmation."
version: 0.1.0
author: Hermes project team
license: MIT
platforms: [windows, linux, darwin]
metadata:
  hermes:
    category: social
    tags: [tiktok, video, post, creator, caption, publish]
---

# TikTok Content Posting API Integration

## Overview

Manage TikTok video posting and creator account status via official TikTok Content Posting API (`https://open.tiktokapis.com/v2/post/publish/...`) with Tier 2 approval guardrails and verifiable publish IDs.

## Capabilities

1. **Creator Info (`tiktok_creator_info`):**
   - Check creator nickname, username, avatar, max allowed video duration, and privacy options.

2. **Tier 2 Post Drafting (`tiktok_create_draft_post`):**
   - Stage a video post draft with caption, hashtags (up to 2200 chars), privacy level (`PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, `SELF_ONLY`, `FOLLOWER_OF_CREATOR`), comment/duet/stitch settings, and commercial content toggle.
   - Generates an idempotency key to prevent accidental duplicate posts.

3. **Video Publishing (`tiktok_publish_video`):**
   - After user confirms via Telegram approval or chat confirmation, executes the publish initialization via the Content Posting API.
   - Returns a `publish_id`.

4. **Post Status (`tiktok_post_status`):**
   - Query the processing status (`PROCESSING_UPLOAD`, `SUCCESS`, `FAILED`) of the submitted video post.

## Operating Rules

- **Tier 2 Draft-Before-Publish:** Always stage caption, hashtags, and privacy settings and present a formatted review summary to the user before publishing.
- **Privacy & Host Identity:** Account management is strictly DM-only per user; requests in group chats redirect to DM.
- **Official API Compliance:** Uses only official TikTok Content Posting API endpoints; no grey automation, browser automation, or credential harvesting.
