# YouTube API Compliance Audit - Cheat Sheet

Use these answers to fill out the YouTube API audit form. Copy-paste ready!

---

## SECTION 1: Basic Information

### Describe your organization's work as it relates to YouTube *
```
I develop a desktop application that automates the creation and upload of educational quiz videos to YouTube. The application generates trivia and general knowledge quiz content using text-to-speech, animated graphics, and uploads them to my personal YouTube channel to share educational content with viewers.
```

### Google representative email address
```
(Leave blank unless you have a Google contact)
```

### Content Owner ID (if available)
```
(Leave blank - this is for YouTube Partner Program MCNs only)
```

---

## SECTION 2: API Client Information

### Have you undergone an audit since June 2019? *
- [ ] Yes
- [x] **No** (select this if first time)

### Is there any way in which your client's use of the YT API changed since the last audit? *
- [ ] Yes
- [x] **No** (if first audit, select No)

### Please list all your API Client(s) *
```
SharvaYoutubePro
```

### Please list all the project numbers used for each of your API Client(s) *
```
(Find this in Google Cloud Console → Your Project → Project Number)
Example: 123456789012
```

### If there is a log-in required to access the API client, please provide a demo account and instructions on how to access the API Client
```
The application is a local desktop tool that runs on my personal computer. It uses OAuth 2.0 to authenticate with my own YouTube channel. No external login is required - the app only uploads to my personal channel after I authorize it through Google's standard OAuth flow.
```

### Choose the option that best resembles your API Client's use case *
- [ ] YouTube analytics
- [ ] Social listening
- [x] **YouTube video uploads** ← SELECT THIS
- [ ] Video streaming site/app
- [ ] Live streaming tools
- [ ] Research
- [ ] Creator Tools
- [ ] Other

---

## SECTION 3: Documentation Upload

### Send documents relating to your implementation, access, integration and use of YouTube API Services *

**What to upload (create a simple PDF or document with):**
- Screenshot of the app interface
- Brief description of the upload flow
- Example of generated video content

**Note:** File must be smaller than 10MB, single file only.

---

## SECTION 4: Quota Request Form
*(Only fill if requesting more quota)*

### Which API Client are you requesting a quota increase for? *
```
SharvaYoutubePro
```

### What API project number are you requesting increased quota for? *
```
(Your Google Cloud Project Number - find in Cloud Console)
```

### Which YouTube API Service(s) are you requesting a quota increase for? *
- [x] **Data API** ← SELECT THIS

### How much "Additional Quota" are you requesting? *
```
40000
```
*(Formula: Total Needed - Current Allocated = Additional Quota)*
*(You have 10,000 default, requesting 50,000 total = 40,000 additional)*

### Justification for requesting additional quota? *
```
Expected growth and timelines:
- Currently uploading ~100 educational quiz videos per day
- Planning to scale to 300-500 videos per day within 3 months
- Each video uses approximately 1600 quota units (upload cost)

Arithmetic calculations:
- Current quota: 10,000 units/day
- Target uploads: 300 videos/day × 1600 units = 480,000 units needed
- Requesting: 50,000 units as initial scale-up

Daily usage pattern:
- Uploads distributed evenly throughout 24 hours
- Peak QPS: ~0.5 requests per second (very low)
- Expected daily calls: ~1,000 API calls total

Content type:
- Original educational quiz/trivia videos
- Text-to-speech narration
- Programmatically generated graphics
- 100% original content, no copyrighted material
```

### Explain in detail how you use YouTube API Services today *
```
My application uses the YouTube Data API v3 for the following operations:

1. VIDEO UPLOADS (videos.insert):
   - Upload educational quiz videos to my channel
   - Set video metadata (title, description, tags)
   - Set privacy status to public
   - Approximately 100 uploads per day currently

2. OAUTH 2.0 AUTHENTICATION:
   - Standard OAuth flow to authorize my personal account
   - Refresh tokens stored securely locally
   - Only accesses my own channel

3. API CALLS BREAKDOWN:
   - videos.insert: ~100 calls/day (1600 units each)
   - No other API endpoints used currently

The application runs on my local machine and only uploads content I create to my own YouTube channel.
```

### What functionality would your API client be lacking without more quota? *
```
Without additional quota, my application cannot:

1. Scale content production beyond ~6 videos per day
2. Meet viewer demand for more educational content
3. Maintain consistent daily upload schedule
4. Grow the channel's educational content library

The 10,000 unit daily limit severely restricts the number of videos I can publish, limiting the channel's growth and ability to serve educational content to viewers.
```

### What potential workarounds would you use to compensate for less quota? *
```
If quota increase is not approved, I would:

1. Reduce upload frequency to 5-6 videos per day maximum
2. Batch uploads during off-peak hours only
3. Create longer videos with more questions instead of multiple shorter videos
4. Implement strict quota monitoring to avoid hitting limits
5. Queue videos and spread uploads across multiple days

However, these workarounds significantly limit the channel's ability to provide fresh educational content daily.
```

---

## SECTION 5: Agreements (Check all boxes)

- [x] I have read and agree to the YouTube API Services Terms of Service (including the Developer Policies and Google Privacy Policy)

- [x] If I provide a demo account and instructions on how Google can access my API Client, I understand and agree that Google is not bound to any terms of service or policies that applies to such account or access to my API Client.

- [x] The above facts are true to the best of my knowledge and I understand that should the above facts be found to be untrue, YouTube may terminate my API Client's access to the YouTube API Services as per YouTube's Terms of Service and Developer Policies.

---

## Quick Reference - Key Points to Remember

| Question | Your Answer |
|----------|-------------|
| Use case | YouTube video uploads |
| API used | Data API v3 |
| Main operation | videos.insert |
| Current quota | 10,000 units/day |
| Requesting | 40,000 additional (50,000 total) |
| Content type | Educational quiz videos |
| Upload method | OAuth 2.0 authenticated |

---

## Where to Find Your Project Number

1. Go to https://console.cloud.google.com/
2. Select your project
3. Click on the project name dropdown
4. Project number is shown (it's a number like 123456789012)

---

## Tips for Approval

1. Be honest about your use case
2. Emphasize educational/original content
3. Show you understand quota costs
4. Provide realistic growth projections
5. Include screenshots if possible
6. Respond promptly to any follow-up questions

Good luck with the audit!
