# PMOVES.YT Resilient Downloader Design

This document outlines the design for a more resilient and efficient download module for the PMOVES.YT service. The proposed changes address key gaps in the current implementation related to concurrency, retries, and download resuming.

## 1. Current State Analysis

The existing `yt.py` service has the following characteristics:

-   **Synchronous Playlist Processing**: The `/yt/playlist` endpoint processes videos in a sequential loop, which is inefficient for large playlists.
-   **Minimal Retry Logic**: Error handling is basic, with no automatic retries for transient failures like network errors.
-   **No Download Resuming**: Downloads are made to a temporary directory that is deleted after each attempt, meaning any progress on a failed download is lost.
-   **Basic Rate Limiting**: A simple static delay (`YT_RATE_LIMIT`) is used between downloads.

## 2. Proposed Architecture

To address these limitations, we will refactor the download and playlist logic to introduce true parallelism and robust error handling.

### 2.1. Asynchronous Worker Pool

The `/yt/playlist` endpoint will be refactored to be fully asynchronous.

-   **`asyncio.Semaphore`**: We will use a semaphore to control concurrency, bounded by the existing `YT_CONCURRENCY` environment variable. This will limit the number of videos being downloaded simultaneously.
-   **`asyncio.gather`**: The main loop will create a list of tasks (one for each video) and run them concurrently using `asyncio.gather`.
-   **Async Ingestion Function**: A new `async def _ingest_one_async(...)` function will be created to wrap the download and transcription logic. This function will be called for each video in the playlist.

```python
# Example snippet for yt.py

async def _ingest_one_async(video_url: str, ns: str, bucket: str, job_id: str, video_id: str):
    # ... implementation with retry logic ...

@app.post('/yt/playlist')
async def yt_playlist(body: Dict[str,Any] = Body(...)):
    # ... (extract entries and create job)

    semaphore = asyncio.Semaphore(YT_CONCURRENCY)
    tasks = []

    async def worker(entry):
        async with semaphore:
            vid_url = f"https://www.youtube.com/watch?v={entry['id']}" if len(entry['id']) == 11 else entry['id']
            if job_id: _item_upsert(job_id, entry['id'], 'running', None, {'title': entry.get('title')})
            
            # Add a small delay before starting the next download
            if YT_RATE_LIMIT > 0:
                await asyncio.sleep(YT_RATE_LIMIT)

            result = await _ingest_one_async(vid_url, ns, bucket, job_id, entry['id'])
            # ... (update job status)
            return result

    for entry in entries:
        tasks.append(worker(entry))

    results = await asyncio.gather(*tasks)
    
    if job_id: _job_update(job_id, 'completed')
    return {'ok': True, 'job_id': job_id, 'count': len(results), 'results': results}
```

### 2.2. Retry Logic with Tenacity

We will use the `tenacity` library to add robust retry capabilities to the download process.

-   **`@tenacity.retry` Decorator**: The `_ingest_one_async` function will be decorated to automatically retry on failure.
-   **Exponential Backoff**: The retry strategy will use exponential backoff to avoid overwhelming the server.
-   **Selective Retries**: The decorator will be configured to only retry on specific, transient exceptions (e.g., `requests.RequestException`, `yt_dlp.utils.DownloadError` for network issues, HTTP 5xx errors). It will not retry on permanent errors like HTTP 404 (Not Found).
-   **State Updates**: The retry handler will update the `yt_items` table to set the status to `retrying`, log the error, and increment the `retries` count.

```python
# Example snippet for yt.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Define which exceptions should trigger a retry
def is_transient_error(exception):
    if isinstance(exception, HTTPException):
        return 500 <= exception.status_code < 600
    return isinstance(exception, (requests.RequestException, yt_dlp.utils.DownloadError))

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=4, max=30),
       retry=retry_if_exception_type((requests.RequestException, yt_dlp.utils.DownloadError, HTTPException)),
       before_sleep=before_sleep_log)
async def _ingest_one_async(video_url: str, ns: str, bucket: str, job_id: str, video_id: str):
    # ... core download and transcript logic ...

def before_sleep_log(retry_state):
    # Log retry attempts to Supabase
    # ... update yt_items with status='retrying' and increment retries count ...
    print(f"Retrying download for {retry_state.args[0]}... Attempt {retry_state.attempt_number}")

```

### 2.3. Download Resuming

To avoid losing progress on large downloads, we will configure `yt-dlp` to support resuming.

-   **Persistent Download Path**: Downloads will be saved to a persistent directory, such as `./temp_downloads/yt/<video_id>/`. This path will not be deleted automatically after each attempt.
-   **`yt-dlp` Options**: We will add the following options to the `ydl_opts` dictionary:
    -   `'download_archive': '<path_to_archive_file>'` or use `'--no-overwrites'` and `'--continue'` flags if more appropriate for the library's usage.
    -   `yt-dlp` inherently supports resuming if the output file already exists. By not deleting the temp directory, subsequent attempts will automatically resume.
-   **Cleanup**: A separate cleanup mechanism will be required to remove the temporary files once the video has been successfully processed and uploaded to S3.

### 2.4. Enhanced State Management

The `yt_items` table in Supabase will be used to provide more granular feedback on the download process.

-   **New Statuses**: We will introduce new statuses like `downloading`, `retrying`, `transcribing`.
-   **Error Logging**: The specific error message that caused a failure or a retry will be logged to the `yt_items.error` column.
-   **Retry Count**: The `yt_items.retries` column will be incremented on each retry attempt.

## 3. Implementation Steps

1.  Add `tenacity` to the project dependencies.
2.  Refactor the `/yt/playlist` endpoint in `yt.py` to be `async` and use the `asyncio.Semaphore` and `asyncio.gather` pattern.
3.  Create a new `_ingest_one_async` function and apply the `@tenacity.retry` decorator with the appropriate configuration.
4.  Modify the `yt_download` function (or its new async equivalent) to use a persistent temporary directory for downloads.
5.  Update the Supabase helper functions (`_item_upsert`) to support the new statuses and to log error messages and retry counts.
6.  Add a cleanup mechanism for the persistent download directory.
