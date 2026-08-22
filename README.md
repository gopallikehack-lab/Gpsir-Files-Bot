# GpsirEra File Vault Bot — Vercel Edition

Webhook-based Telegram file-sharing bot. No polling, no local disk state —
everything persists in Upstash Redis so it survives Vercel's serverless
cold starts.

## 1. Push this repo to GitHub

```
git init
git add .
git commit -m "file vault bot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## 2. Create an Upstash Redis database

- Go to https://console.upstash.com → Create Database
- Copy the **REST URL** and **REST TOKEN** shown on the database page

## 3. Deploy to Vercel

- Import the GitHub repo at https://vercel.com/new
- Under **Environment Variables**, add:

| Key | Value |
|---|---|
| `BOT_TOKEN` | your bot token from @BotFather |
| `DEVELOPER` | `@GpsirEra` |
| `PREMIUM_USERS` | comma-separated numeric Telegram user IDs, e.g. `8932695749,123456789` |
| `UPSTASH_REDIS_REST_URL` | from step 2 |
| `UPSTASH_REDIS_REST_TOKEN` | from step 2 |

- Deploy.

## 4. Point Telegram's webhook at your deployment

Replace `<TOKEN>` and `<your-app>` and run once (from any machine, e.g. Termux):

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-app>.vercel.app/api/index"
```

You should get `{"ok":true,"result":true,...}` back.

## 5. Test it

Message your bot `/start` on Telegram. Forward it a file — you'll get a
shareable link back. Premium users (IDs listed in `PREMIUM_USERS`) get the
VIP UI with your custom Telegram Premium emoji and the `/batch` picker.

## Notes

- **Get real `custom_emoji_id` values**: send the emoji in Saved Messages
  on Telegram Web, forward that message to `@RawDataBot`, and copy the
  `custom_emoji_id` field from the JSON reply. The 5 IDs already in
  `api/index.py` (`PREMIUM_EMOJIS` dict) are the ones you gave me.
- If you rotate your bot token, re-run the `setWebhook` command with the
  new token.
- To switch back to polling locally for testing, you'd need a separate
  script — this repo is built specifically for webhook + Vercel.
