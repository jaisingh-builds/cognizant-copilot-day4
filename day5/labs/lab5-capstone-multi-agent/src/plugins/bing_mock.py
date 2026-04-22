"""Day 5 · Lab 5 · Part 1b — Bing search mock.

Canned HR-relevant results so the lab works without a Bing API key.
Returns realistic-looking snippets keyed by obvious topic words.
"""

_CANNED = {
    "parental leave": [
        (
            "EU parental leave benchmarks — SHRM 2024",
            "https://example.com/shrm-eu-parental-leave-2024",
            "The EU average paid parental leave is 14 weeks; "
            "progressive tech employers offer 16–20 weeks. "
            "Only 12% of EU employers offer 12+ weeks fully paid.",
        ),
        (
            "Global parental leave trends — OECD 2024",
            "https://example.com/oecd-parental-leave-2024",
            "Nordic countries average 43 weeks; Southern Europe "
            "averages 18 weeks. US federal baseline is 0 weeks "
            "paid, though 40% of US tech employers now offer 12+.",
        ),
        (
            "Tech sector parental leave survey — LinkedIn",
            "https://example.com/linkedin-tech-parental-2024",
            "Among top 50 tech employers, median paid parental leave "
            "is 18 weeks; 72% offer ≥ 12 weeks.",
        ),
    ],
    "vacation policy": [
        (
            "Vacation policy benchmarks — Willis Towers Watson 2024",
            "https://example.com/wtw-vacation-2024",
            "Median vacation allowance at US-headquartered tech firms "
            "is 20 days/year; EU firms average 25–30 days.",
        ),
        (
            "Unlimited PTO adoption — Harvard Business Review",
            "https://example.com/hbr-unlimited-pto",
            "28% of US tech firms now offer unlimited PTO; actual "
            "usage averages 14–18 days — lower than traditional caps.",
        ),
    ],
    "bereavement leave": [
        (
            "Bereavement leave benchmarks — SHRM 2023",
            "https://example.com/shrm-bereavement",
            "US employer median bereavement leave is 3–5 days paid. "
            "Progressive employers offer up to 10 days for immediate "
            "family.",
        ),
    ],
    "benefits": [
        (
            "Tech benefits benchmark — Mercer 2024",
            "https://example.com/mercer-tech-benefits",
            "Median 401(k) match at tech firms is 4%; top-quartile "
            "offers 6%. ESPP discounts median 10%; top-quartile 15%.",
        ),
    ],
    "travel policy": [
        (
            "Corporate travel per diem — GSA rates 2024",
            "https://example.com/gsa-per-diem",
            "US federal per diem for major metros averages $80–$95/day. "
            "International per diems range $100–$180/day depending on "
            "destination.",
        ),
    ],
}

_FALLBACK = [
    (
        "General HR benchmark — Gartner 2024",
        "https://example.com/gartner-hr-benchmarks",
        "HR policy benchmarks vary widely by industry and region. "
        "Consider aligning to the median of your sector before "
        "promoting specific numbers externally.",
    )
]


def mock_search(query: str) -> str:
    q = query.lower()
    for key, results in _CANNED.items():
        if key in q:
            return "\n\n".join(
                f"[{i+1}] {name}\n    {url}\n    {snippet}"
                for i, (name, url, snippet) in enumerate(results)
            )
    # generic fallback
    name, url, snippet = _FALLBACK[0]
    return f"[1] {name}\n    {url}\n    {snippet}"
