#!/usr/bin/env python3
# Multi-source job scraper + daily email digest
# Sources: Indeed, Internshala, Naukri, Foundit (Monster), Hirist, LinkedIn (public)
# Keywords: Java, Angular, Full Stack, Frontend, Backend, Spring Boot
# Designed to run inside GitHub Actions (uses env secrets for Gmail sending)

import re
import time
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

print("▶ jobs_scraper.py starting")

# ---------- ENV ----------
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "Daily Java + Angular Jobs for Anil")

# ---------- CONFIG ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}
# broad keyword set covering common relevant roles
KEYWORDS = [
    "Java Angular Full Stack",
    "Java Full Stack",
    "Angular Developer",
    "Java Developer",
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "Spring Boot Developer"
]

# limits & polite delays
PER_SOURCE_LIMIT = 8        # jobs per keyword per source
REQUEST_DELAY = 1.2         # seconds between requests

# notice detection regexes
NOTICE_RE = re.compile(r"\b(\d{1,3})\s*(?:day|days)\b", re.I)
IMMEDIATE_RE = re.compile(r"\b(immediate|asap|join immediately|join asap|immediately)\b", re.I)
NINETY_RE = re.compile(r"\b90\s*(?:day|days)\b", re.I)

def detect_notice_period(text):
    if not text:
        return "Not stated"
    t = text.replace("\n", " ").lower()
    if IMMEDIATE_RE.search(t):
        return "Immediate"
    if NINETY_RE.search(t):
        return "90 days"
    m = NOTICE_RE.search(t)
    if m:
        return f"{int(m.group(1))} days"
    return "Not stated"

