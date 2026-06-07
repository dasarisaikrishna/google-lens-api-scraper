import asyncio
import re
import os
import time
from urllib.parse import quote, urlparse
from dotenv import load_dotenv
import zendriver as zd

load_dotenv()

PROXY_URL = os.getenv("MRSCRAPER_PROXY", "")

if not PROXY_URL:
    raise ValueError("MRSCRAPER_PROXY not set in .env file")

def _parse_proxy(proxy_url: str):
    p = urlparse(proxy_url)
    server = f"{p.scheme}://{p.hostname}:{p.port}"
    return server, (p.username or ""), (p.password or "")

PROXY_SERVER, PROXY_USER, PROXY_PASS = _parse_proxy(PROXY_URL)

MAX_RETRIES = 4
MIN_RESULT_URLS = 5

from proxy_auth_extension import create_proxy_auth_extension

def _build_browser_args() -> list:
    ext_path = create_proxy_auth_extension(
        proxy_host="proxy.mrscraper.com",
        proxy_port="10000",
        proxy_user=PROXY_USER,
        proxy_pass=PROXY_PASS,
    )
    return [
        "--window-size=1280,800",
        "--no-sandbox",
        "--ignore-certificate-errors",
        "--disable-images",
        "--lang=en-US",
        f"--load-extension={os.path.abspath(ext_path)}",
    ]


def _count_result_urls(html: str) -> list:
    urls = re.findall(r'href="(https?://[^"]{10,})"', html)
    return [
        u for u in urls
        if not any(skip in u for skip in (
            "google.", "gstatic.", "schema.org", "w3.org",
            "googleapis.", "accounts.", "support.google"
        ))
    ]


def validate_exact_match_html(html: str) -> tuple:
    """Returns (is_valid, reason)"""
    if len(html) < 50_000:
        return False, f"HTML too small ({len(html)} chars)"

    if any(w in html.lower() for w in ["captcha", "unusual traffic", "not a robot", "/sorry?"]):
        return False, "CAPTCHA detected"

    if "udm=48" not in html:
        return False, "Not on exact match page (udm=48 missing)"

    urls = _count_result_urls(html)
    if len(urls) < 3:
        return False, f"Too few results ({len(urls)} URLs)"

    return True, f"OK — {len(urls)} results"


async def get_exact_match_html(image_url: str, retry: int = 0) -> str:
    if retry > MAX_RETRIES:
        raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded")

    lens_url = f"https://lens.google.com/uploadbyurl?url={quote(image_url)}"

    browser = await zd.start(
        headless=False,
        browser_args=_build_browser_args(),
    )

    try:
        tab = await browser.get("about:blank")

        # Enable fetch interception BEFORE any navigation
        await tab.send(zd.cdp.fetch.enable(handle_auth_requests=True))

        async def handle_auth(event):
            if hasattr(event, "auth_challenge") and event.auth_challenge:
                await tab.send(
                    zd.cdp.fetch.continue_with_auth(
                        request_id=event.request_id,
                        auth_challenge_response=zd.cdp.fetch.AuthChallengeResponse(
                            response="ProvideCredentials",
                            username=PROXY_USER,
                            password=PROXY_PASS,
                        ),
                    )
                )
            else:
                await tab.send(
                    zd.cdp.fetch.continue_request(request_id=event.request_id)
                )

        tab.add_handler(zd.cdp.fetch.RequestPaused, handle_auth)

        # Step 1: Load Lens and wait for redirect
        await tab.get(lens_url)
        await asyncio.sleep(15)

        current_url = tab.url
        print(f"  Attempt {retry + 1} | URL after Lens: {current_url[:120]}")

        if "sorry" in current_url or "captcha" in current_url.lower():
            print("  CAPTCHA detected — retrying...")
            await browser.stop()
            await asyncio.sleep(10)
            return await get_exact_match_html(image_url, retry=retry + 1)

        if "vsrid=" not in current_url:
            print("  No vsrid in URL — retrying...")
            await browser.stop()
            await asyncio.sleep(5)
            return await get_exact_match_html(image_url, retry=retry + 1)

        # Step 2: Click "Exact matches" tab by finding udm=48 link
        clicked = await tab.evaluate("""
            (() => {
                const exactLink = document.querySelector('a[href*="udm=48"]');
                if (exactLink) {
                    exactLink.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return exactLink.href;
                }
                const tabs = [];
                for (const el of document.querySelectorAll('a[href*="udm="]')) {
                    tabs.push(el.textContent.trim() + ' -> ' + el.href);
                }
                return 'NO_EXACT_TAB | available: ' + tabs.join(' || ');
            })()
        """)

        print(f"  Click result: {str(clicked)[:120]}")

        if not clicked or 'NO_EXACT_TAB' in str(clicked):
            print("  Exact matches tab not found — retrying...")
            await browser.stop()
            await asyncio.sleep(5)
            return await get_exact_match_html(image_url, retry=retry + 1)

        await asyncio.sleep(15)

        final_url = tab.url
        print(f"  Final URL: {final_url[:120]}")

        if "udm=48" not in final_url:
            print("  Click did not navigate to exact matches — retrying...")
            await browser.stop()
            await asyncio.sleep(5)
            return await get_exact_match_html(image_url, retry=retry + 1)

        if "sorry" in final_url or "captcha" in final_url.lower():
            print("  CAPTCHA on exact match page — retrying...")
            await browser.stop()
            await asyncio.sleep(10)
            return await get_exact_match_html(image_url, retry=retry + 1)

        html = await tab.get_content()

        # Validate HTML before returning
        is_valid, reason = validate_exact_match_html(html)
        print(f"  Validation: {reason}")

        if not is_valid:
            print(f"  Invalid HTML — retrying...")
            await browser.stop()
            await asyncio.sleep(5)
            return await get_exact_match_html(image_url, retry=retry + 1)

        return html

    finally:
        try:
            await browser.stop()
        except Exception:
            pass


if __name__ == "__main__":
    test_url = "https://cdn.shopify.com/s/files/1/0070/7032/files/product-photography.jpg"

    async def _test():
        print("Running browser smoke-test...")
        start = time.time()
        html = await get_exact_match_html(test_url)
        elapsed = time.time() - start
        non_google = _count_result_urls(html)
        print(f"Done in {elapsed:.1f}s — {len(html):,} chars — {len(non_google)} result URLs")
        with open("zendriver_result.html", "w", encoding="utf-8") as fh:
            fh.write(html)
        print("Saved to zendriver_result.html")

    asyncio.run(_test())