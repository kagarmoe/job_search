# Daily Job Search Scheduler

This repository includes a launchd configuration for automatically running the job search pipeline daily.

## Setup

### 1. Install the launchd job

```bash
# Copy the plist to LaunchAgents directory
cp com.kimberlygarmoe.job_search.plist ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist

# Verify it's loaded
launchctl list | grep job_search
```

### 2. Configuration

The scheduler is configured to:
- Run daily at 8:00 AM
- Execute `run_pipeline.py --rss-only` (RSS feeds only, no API key needed)
- Log output to `logs/pipeline.log` and `logs/pipeline.error.log`
- Use the virtual environment at `.venv/`

### 3. Customization

Edit `com.kimberlygarmoe.job_search.plist` before installing to customize:

**Change schedule:**
```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>8</integer>  <!-- Change hour (0-23) -->
    <key>Minute</key>
    <integer>0</integer>  <!-- Change minute (0-59) -->
</dict>
```

**Enable web search (requires OPENAI_API_KEY):**
```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/kimberlygarmoe/repos/job_search/.venv/bin/python3</string>
    <string>/Users/kimberlygarmoe/repos/job_search/run_pipeline.py</string>
    <!-- Remove --rss-only to run both RSS and web search -->
</array>

<!-- Add API key to environment -->
<key>EnvironmentVariables</key>
<dict>
    <key>OPENAI_API_KEY</key>
    <string>your-api-key-here</string>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
</dict>
```

**Run multiple times per day:**
```xml
<!-- Replace StartCalendarInterval with array for multiple times -->
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <dict>
        <key>Hour</key>
        <integer>17</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</array>
```

## Management

### Check status
```bash
launchctl list | grep job_search
```

### View logs
```bash
# Standard output
tail -f logs/pipeline.log

# Errors
tail -f logs/pipeline.error.log
```

### Manually trigger
```bash
launchctl start com.kimberlygarmoe.job_search
```

### Disable (stop automatic runs)
```bash
launchctl unload ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
```

### Re-enable
```bash
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
```

### Update configuration
```bash
# Unload old version
launchctl unload ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist

# Copy updated file
cp com.kimberlygarmoe.job_search.plist ~/Library/LaunchAgents/

# Load new version
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
```

## Troubleshooting

### Job not running
1. Check if loaded: `launchctl list | grep job_search`
2. Check logs: `tail logs/pipeline.error.log`
3. Verify paths in plist are absolute and correct
4. Ensure Python virtual environment exists: `ls .venv/bin/python3`

### Permission issues
Ensure the plist file has correct permissions:
```bash
chmod 644 ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
```

### Mac was asleep during scheduled time
By default, `RunAtLoad` is `false`, so missed runs won't execute on wake. To run immediately when the Mac wakes:
```xml
<key>RunAtLoad</key>
<true/>
```

### Test manually first
Before scheduling, test the pipeline manually:
```bash
source .venv/bin/activate
python run_pipeline.py --rss-only
```

## Logs Retention

Logs accumulate over time. To rotate logs:

```bash
# Archive old logs
mv logs/pipeline.log logs/pipeline.log.$(date +%Y%m%d)
mv logs/pipeline.error.log logs/pipeline.error.log.$(date +%Y%m%d)

# Or clear logs
> logs/pipeline.log
> logs/pipeline.error.log
```

Consider adding a cron job or launchd task to rotate logs monthly.
