from ddgs import DDGS
import re

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

queries = [
    'LinkedIn Karachi hiring Software Engineer',
    'LinkedIn Karachi hiring Python Developer',
    'LinkedIn Karachi send CV Software Developer',
    'site:linkedin.com/posts Karachi hiring Python',
    'site:linkedin.com/feed/update Karachi hiring'
]

ddgs = DDGS()
for q in queries:
    print(f"\n--- Query: {q} ---")
    try:
        results = list(ddgs.text(q, max_results=5))
        print(f"Found {len(results)} results:")
        for r in results:
            title = r.get("title", "")
            url = r.get("href", "")
            body = r.get("body", "")
            emails = re.findall(EMAIL_REGEX, f"{title} {body}")
            print("Title:", title)
            print("URL:", url)
            print("Snippet:", body[:140])
            if emails:
                print("Emails found:", emails)
            print("---")
    except Exception as e:
        print("Error:", e)
