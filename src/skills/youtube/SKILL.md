---
name: youtube
description: "Manage official YouTube Channel video metadata, stage video upload drafts (Tier 2), and execute video uploads with 1-tap confirmation."
version: 0.1.0
author: Hermes project team
license: MIT
platforms: [windows, linux, darwin]
metadata:
  hermes:
    category: social
    tags: [youtube, video, upload, channel, metadata]
---

# YouTube Channel Integration & Video Automation

## Overview

Manage YouTube channel content, video drafts, and uploads via official Google/YouTube Data API v3 with Tier 2 approval guardrails and machine-verifiable video IDs.

## Capabilities

1. **Channel Status (`youtube_channel_status`):**
   - Check channel title, subscriber count, total video count, and connection health.

2. **Video Listing (`youtube_list_videos`):**
   - List recent videos on the channel with title, view count, publish date, and privacy status.

3. **Tier 2 Video Drafting (`youtube_create_draft_video`):**
   - Stage a video upload draft with title, description, tags, privacy level (`private`, `unlisted`, `public`), video file path, and custom thumbnail.
   - Generates an idempotency key to prevent duplicate uploads.

4. **Video Upload (`youtube_upload_video`):**
   - After user confirms via Telegram approval or chat confirmation, executes the upload to YouTube.
   - Returns verified YouTube Video ID and watch URL (`https://www.youtube.com/watch?v=...`).

5. **Metadata Updates (`youtube_update_video_metadata`):**
   - Update title, description, tags, or privacy status of existing channel videos.

## Operating Rules

- **Tier 2 Draft-Before-Upload:** Always stage video metadata and present a formatted review summary to the user before uploading.
- **Privacy & Host Identity:** Channel management is strictly DM-only per user; requests in group chats redirect to DM.
- **Validation:** Enforces YouTube policy bounds (titles <= 100 chars, descriptions <= 5000 chars, tags <= 30, supported video formats .mp4, .mov, .webm, .mkv).
