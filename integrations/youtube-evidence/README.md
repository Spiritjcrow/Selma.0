# Selma° YouTube Evidence Research v0.1

Independent read-only connector for `Spiritjcrow/Selma.0`. This branch changes only `integrations/youtube-evidence/` and does not modify PR #78, SelmaOS runtime, or Android builds.

## Tools
- `youtube_search`: public video metadata search (official YouTube Data API v3).
- `youtube_video_metadata`: public metadata / description / duration.
- `youtube_timestamp_link`: timestamped watch URL, no API key required.
- `youtube_evidence_checklist`: neutral, reproducible video review plan, no API key required.

## Run
Python 3.11+, `pip install -r requirements.txt`, then `python server.py` for a local MCP stdio server. To enable YouTube API endpoints set `YOUTUBE_API_KEY` as a private environment variable. Never commit secrets.

A remote ChatGPT plugin requires an authenticated supported MCP Streamable HTTP deployment or approved secure MCP tunnel and an eligible account/workspace connection. This package does not deploy or activate a plugin, and should **not** be exposed as an unauthenticated public service.

The YouTube Data API metadata methods do not download media, inspect images, hear audio, or obtain arbitrary public transcript text. Add approved visual analysis capability separately before drawing conclusions about any claimed event.

Reusable `skills/youtube-evidence/SKILL.md` and `GEM_INSTRUCTIONS.md` are included. Creating the files does not install a ChatGPT skill or Google Gem automatically.

Official references: https://developers.google.com/youtube/v3/docs/search/list ; https://developers.google.com/youtube/v3/docs/videos/list ; https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
