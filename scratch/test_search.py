"""Manual diagnostic only; importing this file never searches the network."""


def main():
    from ddgs import DDGS
    from config import load_config
    config = load_config()
    with DDGS(timeout=8) as search:
        for query in config["linkedin_posts"]["queries"]:
            print(query)
            for result in search.text(query, timelimit="m", max_results=6):
                print(result.get("title", ""), result.get("href", ""))


if __name__ == "__main__":
    main()
