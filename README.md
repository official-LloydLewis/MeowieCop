---

# 🐾 MeowieCop v2.0.0

<div align="center">

Lightweight moderation helper bot for **Bale** group chats  
Now upgraded with safer storage, better performance, timed moderation, and smarter command targeting.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Version](https://img.shields.io/badge/Version-2.0.0-green)
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

Compared to **v1.9.0**, the **v2.0.0 generation** (including `V2.1.0` and `V2.2.0`) introduces stronger reliability and moderation quality:

* 🔒 Atomic YAML write flow to reduce data corruption risk
* ⏱️ Timed mute support (`10min`, `2h`, `3d`, `1w`) + background expiry handling
* 🧠 Better target resolution (reply, mention entities, username lookup, prefix matching)
* 🧵 Thread-safe cache/database access with locks and background workers
* 🚦 API resilience improvements (retry/backoff, rate-limit handling, pooled HTTP session)
* 📚 Expanded command aliases in Persian and English

Current implementation is located in:

```text
v2.0.0/V2.2.0/MoewieCop.py
```

---

# ✨ Features

| Feature                       | Description                                                              |
| ----------------------------- | ------------------------------------------------------------------------ |
| 🔨 Ban / Unban                | Reply or mention-based moderation commands for banning users             |
| 🔇 Timed & Permanent Mute     | Mute users for specific durations or indefinitely                        |
| 💾 Unified Persistent Storage | Stores users, muted users, and blacklist in one YAML database            |
| 🚫 Auto Re-ban                | Automatically bans blacklisted users when they rejoin                    |
| 🧭 Smart User Resolution      | Resolves users via reply, mention entities, cached usernames, and prefix |
| 🔁 Resilient API Calls        | Handles transient failures, 429 rate limits, and server retries          |
| ⚙️ Background Workers         | Periodic mute expiration checks and deferred cache-to-database flushing  |
| 📜 Structured Logging         | Thread-aware logs for startup and runtime observability                  |

---

# 📁 Project Structure

```text
.
├── LICENSE
├── README.md
├── v1.9.0/
│   ├── MeowieHelper.py
│   ├── blacklist.yml
│   └── database.yml
└── v2.0.0/
    ├── V2.1.0/
    │   └── MoewieCop.py
    └── V2.2.0/
        └── MoewieCop.py
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

The bot reads configuration from constants and environment variables inside `MoewieCop.py`.

## 🔑 Required Environment Variable

```bash
export BOT_TOKEN="your_bale_bot_token"
```

> ⚠️ Never hardcode real tokens in production environments.

---

# 📂 Important Files

| File                         | Purpose                                                |
| ---------------------------- | ------------------------------------------------------ |
| `v2.0.0/V2.2.0/MoewieCop.py`| Current stable implementation                           |
| `database.yml`              | Unified runtime database (users, muted, blacklist data)|

Run the bot from inside the chosen version directory so relative paths resolve correctly.

---

# ▶️ Run the Bot

From repository root:

```bash
cd v2.0.0/V2.2.0
python MoewieCop.py
```

You should see startup logs and the **MeowieCop 2.x** banner in the console.

---

# 🛠️ Admin Commands

## 🔨 Ban Commands

| Persian       | English |
| ------------- | ------- |
| `بن`          | `ban`   |
| `سیک`         | `ban`   |
| `گمشو بیرون`  | `ban`   |
| `اخراج`       | `ban`   |

---

## 🔓 Unban Commands

| Persian | English |
| ------- | ------- |
| `انبن`  | `unban` |
| `آنبن`  | `unban` |

---

## 🔇 Mute Commands

| Persian | English |
| ------- | ------- |
| `سکوت`  | `mute`  |
| `میوت`  | `mute`  |
| `خفه`   | `mute`  |

Timed examples:

```text
mute @username 10min
سکوت @username 2h
```

---

## 🔊 Unmute Commands

| Persian        | English  |
| -------------- | -------- |
| `بازکردن سکوت` | `unmute` |
| `رفع سکوت`     | `unmute` |
| `آزاد`         | `unmute` |
| `ازاد`         | `unmute` |

---

## ℹ️ Info Commands

| Persian  | English |
| -------- | ------- |
| `راهنما` | `info`  |
| `-info`  | `info`  |

> ⚠️ Moderation actions support reply-based and mention-based targeting.

---

# 🚀 Production Notes

* 🔐 Keep `BOT_TOKEN` secret
* 🧠 Prefer `V2.2.0` for current production use
* 🗂️ Back up `database.yml` regularly
* 📈 Tune env-based limits (`RATE_LIMIT_PER_SEC`, `USER_CACHE_MAX_SIZE`, etc.) for large groups
* 🧪 Test timed mute flows in a staging group before rollout

---

# 📄 License

This project is distributed under the terms of the license in [`LICENSE`](./LICENSE).

---

# 🇮🇷 فارسی

## 📌 معرفی

**MeowieCop** یک ربات سبک مدیریت گروه برای پیام‌رسان **بله** است.

نسخه‌های **۲.۰.۰** (شامل `V2.1.0` و `V2.2.0`) نسبت به **۱.۹.۰** بهبودهای مهمی دارند:

* 🔒 ذخیره‌سازی اتمیک YAML برای کاهش ریسک خراب‌شدن دیتابیس
* ⏱️ میوت زمان‌دار (`10min`، `2h`، `3d`، `1w`) همراه با بررسی خودکار پایان میوت
* 🧠 پیدا کردن هوشمند کاربر هدف از طریق ریپلای، منشن و کش کاربران
* 🧵 امنیت همزمانی بهتر با Lock و Workerهای پس‌زمینه
* 🚦 ارتباط پایدارتر با API (Retry/Backoff/Rate-limit handling)
* 📚 دستورات بیشتر به فارسی و انگلیسی

فایل اصلی نسخه فعلی:

```text
v2.0.0/V2.2.0/MoewieCop.py
```

---

# ✨ امکانات

| قابلیت                   | توضیح                                                         |
| ------------------------ | ------------------------------------------------------------- |
| 🔨 بن / آنبن             | مدیریت کاربران با ریپلای یا منشن                              |
| 🔇 سکوت زمان‌دار و دائم   | میوت برای زمان مشخص یا نامحدود                                |
| 💾 ذخیره‌سازی یکپارچه     | نگهداری users / muted / blacklist در یک دیتابیس YAML          |
| 🚫 بن خودکار             | بن مجدد کاربران بلک‌لیست‌شده هنگام ورود مجدد                  |
| 🧭 تشخیص هوشمند کاربر هدف | تشخیص با ریپلای، منشن، کش و Prefix Match                      |
| 🔁 API مقاوم             | مدیریت خطاهای موقت، 429 و Retry سمت سرور                      |
| ⚙️ Worker پس‌زمینه       | بررسی پایان میوت و Flush دوره‌ای کش کاربران به دیتابیس        |
| 📜 لاگ‌گیری ساختاریافته  | لاگ‌های دقیق با نمایش Thread برای عیب‌یابی بهتر               |

---

# 📁 ساختار پروژه

```text
.
├── LICENSE
├── README.md
├── v1.9.0/
│   ├── MeowieHelper.py
│   ├── blacklist.yml
│   └── database.yml
└── v2.0.0/
    ├── V2.1.0/
    │   └── MoewieCop.py
    └── V2.2.0/
        └── MoewieCop.py
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

ربات تنظیمات را از ثابت‌ها و متغیرهای محیطی داخل `MoewieCop.py` می‌خواند.

## 🔑 متغیر ضروری

```bash
export BOT_TOKEN="your_bale_bot_token"
```

> ⚠️ توکن واقعی را داخل سورس قرار ندهید.

---

# ▶️ اجرای ربات

از ریشه پروژه:

```bash
cd v2.0.0/V2.2.0
python MoewieCop.py
```

بعد از اجرا، لاگ‌های شروع و بنر **MeowieCop 2.x** نمایش داده می‌شود.

---

# 🛠️ دستورات مدیریتی

| عملیات      | دستورات                                                       |
| ----------- | ------------------------------------------------------------- |
| 🔨 بن       | `بن` / `سیک` / `گمشو بیرون` / `اخراج` / `ban`                |
| 🔓 آنبن     | `انبن` / `آنبن` / `unban`                                     |
| 🔇 سکوت     | `سکوت` / `میوت` / `خفه` / `mute` (+ زمان مثل `10min`, `2h`) |
| 🔊 رفع سکوت | `بازکردن سکوت` / `رفع سکوت` / `آزاد` / `ازاد` / `unmute`    |
| ℹ️ راهنما   | `راهنما` / `info` / `-info`                                  |

> ⚠️ دستورات مدیریتی هم به صورت ریپلای و هم منشن پشتیبانی می‌شوند.

---

# 🚀 نکات استفاده در محیط واقعی

* 🔐 توکن ربات را مخفی نگه دارید
* 🧠 برای استفاده عملی، نسخه `V2.2.0` پیشنهاد می‌شود
* 💾 از `database.yml` بکاپ منظم بگیرید
* 📈 برای گروه‌های بزرگ، مقادیر محدودیت کش و Rate Limit را تنظیم کنید
* 🧪 قبل از اجرا در گروه اصلی، میوت زمان‌دار را در گروه تست بررسی کنید

---

# 📄 لایسنس

این پروژه تحت شرایط فایل [`LICENSE`](./LICENSE) منتشر شده است.
