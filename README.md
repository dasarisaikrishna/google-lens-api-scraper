# 🔍 Google Lens Exact Match API

> Accepts an image URL → performs Google Lens search → returns the full **Exact Match** page HTML.

---

## 📌 What It Does

This API automates the full Google Lens flow a user would perform manually:

1. Go to Google Lens with the image URL
2. Wait for redirect to the search results page
3. Click the **"Exact matches"** tab
4. Validate the response (no CAPTCHA, correct page, real results)
5. Return the full HTML

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/google-lens-api-scraper.git
cd google-lens-api-scraper

python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Mac/Linux

pip install -r requirements.txt
```

### 2. Set Up Environment

```bash
cp .env.example .env
```

Fill in your proxy credentials in `.env`:

```env
WEBSHARE_PROXY=http://username:password@proxy.mrscraper.com:10000
PROXY=http://username:password@p.webshare.io:80
MAX_CONCURRENCY=10
```

> ⚠️ Get free proxies from [MrScraper](https://mrscraper.com) or [Webshare](https://webshare.io).

### 3. Run the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

### 4. Expose Publicly (for remote testing)

```bash
ngrok http 8000
```

---

## 📡 API Reference

### `GET /google-lens/browser`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `imageUrl` | string | ✅ | Any publicly accessible image URL |

**Example:**

```bash
curl "http://localhost:8000/google-lens/browser?imageUrl=https://m.media-amazon.com/images/I/61CGHv6kmWL._AC_SL1500_.jpg"
```

**Response:** Raw HTML of the Google Lens Exact Match page

| Status | Meaning |
|---|---|
| `200` | Success — full Exact Match HTML returned |
| `400` | Missing or empty `imageUrl` |
| `502` | Scraping failed after all retries |
| `500` | Unexpected server error |

---

### `GET /health`

```json
{
  "status": "ok",
  "max_concurrency": 10,
  "stats": {
    "total_requests": 10,
    "successful": 10,
    "failed": 0,
    "avg_response_time_seconds": 35.1,
    "success_rate": "100.0%"
  }
}
```

### `GET /stats`

Detailed performance stats — total requests, success rate, avg latency.

---

## 🛡️ Anti-Bot Strategies

| Strategy | Details |
|---|---|
| **Stealth browser** | Real Chrome via `zendriver` — not a headless HTTP client |
| **Residential proxy** | All traffic routed through MrScraper/Webshare proxy |
| **Silent proxy auth** | Chrome extension handles proxy login — no popup ever appears |
| **Session preservation** | Clicks the Exact matches tab instead of URL navigation to keep `vsrid` alive |
| **Retry logic** | Up to 4 automatic retries on CAPTCHA or bad response |
| **HTML validation** | Checks `udm=48`, result count, and CAPTCHA before returning |

---

## ⚙️ Tech Stack

| | |
|---|---|
| Language | Python 3.10+ |
| Framework | FastAPI |
| Browser automation | zendriver (Chrome CDP) |
| Server | uvicorn |
| Proxy | MrScraper / Webshare residential |

---

## 📁 Project Structure

```
google-lens-api-scraper/
├── main.py                  # FastAPI server & endpoints
├── scraper.py               # Core browser scraping logic
├── proxy_auth_extension.py  # Auto-generates Chrome proxy auth extension
├── .env.example             # Env variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📊 Performance

| Metric | Result |
|---|---|
| Avg latency | ~35 seconds |
| Max concurrency | 10 simultaneous requests |
| Success rate | >97% |
| Exact match results per image | 300–400 URLs |

---

## 🌐 Hosted API

| | |
|---|---|
| Endpoint | `http://{ngrok-url}/google-lens/browser?imageUrl={image_url}` |
| Max Concurrency | 10 |
| Avg Latency | ~35s |

---

## 📋 Requirements

```
fastapi
uvicorn[standard]
zendriver
python-dotenv
httpx
```
