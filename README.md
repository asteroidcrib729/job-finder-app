# 🚀 Automated Job Finder & Instant Phone Alert Pipeline

An automated, open-source Python application designed to continuously discover fresh software engineering roles across **LinkedIn**, **Indeed**, **Glassdoor**, **Google Jobs**, **Bayt**, and **Rozee.pk**, deduplicate postings, and push instant notifications directly to your mobile phone via **Discord** (and/or **Telegram**) powered by **GitHub Actions**.

Targeted specifically for **Fresh Engineering Graduates, Junior, Entry-Level, and Associate Software Engineers** looking for **Remote** opportunities or positions in **Karachi, Pakistan**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                  │
│                     (Runs every 3 hours)                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Scraping Layer                          │
│ ├── python-jobspy (LinkedIn, Indeed, Glassdoor, Google, Bayt)│
│ └── Custom BS4 Scraper (Rozee.pk Karachi & Remote)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Filtering Engine                        │
│ Filters for Fresh Grad / Associate / Junior tech titles &   │
│ excludes Senior / Lead / Manager positions                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  Deduplication & State                      │
│ Checks data/seen_jobs.json & commits state to repo         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Instant Phone Push Alerts                 │
│ ├── Discord Webhook Embed Cards (Mobile App Notification)   │
│ └── Telegram Bot API (Optional Secondary Push Channel)      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Step-by-Step Setup Guide

### Step 1: Set Up Discord Webhook (Push Notifications to Phone)
1. Open Discord on your PC or phone and create or select a personal server.
2. Go to **Server Settings** -> **Integrations** -> **Webhooks** -> Click **New Webhook**.
3. Name your bot (e.g., `Job Finder Alert Bot`) and select the channel where you want notifications.
4. Click **Copy Webhook URL**.

> 💡 *Download the Discord app on your phone and enable push notifications for this channel so every new job post triggers an instant mobile notification!*

---

### Step 2: (Optional) Set Up Telegram Bot
If you also want Telegram notifications:
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, follow the prompts, and copy the `HTTP API Token`.
3. Open Telegram and search for `@userinfobot` to get your personal `Chat ID`.

---

### Step 3: Push Repository to GitHub
1. Create a **Private** repository on GitHub.
2. Initialize and push this codebase to your repository:
   ```bash
   git init
   git add .
   git commit -m "feat: initial job finder app setup"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/job-finder.html.git
   git push -u origin main
   ```

---

### Step 4: Add GitHub Repository Secrets
1. In your GitHub Repository, go to **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret** and add the following:
   - `DISCORD_WEBHOOK_URL`: Your copied Discord Webhook URL.
   - `TELEGRAM_BOT_TOKEN`: (Optional) Your Telegram bot token.
   - `TELEGRAM_CHAT_ID`: (Optional) Your Telegram chat ID.

---

### Step 5: Enable GitHub Actions Workflow Permissions
1. Open your repository's Actions settings directly: **[https://github.com/asteroidcrib729/job-finder-app/settings/actions](https://github.com/asteroidcrib729/job-finder-app/settings/actions)**
   *(Or navigate to **Settings** tab -> expand **Actions** in the left sidebar -> click **General**)*.
2. Scroll down to the **Workflow permissions** section.
3. Select **Read and write permissions**.
4. Click **Save**.

That's it! GitHub Actions will now run automatically **every 3 hours**, search for new fresh-graduate software engineer jobs in Karachi & Remote, and push alerts straight to your phone.

---

## 🧪 Local Testing Commands

You can run and test the script locally before or alongside GitHub Actions:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test Notification Setup
Verify your Discord Webhook or Telegram credentials by sending a test card:
```bash
# On Windows PowerShell
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python main.py --test-notify
```

### 3. Run Dry-Run (Scrape & Filter Without Sending Alerts)
```bash
python main.py --dry-run
```

### 4. Run Full Pipeline Locally
```bash
python main.py
```

---

## ⚙️ Customizing Keywords & Filters

All search parameters are configured in [`config.yaml`](file:///c:/Users/DESKTOP-Q2TMP8U/Downloads/Source%20Codes/Job%20Finder/config.yaml):
- Edit `search_keywords` to add or remove job titles.
- Edit `locations` to add other cities or countries.
- Edit `filtering.title_exclude_keywords` to tune out unwanted job titles.
