"""Optional public remote feeds, sharing the same eligibility and delivery pipeline."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from scrapers.base import Job, parse_date
from scrapers.common import SourceError, SourceResult, QueryOutcome, get_public, host_allowed
from scrapers.structured import plain_html


def parse_remotive(payload, limit):
    rows = payload.get("jobs")
    if not isinstance(rows, list):
        raise SourceError("parse_failed", "jobs_not_list")
    jobs, invalid = [], 0
    for row in rows[:limit]:
        try:
            if not host_allowed(row.get("url", ""), ("remotive.com",)):
                raise ValueError("Invalid source link")
            jobs.append(Job(title=row["title"], company=row.get("company_name", ""),
                location=row.get("candidate_required_location", ""), candidate_locations=row.get("candidate_required_location", ""),
                url=row["url"], platform="Remotive", source_id=str(row["id"]), is_remote=True,
                description=plain_html(row.get("description")), description_status="full",
                posted_at=row.get("publication_date", ""), date_source="feed",
                job_type=row.get("job_type", ""), salary_text=row.get("salary", ""), active_status="active"))
        except (ValueError, KeyError, TypeError, AttributeError):
            invalid += 1
    return jobs, invalid


def parse_wwr(text, limit):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SourceError("parse_failed", "invalid_feed_xml") from exc
    if root.tag != "rss" or root.find("channel") is None:
        raise SourceError("parse_failed", "not_rss")
    jobs, invalid = [], 0
    for item in root.findall("./channel/item")[:limit]:
        try:
            url = item.findtext("link", "")
            if not host_allowed(url, ("weworkremotely.com",)):
                raise ValueError("Invalid source link")
            title = item.findtext("title", "")
            company, separator, role = title.partition(": ")
            date = item.findtext("pubDate", "")
            try:
                date = parsedate_to_datetime(date).isoformat() if date else ""
            except (ValueError, TypeError):
                date = ""
            jobs.append(Job(title=role if separator else title, company=company if separator else "",
                location=item.findtext("region", ""), candidate_locations=item.findtext("region", ""),
                url=url, platform="We Work Remotely", is_remote=True, posted_at=date, date_source="feed",
                description=plain_html(item.findtext("description", "")), description_status="full",
                active_status="active"))
        except (ValueError, TypeError):
            invalid += 1
    return jobs, invalid


def fetch_remote_feeds(config, discovery=None):
    options = config["remote_feeds"]
    result = SourceResult("Remote feeds")
    discovery = discovery or {}
    specs = [
        ("remotive", "https://remotive.com/api/remote-jobs?category=software-dev", ("remotive.com",)),
        ("wwr", "https://weworkremotely.com/categories/remote-programming-jobs.rss", ("weworkremotely.com",)),
    ]
    enabled = False
    for name, url, domains in specs:
        if not options[name + "_enabled"]:
            continue
        enabled = True
        key = "feed:" + name
        previous = parse_date(discovery.get(key, {}).get("last_success"))
        now = datetime.now(timezone.utc)
        if previous and (now - previous).total_seconds() < options["interval_hours"] * 3600:
            result.report.notes.append(name + "_not_due")
            continue
        try:
            response = get_public(url, domains)
            if name == "remotive":
                jobs, invalid = parse_remotive(response.json(), options["max_jobs"])
            else:
                jobs, invalid = parse_wwr(response.text, options["max_jobs"])
            result.extend(jobs)
            result.report.queries.append(QueryOutcome(key, "partial" if invalid else "success" if jobs else "valid_empty",
                len(jobs) + invalid, len(jobs), invalid))
            if not invalid:
                result.updates[key] = {"last_success": now.isoformat()}
        except SourceError as exc:
            result.report.queries.append(QueryOutcome(key, exc.status, reason=exc.reason))
        except (ValueError, TypeError, AttributeError):
            result.report.queries.append(QueryOutcome(key, "parse_failed", reason="invalid_feed_payload"))
    result.report.skipped = not enabled or not result.report.queries
    return result
