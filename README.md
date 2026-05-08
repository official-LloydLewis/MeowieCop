---

# 🐾 MeowieCop v1.9.0

<div align="center">

Lightweight moderation helper bot for **Bale** group chats
Built for practical moderation workflows, persistent storage, and automated admin utilities.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Version](https://img.shields.io/badge/Version-1.9.0-green)
![Platform](https://img.shields.io/badge/Platform-Bale-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

</div>

---

# 🌍 Languages / زبان‌ها

| Language     | Link                         |
| ------------ | ---------------------------- |
| 🇺🇸 English | [English Section](#-english) |
| 🇮🇷 فارسی   | [بخش فارسی](#-فارسی)         |

---

# 🇺🇸 English

## 📌 Overview

**MeowieCop** is a lightweight moderation assistant bot for **Bale** group chats.

It provides practical administration tools including:

* 🔨 Reply-based banning system
* 🔇 Mute / unmute moderation
* 💾 Persistent YAML storage
* 🚫 Automatic re-ban for blacklisted users
* 📜 Polling architecture with readable logs

Current implementation is located in:

```text
v1.9.0/MeowieHelper.py
```

---

# ✨ Features

| Feature               | Description                                           |
| --------------------- | ----------------------------------------------------- |
| 🔨 Ban / Unban        | Reply-based moderation commands for banning users     |
| 🔇 Mute / Unmute      | Silence users temporarily or permanently              |
| 💾 Persistent Storage | Saves moderation data using YAML files                |
| 🚫 Auto Re-ban        | Automatically bans blacklisted users when they rejoin |
| ⏰ Auto Unmute Checker | Background checker prepared for timed mutes           |
| 📜 Logging            | Clear startup and runtime console logs                |

---

# 📁 Project Structure

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

# ⚙️ Requirements

| Requirement           | Version  |
| --------------------- | -------- |
| 🐍 Python             | 3.9+     |
| 🤖 Bale Bot API Token | Required |
| 📦 requests           | Latest   |
| 📦 PyYAML             | Latest   |

Install dependencies:

```bash
pip install requests pyyaml
```

---

# 🔧 Configuration

The bot reads configuration from constants and environment variables inside `MeowieHelper.py`.

## 🔑 Required Environment Variable

```bash
export BOT_TOKEN="your_bale_bot_token"
```

> ⚠️ Never hardcode real tokens in production environments.

---

# 📂 Important Files

| File            | Purpose             |
| --------------- | ------------------- |
| `database.yml`  | Stores muted users  |
| `blacklist.yml` | Stores banned users |

Run the bot from inside the `v1.9.0` directory so relative paths resolve correctly.

---

# ▶️ Run the Bot

From repository root:

```bash
cd v1.9.0
python MeowieHelper.py
```

You should see startup logs and the **MeowieCop v1.9.0** banner in the console.

---

# 🛠️ Admin Commands

## 🔨 Ban Commands

| Persian | English |
| ------- | ------- |
| `بن`    | `ban`   |
| `سیک`   | `ban`   |

---

## 🔓 Unban Commands

| Persian | English |
| ------- | ------- |
| `انبن`  | `unban` |

---

## 🔇 Mute Commands

| Persian | English |
| ------- | ------- |
| `سکوت`  | `mute`  |

---

## 🔊 Unmute Commands

| Persian        | English  |
| -------------- | -------- |
| `بازکردن سکوت` | `unmute` |
| `رفع سکوت`     | `unmute` |

---

## ℹ️ Info Commands

| Persian  | English |
| -------- | ------- |
| `راهنما` | `info`  |
| `-info`  | `info`  |

> ⚠️ Most moderation actions are reply-based and require replying to a target user's message.

---

# 🚀 Production Notes

* 🔐 Keep `BOT_TOKEN` secret
* 🐳 Consider using Docker or a process manager
* 📜 Enable log rotation for long-running bots
* 💾 Back up YAML files regularly

---

# 📄 License

This project is distributed under the terms of the license in [`LICENSE`](./LICENSE).

---

# 🇮🇷 فارسی

## 📌 معرفی

**MeowieCop** یک ربات سبک مدیریت گروه برای پیام‌رسان **بله** است که برای مدیریت عملی گروه‌ها طراحی شده است.

امکانات اصلی:

* 🔨 سیستم بن و آنبن بر پایه ریپلای
* 🔇 میوت و آن‌میوت کاربران
* 💾 ذخیره‌سازی دائمی با YAML
* 🚫 بن خودکار کاربران بلک‌لیست‌شده
* 📜 لاگ‌گیری واضح و معماری Polling

فایل اصلی پروژه:

```text
v1.9.0/MeowieHelper.py
```

---

# ✨ امکانات

| قابلیت              | توضیح                                   |
| ------------------- | --------------------------------------- |
| 🔨 بن / آنبن        | مدیریت کاربران با دستورات ریپلای        |
| 🔇 سکوت / رفع سکوت  | میوت و آن‌میوت کاربران                  |
| 💾 ذخیره‌سازی دائمی | ذخیره اطلاعات در فایل‌های YAML          |
| 🚫 بن خودکار        | بن مجدد کاربران بلک‌لیست‌شده هنگام ورود |
| ⏰ بررسی خودکار سکوت | ساختار آماده برای میوت زمان‌دار         |
| 📜 لاگ‌گیری         | لاگ‌های واضح هنگام اجرا                 |

---

# 📁 ساختار پروژه

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

# ⚙️ پیش‌نیازها

| مورد             | نسخه       |
| ---------------- | ---------- |
| 🐍 پایتون        | 3.9+       |
| 🤖 توکن ربات بله | ضروری      |
| 📦 requests      | آخرین نسخه |
| 📦 PyYAML        | آخرین نسخه |

نصب وابستگی‌ها:

```bash
pip install requests pyyaml
```

---

# 🔧 تنظیمات

ربات تنظیمات را از متغیرهای محیطی و ثابت‌های داخل `MeowieHelper.py` می‌خواند.

## 🔑 متغیر ضروری

```bash
export BOT_TOKEN="your_bale_bot_token"
```

> ⚠️ توکن واقعی را داخل سورس قرار ندهید.

---

# ▶️ اجرای ربات

از ریشه پروژه:

```bash
cd v1.9.0
python MeowieHelper.py
```

پس از اجرا، لاگ‌های شروع و بنر **MeowieCop v1.9.0** نمایش داده می‌شود.

---

# 🛠️ دستورات مدیریتی

| عملیات      | دستورات                                |
| ----------- | -------------------------------------- |
| 🔨 بن       | `بن` / `سیک` / `ban`                   |
| 🔓 آنبن     | `انبن` / `unban`                       |
| 🔇 سکوت     | `سکوت` / `mute`                        |
| 🔊 رفع سکوت | `بازکردن سکوت` / `رفع سکوت` / `unmute` |
| ℹ️ راهنما   | `راهنما` / `info` / `-info`            |

> ⚠️ بیشتر دستورات مدیریتی به صورت ریپلای روی پیام کاربر استفاده می‌شوند.

---

# 🚀 نکات استفاده در محیط واقعی

* 🔐 توکن ربات را مخفی نگه دارید
* 🐳 استفاده از Docker یا Process Manager پیشنهاد می‌شود
* 📜 برای لاگ‌ها Log Rotation تنظیم کنید
* 💾 از فایل‌های YAML بکاپ بگیرید

---

# 📄 لایسنس

این پروژه تحت شرایط فایل [`LICENSE`](./LICENSE) منتشر شده است.
