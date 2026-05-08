# MeowieCop v1.9.0

A lightweight moderation helper bot for **Bale** group chats, focused on practical admin workflows:

- Reply-based **ban / unban**
- Reply-based **mute / unmute**
- Persistent YAML storage for moderation state
- Automatic re-ban of previously blacklisted users when they rejoin
- Polling-based architecture with clear logging

This repository currently contains the `v1.9.0` release implementation in `v1.9.0/MeowieHelper.py`.

---

## Features

### 1) Ban and Unban
Admins can reply to a user's message and issue a ban/unban command.

- On ban, the user is added to `blacklist.yml`
- On unban, the user is removed from `blacklist.yml`

### 2) Mute and Unmute
Admins can mute/unmute users by replying to messages.

- Muted users are tracked in memory and in `database.yml`
- Muted users' messages are automatically deleted while mute is active

### 3) Persistent State
Bot state is stored in YAML files and restored on startup:

- `database.yml` for muted users
- `blacklist.yml` for blacklisted users

The bot also auto-creates these files with safe defaults if they do not exist.

### 4) Auto Re-ban on Join
If a user in the blacklist rejoins a chat, the bot automatically bans them again and removes the join event message.

### 5) Auto Unmute Checker
A periodic mute expiration checker is included. Current mute entries are indefinite by default (far-future timestamp), while timed mute support is structurally prepared.

---

## Project Structure

```text
.
├── LICENSE
├── README.md
└── v1.9.0/
    ├── MeowieHelper.py
    ├── blacklist.yml
    └── database.yml
```

---

## Requirements

- Python 3.9+
- Bale Bot API token
- Python packages:
  - `requests`
  - `PyYAML`

Install dependencies:

```bash
pip install requests pyyaml
```

---

## Configuration

The bot reads configuration from constants and environment variables in `MeowieHelper.py`.

### Required environment variable

```bash
export BOT_TOKEN="your_bale_bot_token"
```

> If `BOT_TOKEN` is not set, the code falls back to `ENTER THE TOKEN HERE`. You should always provide a real token via environment variables before running in production.

### Important paths

By default the bot uses:

- `database.yml`
- `blacklist.yml`

Run the bot from the `v1.9.0` directory so relative paths resolve correctly.

---

## Run

From repository root:

```bash
cd v1.9.0
python MeowieHelper.py
```

You should see startup logs and the v1.9.0 banner in the console.

---

## Admin Commands

The bot supports Persian and English trigger words:

- Ban: `بن` / `سیک` / `ban`
- Unban: `انبن` / `unban`
- Mute: `سکوت` / `mute`
- Unmute: `بازکردن سکوت` / `رفع سکوت` / `unmute`
- Info: `info` / `راهنما` / `-info`

> Most moderation actions are reply-based and require replying to a target user's message.

---

## Notes for Production Use

- Keep `BOT_TOKEN` secret; never commit real secrets.
- Consider running the bot behind a process manager (e.g., systemd, supervisor, docker).
- Add log rotation for long-running deployments.
- Back up YAML files periodically if moderation history is important.

---

## License

This project is distributed under the terms of the license in [`LICENSE`](./LICENSE).
