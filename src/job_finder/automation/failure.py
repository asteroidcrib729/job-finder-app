"""Surface a failed production step after recovery and evidence uploads finish."""


def main():
    print("::error::Pipeline or state persistence failed. Inspect the earlier step logs.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
