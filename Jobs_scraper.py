#!/usr/bin/env python3
# jobs_scraper.py
# Scrapes Indeed & Internshala for "Java Angular Full Stack" roles and emails a daily HTML digest.

import re
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from datetime import datetime, timezone, timedelta

# Gmail credentials (from GitHub Secrets)
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "Daily Java + Angular Jobs for Anil")

# Public search pages
SEARCH_QUERIES = [
    ("https://in.indeed.com/jobs?q=Java+Angular+Full+Stack&l=", "indeed"),
    ("https://internshala.com/internships/keyword-java%20angular", "internshala"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Notice period patterns
NOTICE_RE = re.compile(r"\b(\d{1,3})\s*(?:day|days)\b", re.I)
IMMEDIATE_RE = re.compile(r"\b(immediate|join immediately|asap)\b", re.I)
NINETY_RE = re.compile(r"\b90\s*(?:day|days)\b", re.I)

def detect_notice_period(text):
    if not text:
        return "Not stated"
    t = text.lower()
    if IMMEDIATE_RE.search(t):
        return "Immediate"
    if NINETY_RE.search(t):
        return "90 days"
    m = NOTICE_RE.search(t)
        # Return matched days
    if m:
        return f"{m.group(1)} days"
    return "Not stated"

# ----------- SCRAPER: INDEED -------------

def scrape_indeed(url):
    jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.select("a.tapItem")
        for c in cards[:10]:  # limit to 10 jobs
            try:
                title = c.select_one("h2.jobTitle span").get_text(strip=True)
                company = c.select_one(".companyName").get_text(strip=True)
                link = c.get("href")
                if link.startswith("/"):
                    link = "https://in.indeed.com" + link
                snippet = c.select_one(".job-snippet").get_text(" ", strip=True)

                notice = detect_notice_period(snippet)

                jobs.append({
                    "source": "Indeed",
                    "title": title,
                    "company": company,
                    "link": link,
                    "snippet": snippet,
                    "notice": notice
                })
            except:
                continue
    except Exception as e:
        print("Indeed error:", e)

    return jobs

# ----------- SCRAPER: INTERNSHALA -------------

def scrape_internshala(url):
    jobs = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.select(".internship_meta")
        for c in cards[:10]:
            try:
                title = c.select_one("a").get_text(strip=True)
                link = c.select_one("a").get("href")
                if link.startswith("/"):
                    link = "https://internshala.com" + link
                company = c.select_one(".company_name").get_text(strip=True)
                snippet = c.get_text(" ", strip=True)[:200]

                notice = detect_notice_period(snippet)

                jobs.append({
                    "source": "Internshala",
                    "title": title,
                    "company": company,
                    "link": link,
                    "snippet": snippet,
                    "notice": notice
                })
            except:
                continue
    except Exception as e:
        print("Internshala error:", e)

    return jobs

# ----------- HELPER: GATHER ALL JOBS -------------

def gather_jobs():
    all_jobs = []
    for url, typ in SEARCH_QUERIES:
        if typ == "indeed":
            all_jobs += scrape_indeed(url)
        elif typ == "internshala":
            all_jobs += scrape_internshala(url)

    # Remove duplicates
    unique = []
    seen = set()
    for job in all_jobs:
        key = (job["title"], job["company"], job["link"])
        if key not in seen:
            seen.add(key)
            unique.append(job)

    return unique

# ----------- EMAIL BUILDER -------------

def build_html_email(jobs):
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = now.strftime("%d %b %Y, %I:%M %p IST")

    style = """
    <style>
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
    th { background: #f2f2f2; }
    .notice-90 { background:#ff4d4d; color:white; padding:3px; border-radius:4px; }
    .notice-other { background:#eee; padding:3px; border-radius:4px; }
    </style>
    """

    rows = ""
    for j in jobs:
        notice_html = (
            f'<span class="notice-90">90 days</span>'
            if j["notice"] == "90 days"
            else f'<span class="notice-other">{j["notice"]}</span>'
        )

        rows += f"""
        <tr>
            <td><b>{j['title']}</b><br>{j['company']}<br><a href="{j['link']}">Apply Link</a></td>
            <td>{j['snippet']}</td>
            <td>{notice_html}</td>
        </tr>
        """

    table = f"""
    <h2>{EMAIL_SENDER_NAME} — {date_str}</h2>
    {style}
    <table>
        <tr><th>Job</th><th>Description</th><th>Notice</th></tr>
        {rows}
    </table>
    """

    return table

# ----------- SEND EMAIL -------------

def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText("Your device does not support HTML email.", "plain"))
    msg.attach(MIMEText(html_body, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    server.quit()

# ----------- MAIN -------------

def main():
    jobs = gather_jobs()
    html = build_html_email(jobs)
    subject = f"{EMAIL_SENDER_NAME} — Daily Digest"
    send_email(subject, html)

if __name__ == "__main__":
    main()
