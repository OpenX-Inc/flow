# Publishing & Distribution Research

## Supported Platforms

### TikTok — Content Posting API

- **Official API**: TikTok Content Posting API (REST, OAuth 2.0)
- **Upload limit**: 25 videos/account/day
- **File size**: Up to 1 GB (MP4)
- **Requirements**: App review + OAuth authorization from account owner
- **Features**: Upload, caption, schedule, privacy settings
- **Docs**: [TikTok for Developers](https://developers.tiktok.com)

### YouTube Shorts — YouTube Data API v3

- **Official API**: YouTube Data API v3 (`videos.insert`)
- **Upload limit**: ~100 videos/day (quota-based)
- **Shorts detection**: Automatic if video is ≤60s and vertical (9:16)
- **Requirements**: Google Cloud project + OAuth
- **Features**: Upload, title, description, tags, thumbnail, schedule
- **Quota cost**: 1600 units per upload (daily quota: 10,000 units = ~6 uploads default, can request increase)

### Instagram Reels — Instagram Graph API

- **Official API**: Instagram Content Publishing API
- **Requirements**: Facebook Business account + App review
- **Upload flow**: Two-step (create container → publish)
- **Limits**: 50 API-published posts per 24 hours
- **Features**: Upload, caption, location, cover image

### Cross-Platform Tool: Upload-Post

- Third-party service that handles TikTok + Instagram posting
- Already integrated into MoneyPrinterTurbo (our forked repo)
- API-based, handles OAuth complexity
- Docs: [upload-post.com](https://upload-post.com)

## Posting Strategy

For an autonomous system generating 1-3 videos per day:

| Platform | Videos/Day | Best Times | Format |
|----------|-----------|------------|--------|
| TikTok | 1-3 | 7-9am, 12-3pm, 7-11pm | 9:16, ≤60s, MP4 |
| YouTube Shorts | 1-2 | 2-4pm, 7-9pm | 9:16, ≤60s, MP4 |
| Instagram Reels | 1-2 | 11am-1pm, 7-9pm | 9:16, ≤90s, MP4 |

## Technical Requirements

- OAuth tokens stored securely (refreshed automatically)
- Retry logic for rate limits and transient failures
- Metadata generation (title, description, hashtags) via LLM
- Thumbnail extraction (first frame or best frame detection)
- Scheduling to optimize posting times per platform

## References

- [TikTok Content Posting API Guide](https://tokportal.com/learn/tiktok-content-posting-api-developer-guide)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Upload-Post Docs](https://docs.upload-post.com)
- [Auto-Post YouTube Shorts](https://www.upload-post.com/how-to/auto-post-youtube-shorts/)
