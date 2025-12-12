#!/usr/bin/env python3
# Full job scraper with debug logs for GitHub Actions

import re
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from datetime import datetime, timedelta, timezone

print("✔ Script started")

# ---------------- ENV VARIABLES ----------------
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "Daily Java + Angular Jobs for Anil")

print("✔ Loaded environment variables")

HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCH_QUERIES = [
    ("https://in.indeed.com/jobs?q=Java+Angular+Full+Stack&l=", "indeed"),
    ("https://internshala.com/internships/keyword-java%20angular", "internshala"),
]

NOTICE_RE = re.compile(r"\b(\d{1,3})\s*(?:day|days)\b", re.I)
NINETY_RE = re.compile(r"\b90\s*(?:day|days)\b", re.I)
IMMEDIATE_RE = re.compile(r"\b(immediate|asap|join immediately)\b", re.I)

def detect_notice(text):
    if not text:
        return "Not stated"
    t = text.lower()
    if IMMEDIATE_RE.search(t):
        return "Immediate"
    if NINETY_RE.search(t):
        return "90 days"
    m = NOTICE_RE.search(t)
    if m:
        return f"{m.group(1)} days"
    return "Not stated"

# ---------------- SCRAPE INDEED ----------------
def scrape_indeed(url):
    print("🔍 Scraping Indeed...")
    jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("a.tapItem")
        print(f"✔ Indeed cards found: {len(cards)}")

        for c in cards[:10]:
            try:
                title = c.select_one("h2.jobTitle span").get_text(strip=True)
                company = c.select_one(".companyName").get_text(strip=True)
                link = c.get("href")
                if link and link.startswith("/"):
                    link = "https://in.indeed.com" + link
                snippet = c.select_one(".job-snippet").get_text(" ", strip=True)
                notice = detect_notice(snippet)

                jobs.append({
                    "source": "Indeed",
                    "title": title,
                    "company": company,
                    "link": link,
                    "snippet": snippet,
                    "notice": notice
                })
            except Exception as e:
                print("⚠️ Error reading Indeed card:", e)
                continue
    except Exception as e:
        print("❌ Indeed request error:", e)

    print(f"✔ Final Indeed jobs: {len(jobs)}")
    return jobs

# ---------------- SCRAPE INTERNSHALA ----------------
def scrape_internshala(url):
    print("🔍 Scraping Internshala...")
    jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".internship_meta")
        print(f"✔ Internshala cards found: {len(cards)}")

        for c in cards[:10]:
            try:
                title = c.select_one("a").get_text(strip=True)
                link = c.select_one("a").get("href")
                if link.startswith("/"):
                    link = "https://internshala.com" + link
                company = c.select_one(".company_name").get_text(strip=True)
                snippet = c.get_text(" ", strip=True)[:200]
                notice = detect_notice(snippet)

                jobs.append({
                    "source": "Internshala",
                    "title": title,
                    "company": company,
                    "link": link,
                    "snippet": snippet,
                    "notice": notice
                })
            except Exception as e:
                print("⚠️ Error reading Internshala card:", e)
                continue
    except Exception as e:
        print("❌ Internshala request error:", e)

    print(f"✔ Final Internshala jobs: {len(jobs)}")
    return jobs

# ---------------- GATHER JOBS ----------------
def gather_jobs():
    print("✔ Gathering all jobs...")
    all_jobs = []

    all_jobs += scrape_indeed(SEARCH_QUERIES[0][0])
    all_jobs += scrape_internshala(SEARCH_QUERIES[1][0])

    print(f"✔ Total raw jobs: {len(all_jobs)}")

    seen = set()
    unique = []

    for j in all_jobs:
        key = (j["title"], j["company"], j["link"])
        if key not in seen:
            seen.add(key)
            unique.append(j)

    print(f"✔ UNIQUE jobs: {len(unique)}")
    return unique

# ---------------- BUILD HTML ----------------
def build_html_email(jobs):
    print("✔ Building HTML email...")
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = now.strftime("%d %b %Y, %I:%M %p IST")

    rows = ""
    for j in jobs:
        notice_style = "background:#ff4d4d;color:white" if j["notice"] == "90 days" else "background:#eee"
        rows += f"""
        <tr>
            <td><b>{j['title']}</b><br>{j['company']}<br><a href="{j['link']}">Apply</a></td>
            <td>{j['snippet']}</td>
            <td><span style='{notice_style};padding:4px;border-radius:4px'>{j['notice']}</span></td>
        </tr>
        """

    if not rows:
        rows = "<tr><td colspan='3'>No jobs found today.</td></tr>"

    html = f"""
    <h2>{EMAIL_SENDER_NAME} — {date_str}</h2>
    <table border='1' cellpadding='8'>
        <tr><th>Job</th><th>Description</th><th>Notice</th></tr>
        {rows}
    </table>
    """
    return html

# ---------------- SEND EMAIL ----------------
def send_email(subject, html_body):
    print("📨 Preparing to send email...")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL

        msg.attach(MIMEText("HTML required", "plain"))
        msg.attach(MIMEText(html_body, "html"))

        print("✔ Connecting to Gmail SMTP…")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)

        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        server.quit()

        print("🎉 EMAIL SENT SUCCESSFULLY!")
    except Exception as e:
        print("❌ EMAIL FAILED:", e)
        raise

# ---------------- MAIN ----------------
def main():
    print("🚀 Starting script...")
    jobs = gather_jobs()
    html = build_html_email(jobs)

    # Save email preview
    with open("last_email.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✔ Saved last_email.html")

    subject = f"{EMAIL_SENDER_NAME} — {datetime.now().strftime('%d %b %Y')}"
    send_email(subject, html)

print("✔ Running main() now...")
main()
print("✔ Script completed")
