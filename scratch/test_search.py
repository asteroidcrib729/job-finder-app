import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ddgs import DDGS
import re

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

queries = [
    'site:linkedin.com/posts "Karachi" ("send CV" OR "apply at" OR "email" OR "hiring") ("developer" OR "engineer" OR "Python" OR "React")',
    'site:linkedin.com/feed/update "Karachi" ("hiring" OR "send CV") ("developer" OR "engineer" OR "React" OR "Python")',
    'site:linkedin.com/posts "Remote" ("hiring" OR "send CV") ("Python" OR "React" OR "Full Stack" OR "Node")'
]

ddgs = DDGS()
for q in queries:
    print(f"\n==========================================")
    print(f"Testing timelimit='m': {q}")
    print(f"==========================================")
    try:
        results = list(ddgs.text(q, timelimit='m', max_results=6))
        print(f"Found {len(results)} fresh posts:")
        for r in results:
            title = r.get("title", "")
            url = r.get("href", "")
            body = r.get("body", "")
            print("Title:", title)
            print("URL:", url)
            print("Snippet:", body[:200])
            emails = re.findall(EMAIL_REGEX, f"{title} {body}")
            if emails:
                print("Emails:", emails)
            print("---")
    except Exception as e:
        print("Error with timelimit='m':", e)
