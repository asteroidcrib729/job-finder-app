"""Split only explicit role sections; preserve the complete announcement as provenance."""
import re
from scrapers.base import Job, normalized
from scrapers.cache import query_key

ROLE_WORD = re.compile(r"\b(?:developer|engineer|designer|analyst|manager|recruiter|accountant|specialist|writer|executive|intern)\b", re.I)


def split_post_roles(post):
    if post.kind != "lead" or post.description_status != "full":
        return [post]
    lines = post.description.splitlines()
    headings = []
    for index, line in enumerate(lines):
        title = re.sub(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", "", line).strip()
        explicit = re.match(r"^(?:role|position|job title)\s*:\s*(.+)$", title, re.I)
        if explicit:
            title = explicit.group(1).strip()
        # Restrict implicit headings to short standalone role names.
        if (not explicit and (not ROLE_WORD.search(title) or len(title.split()) > 10
                or re.search(r"\b(?:required|requirements|experience|years?|must|seeking|hiring|looking|welcome)\b", title, re.I)
                or any(mark in title for mark in (". ", ":", ";")))):
            continue
        title = title.strip("*: ")
        if 3 <= len(title) <= 120:
            headings.append((index, title))
    if len(headings) < 2 or len({normalized(title) for _, title in headings}) != len(headings):
        return [post]
    # Shared context precedes roles; a clearly labeled footer can also apply to all.
    shared = "\n".join(lines[:headings[0][0]])
    end = len(lines)
    for index in range(headings[-1][0] + 1, len(lines)):
        if re.match(r"^\s*(?:for all (?:roles|positions)|common requirements|how to apply)\s*:", lines[index], re.I):
            end = index
            shared += "\n" + "\n".join(lines[index:])
            break
    candidates = []
    for number, (start, title) in enumerate(headings):
        stop = headings[number + 1][0] if number + 1 < len(headings) else end
        data = post.to_dict()
        data.update(title=title, description="\n".join(filter(None, [shared.strip(), "\n".join(lines[start:stop]).strip()])),
                    job_id="", aliases=[], source_id=query_key("role", post.url + "|" + normalized(title)),
                    source_title=post.title, source_description=post.description,
                    work_mode="unknown", is_remote=None, location="")
        # Recompute geography from role-specific/shared text, not another role's location.
        text = data["description"]
        cities = [city for city in ("Karachi", "Lahore", "Islamabad", "Hyderabad", "Rawalpindi")
                  if re.search(r"\b" + city + r"\b", text, re.I)]
        if len(cities) == 1:
            data["location"] = cities[0] + ", Pakistan"
        candidates.append(Job.from_dict(data))
    return candidates
