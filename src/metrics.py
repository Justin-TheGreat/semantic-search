from prometheus_client import Counter, Histogram

search_requests = Counter(
    "search_requests_total",
    "Total search requests",
    ["cached"],
)

search_latency = Histogram(
    "search_latency_seconds",
    "Search latency in seconds",
)