# ---------- SCRAPERS ----------
def scrape_indeed_for(query):
    q = quote_plus(query)
    url = f"https://in.indeed.com/jobs?q={q}&l="
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("a.tapItem") or soup.select(".result")
        # iterate top cards
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                title = (c.select_one("h2.jobTitle span") or c.select_one("h2.jobTitle")).get_text(strip=True)
                company = (c.select_one(".companyName") or c.select_one(".company")).get_text(strip=True) if (c.select_one(".companyName") or c.select_one(".company")) else "Unknown"
                link = c.get("href") or (c.select_one("a") and c.select_one("a").get("href"))
                if link and link.startswith("/"):
                    link = "https://in.indeed.com" + link
                snippet_node = c.select_one(".job-snippet")
                snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
                notice = detect_notice_period(snippet)
                results.append(dict(source="Indeed", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                # ignore individual card parse errors
                print("indeed-card-err:", e)
                continue
    except Exception as e:
        print("indeed-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"Indeed: {len(results)} results for '{query}'")
    return results

def scrape_internshala_for(query):
    # Internshala is mostly internships; use its keyword search
    q = quote_plus(query)
    url = f"https://internshala.com/internships/keyword-{q}"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".internship_meta") or soup.select(".item")
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                a = c.select_one("a")
                title = a.get_text(strip=True) if a else "No title"
                link = a.get("href") if a else None
                if link and link.startswith("/"):
                    link = "https://internshala.com" + link
                company = (c.select_one(".company_name") or c.select_one(".company")).get_text(strip=True) if (c.select_one(".company_name") or c.select_one(".company")) else "Unknown"
                snippet = c.get_text(" ", strip=True)[:200]
                notice = detect_notice_period(snippet)
                results.append(dict(source="Internshala", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                print("internshala-card-err:", e)
                continue
    except Exception as e:
        print("internshala-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"Internshala: {len(results)} results for '{query}'")
    return results

def scrape_naukri_for(query):
    q = quote_plus(query)
    url = f"https://www.naukri.com/{q}-jobs"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".jobTuple") or soup.select(".list")
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                title_node = c.select_one("a.title") or c.select_one("h2.title")
                title = title_node.get_text(strip=True) if title_node else "No title"
                company_node = c.select_one("a.subTitle") or c.select_one(".companyName")
                company = company_node.get_text(strip=True) if company_node else "Unknown"
                link = title_node.get("href") if title_node and title_node.get("href") else None
                snippet = c.get_text(" ", strip=True)[:250]
                notice = detect_notice_period(snippet)
                results.append(dict(source="Naukri", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                print("naukri-card-err:", e)
                continue
    except Exception as e:
        print("naukri-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"Naukri: {len(results)} results for '{query}'")
    return results

def scrape_foundit_for(query):
    # Foundit is the rebranded Monster; their public search url:
    q = quote_plus(query)
    url = f"https://www.foundit.in/jobs?q={q}"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".card__job") or soup.select(".job-tile") or soup.select(".jobCard")
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                title_node = c.select_one("h3") or c.select_one(".card-title") or c.select_one("a")
                title = title_node.get_text(strip=True) if title_node else "No title"
                company_node = c.select_one(".company") or c.select_one(".card-subtitle")
                company = company_node.get_text(strip=True) if company_node else "Unknown"
                link = c.select_one("a").get("href") if c.select_one("a") else None
                if link and link.startswith("/"):
                    link = "https://www.foundit.in" + link
                snippet = c.get_text(" ", strip=True)[:200]
                notice = detect_notice_period(snippet)
                results.append(dict(source="Foundit", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                print("foundit-card-err:", e)
                continue
    except Exception as e:
        print("foundit-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"Foundit: {len(results)} results for '{query}'")
    return results

def scrape_hirist_for(query):
    q = quote_plus(query)
    url = f"https://hirist.com/search?query={q}"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".job") or soup.select(".job-card")
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                title_node = c.select_one("a.job-title") or c.select_one("h2")
                title = title_node.get_text(strip=True) if title_node else "No title"
                company_node = c.select_one(".company") or c.select_one(".company-name")
                company = company_node.get_text(strip=True) if company_node else "Unknown"
                link = title_node.get("href") if title_node and title_node.get("href") else None
                if link and link.startswith("/"):
                    link = "https://hirist.com" + link
                snippet = c.get_text(" ", strip=True)[:200]
                notice = detect_notice_period(snippet)
                results.append(dict(source="Hirist", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                print("hirist-card-err:", e)
                continue
    except Exception as e:
        print("hirist-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"Hirist: {len(results)} results for '{query}'")
    return results

def scrape_linkedin_public_for(query):
    # LinkedIn public search (no login) — limited and sometimes blocked
    q = quote_plus(query)
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=India"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # LinkedIn has many dynamic classes; try common anchors
        cards = soup.select("ul.jobs-search__results-list li") or soup.select(".result-card")
        for c in cards[:PER_SOURCE_LIMIT]:
            try:
                title_node = c.select_one("h3") or c.select_one(".job-card-list__title")
                title = title_node.get_text(strip=True) if title_node else "No title"
                company_node = c.select_one("h4") or c.select_one(".job-card-container__company-name")
                company = company_node.get_text(strip=True) if company_node else "Unknown"
                link_node = c.select_one("a")
                link = link_node.get("href") if link_node and link_node.get("href") else None
                snippet = c.get_text(" ", strip=True)[:200]
                notice = detect_notice_period(snippet)
                results.append(dict(source="LinkedIn", title=title, company=company, link=link, snippet=snippet, notice=notice))
            except Exception as e:
                print("linkedin-card-err:", e)
                continue
    except Exception as e:
        print("linkedin-request-error:", e)
    time.sleep(REQUEST_DELAY)
    print(f"LinkedIn: {len(results)} results for '{query}'")
    return results

# ---------- AGGREGATION ----------
def gather_all_jobs(keywords):
    print("Gathering jobs for keywords:", keywords)
    all_found = []  # list of dicts with fields: keyword, source, title, company, link, snippet, notice
    for kw in keywords:
        try:
            print(f"=== Searching: {kw} ===")
            # indeed
            all_found += [{"keyword": kw, **j} for j in scrape_indeed_for(kw)]
            # internshala
            all_found += [{"keyword": kw, **j} for j in scrape_internshala_for(kw)]
            # naukri
            all_found += [{"keyword": kw, **j} for j in scrape_naukri_for(kw)]
            # foundit
            all_found += [{"keyword": kw, **j} for j in scrape_foundit_for(kw)]
            # hirist
            all_found += [{"keyword": kw, **j} for j in scrape_hirist_for(kw)]
            # linkedin public
            all_found += [{"keyword": kw, **j} for j in scrape_linkedin_public_for(kw)]
        except Exception as e:
            print("error during keyword search:", kw, e)
            continue
    # deduplicate by (source, title, company, link)
    seen = set()
    unique = []
    for item in all_found:
        key = (item.get("source"), item.get("title"), item.get("company"), item.get("link"))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    print(f"Total unique jobs gathered: {len(unique)}")
    return unique

# ---------- EMAIL BUILD ----------
def build_grouped_html(jobs):
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    header = f"<h2>{EMAIL_SENDER_NAME} — {now.strftime('%d %b %Y, %I:%M %p IST')}</h2>"
    style = """
    <style>
    table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    th { background: #f6f6f6; }
    .notice-90 { background:#ff4d4d; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; }
    .notice-other { background:#eee; padding:4px 6px; border-radius:4px; }
    .source { font-size:13px; color:#555; margin-bottom:6px; }
    </style>
    """
    if not jobs:
        body = header + style + "<p>No jobs found today.</p>"
        return body

    # group by source then keyword for readability
    grouped = {}
    for j in jobs:
        src = j.get("source", "Other")
        grouped.setdefault(src, []).append(j)

    body = header + style
    for src, items in grouped.items():
        body += f"<h3 class='source'>{src} — {len(items)} results</h3>"
        body += "<table><thead><tr><th>Role & Company</th><th>Snippet</th><th>Keyword</th><th>Notice</th></tr></thead><tbody>"
        for it in items:
            title = it.get("title", "No title")
            company = it.get("company", "Unknown")
            link = it.get("link") or "#"
            snippet = (it.get("snippet") or "")[:400]
            keyword = it.get("keyword") or ""
            notice = it.get("notice") or "Not stated"
            if "90" in notice:
                notice_html = f"<span class='notice-90'>90 days</span>"
            else:
                notice_html = f"<span class='notice-other'>{notice}</span>"
            body += f"<tr><td><a href='{link}'><b>{title}</b></a><br/>{company}</td><td>{snippet}</td><td>{keyword}</td><td>{notice_html}</td></tr>"
        body += "</tbody></table><br/>"

    body += "<p>Note: 90-days notice periods are highlighted in red.</p>"
    return body

# ---------- SEND EMAIL ----------
def send_email(subject, html_body):
    print("Preparing email to:", RECIPIENT_EMAIL)
    if not (GMAIL_USER and GMAIL_APP_PASSWORD and RECIPIENT_EMAIL):
        raise EnvironmentError("Missing GMAIL_USER / GMAIL_APP_PASSWORD / RECIPIENT_EMAIL environment variables")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{EMAIL_SENDER_NAME} <{GMAIL_USER}>"
        msg["To"] = RECIPIENT_EMAIL
        part1 = MIMEText("Open this email in an HTML-capable client.", "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print("Email sent successfully to", RECIPIENT_EMAIL)
    except Exception as e:
        print("Error sending email:", repr(e))
        # save HTML for debugging
        try:
            with open("last_email.html", "w", encoding="utf-8") as f:
                f.write(html_body)
            print("Saved last_email.html for debugging")
        except Exception as se:
            print("Failed to save last_email.html:", se)
        raise

# ---------- MAIN ----------
def main():
    print("Starting multi-site job scrape")
    jobs = gather_all_jobs(KEYWORDS)
    html = build_grouped_html(jobs)
    # save preview
    try:
        with open("last_email.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved last_email.html (preview)")
    except Exception as e:
        print("Failed to save preview HTML:", e)
    subject = f"{EMAIL_SENDER_NAME} — {datetime.now().strftime('%d %b %Y')}"
    send_email(subject, html)
    print("Done.")

if __name__ == "__main__":
    main()
