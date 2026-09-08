"""Extract explicitly published JobPosting fields; never infer city from a query."""
import json
from bs4 import BeautifulSoup
from scrapers.base import Job, clean_text


def plain_html(text):
    return BeautifulSoup(clean_text(text), "html.parser").get_text(" ", strip=True)


def jsonld_objects(soup):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            yield value
            for key in ("@graph", "itemListElement", "item"):
                if key in value:
                    yield from walk(value[key])
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue


def schema_locations(value):
    values = value if isinstance(value, list) else [value]
    locations = []
    for item in values:
        if isinstance(item, str):
            locations.append(item)
        elif isinstance(item, dict):
            address = item.get("address", item)
            if isinstance(address, str):
                locations.append(address)
            elif isinstance(address, dict):
                pieces = []
                for key in ("addressLocality", "addressRegion", "addressCountry"):
                    value = address.get(key, "")
                    if isinstance(value, dict):
                        value = value.get("name", "")
                    if value:
                        pieces.append(clean_text(value))
                locations.append(", ".join(pieces) or clean_text(item.get("name")))
    return "; ".join(filter(None, locations))


def job_from_schema(data, fallback_url, platform):
    company = data.get("hiringOrganization", {})
    company = company.get("name", "") if isinstance(company, dict) else ""
    identifier = data.get("identifier", {})
    identifier = identifier.get("value", "") if isinstance(identifier, dict) else clean_text(identifier)
    salary = data.get("baseSalary") or {}
    if not isinstance(salary, dict):
        salary = {}
    value = salary.get("value") or {}
    if not isinstance(value, dict):
        value = {"value": value}
    remote = clean_text(data.get("jobLocationType")).upper() == "TELECOMMUTE"
    description = plain_html(data.get("description", ""))
    return Job(
        title=clean_text(data.get("title")), company=company,
        location=schema_locations(data.get("jobLocation", [])),
        url=clean_text(data.get("url")) or fallback_url, platform=platform,
        source_id=clean_text(identifier), description=description,
        description_status="full" if description else "missing",
        is_remote=True if remote else None,
        candidate_locations=schema_locations(data.get("applicantLocationRequirements", [])),
        posted_at=clean_text(data.get("datePosted")), expires_at=clean_text(data.get("validThrough")),
        date_source="structured_data", job_type=clean_text(data.get("employmentType")),
        salary_min=value.get("minValue", value.get("value")),
        salary_max=value.get("maxValue"), salary_currency=clean_text(salary.get("currency")),
        salary_interval=clean_text(value.get("unitText")), salary_source="disclosed" if salary else "unknown",
        active_status="active")
