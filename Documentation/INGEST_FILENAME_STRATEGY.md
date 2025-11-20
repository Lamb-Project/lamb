## Smart Filename Generation Strategy for YouTube Video Ingestion (#107)

### Objective
When ingesting YouTube videos using the `youtube_transcript_ingest` plugin, the system generates a `file_name` that is as descriptive and human-friendly as possible, instead of just using a generic placeholder or video ID.

### Applied Logic

#### 1. **YouTube Video Ingestion**
- **Attempts to get the real video title** using the `yt-dlp` library.
- If not available or fails, **performs web scraping** of the title using `httpx` and `BeautifulSoup`.
- If that also fails, **uses the video ID** as a fallback (`yt:video_id.txt`).
- The title is normalized with a `slugify` function to ensure filesystem safety.
- **Example:**
  - Real title: `How to Program in Python (2025)`  `yt:how_to_program_in_python_2025.txt`
  - Fallback: `yt:dQw4w9WgXcQ.txt`

#### 2. **`slugify` Function**
- Converts text to lowercase.
- Removes special characters.
- Replaces spaces and dashes with underscores.
- Limits the length to 80 characters.

#### 3. **Dependency Handling**
- If any dependency (`yt-dlp`, `httpx`, `beautifulsoup4`) is not available, the system uses the basic fallback.
- Logs are added for debugging and traceability.

---

### Flow Summary
1. The user requests ingestion of a YouTube video.
2. The backend tries to obtain the real title of the video.
3. If successful, it uses it as the normalized filename with `yt:` prefix.
4. If not, it uses the video ID as a unique and safe identifier.
5. The generated name appears as `file_name` in the knowledge base.

---

**Advantages:**
- Files in the knowledge base are much easier to identify and search for.
- Avoids generic or uninformative names.
- The system is robust against network or dependency failures.
- The `yt:` prefix clearly identifies YouTube video content.
