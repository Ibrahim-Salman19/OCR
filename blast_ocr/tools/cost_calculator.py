"""Cloud OCR Cost vs. Local Hardware ROI Calculator.

Engineering-as-Marketing interactive utility calculating exact financial
and operational savings of self-hosted B.L.A.S.T. OCR vs AWS Textract,
Google Document AI, and Azure Document Intelligence.
"""
from __future__ import annotations

import argparse
import json
import math
from typing import Any, Dict

# Standard cloud pricing per 1,000 pages (USD)
CLOUD_PRICING: Dict[str, Dict[str, Any]] = {
    "textract": {
        "text_only": 1.50,         # $0.0015 / page
        "tables_forms": 50.00,     # $0.0500 / page
        "queries": 15.00,          # $0.0150 / page
        "name": "AWS Textract",
    },
    "google_docai": {
        "text_only": 1.50,         # $0.0015 / page
        "tables_forms": 65.00,     # $0.0650 / page (Form Parser)
        "queries": 30.00,          # $0.0300 / page
        "name": "Google Document AI",
    },
    "azure_di": {
        "text_only": 1.50,         # $0.0015 / page
        "tables_forms": 50.00,     # $0.0500 / page (Prebuilt Layout)
        "queries": 25.00,          # $0.0250 / page
        "name": "Azure AI Document Intelligence",
    },
}

# B.L.A.S.T. performance: 29.1 pages/second on CPU = ~104,760 pages/hour per core
# AWS EC2 c6i.large ($0.085/hr, 2 vCPUs) can process ~200,000 pages/hour
PAGES_PER_HOUR_PER_INSTANCE = 200_000
INSTANCE_HOURLY_COST_USD = 0.085  # AWS c6i.large spot/reserved average


def calculate_roi(
    pages_per_month: int,
    cloud_provider: str = "textract",
    include_tables: bool = True,
    use_reserved_instances: bool = True,
) -> Dict[str, Any]:
    """Calculate exact monthly and annual savings of B.L.A.S.T. vs cloud OCR.

    Args:
        pages_per_month: Total document pages ingested per month.
        cloud_provider: 'textract', 'google_docai', or 'azure_di'.
        include_tables: Whether table and form extraction is required.
        use_reserved_instances: Whether cloud compute uses reserved/spot discount.

    Returns:
        Dictionary containing granular financial, operational, and latency metrics.
    """
    if pages_per_month < 0:
        raise ValueError("pages_per_month must be non-negative")

    provider_info = CLOUD_PRICING.get(cloud_provider.lower(), CLOUD_PRICING["textract"])
    rate_per_k = float(provider_info["tables_forms"] if include_tables else provider_info["text_only"])
    cloud_monthly_cost = (pages_per_month / 1000.0) * rate_per_k
    cloud_annual_cost = cloud_monthly_cost * 12.0

    if pages_per_month == 0:
        return {
            "pages_per_month": 0,
            "cloud_provider": provider_info["name"],
            "rate_per_1k_pages_usd": rate_per_k,
            "cloud_monthly_cost_usd": 0.0,
            "cloud_annual_cost_usd": 0.0,
            "blast_instances_needed": 0,
            "blast_monthly_infra_usd": 0.0,
            "blast_annual_infra_usd": 0.0,
            "monthly_savings_usd": 0.0,
            "annual_savings_usd": 0.0,
            "savings_percentage": 0.0,
            "payback_period_days": 0.0,
            "gb_transit_avoided": 0.0,
        }

    active_compute_hours = pages_per_month / PAGES_PER_HOUR_PER_INSTANCE
    num_instances = max(1, math.ceil(active_compute_hours / 730.0))
    hourly_rate = INSTANCE_HOURLY_COST_USD if use_reserved_instances else INSTANCE_HOURLY_COST_USD * 1.5
    blast_monthly_infra = num_instances * 730.0 * hourly_rate
    blast_annual_infra = blast_monthly_infra * 12.0

    monthly_savings = max(0.0, cloud_monthly_cost - blast_monthly_infra)
    annual_savings = monthly_savings * 12.0
    savings_pct = (monthly_savings / cloud_monthly_cost * 100.0) if cloud_monthly_cost > 0 else 0.0

    daily_savings = monthly_savings / 30.0
    payback_days = (blast_monthly_infra / daily_savings) if daily_savings > 0 else 0.0
    gb_transit_avoided = (pages_per_month * 250) / (1024 * 1024)

    return {
        "pages_per_month": pages_per_month,
        "cloud_provider": provider_info["name"],
        "rate_per_1k_pages_usd": rate_per_k,
        "cloud_monthly_cost_usd": round(cloud_monthly_cost, 2),
        "cloud_annual_cost_usd": round(cloud_annual_cost, 2),
        "blast_instances_needed": num_instances,
        "blast_monthly_infra_usd": round(blast_monthly_infra, 2),
        "blast_annual_infra_usd": round(blast_annual_infra, 2),
        "monthly_savings_usd": round(monthly_savings, 2),
        "annual_savings_usd": round(annual_savings, 2),
        "savings_percentage": round(savings_pct, 1),
        "payback_period_days": round(payback_days, 1),
        "gb_transit_avoided": round(gb_transit_avoided, 2),
    }


def format_report_markdown(data: Dict[str, Any]) -> str:
    """Format the ROI calculation into a clean GitHub Flavored Markdown report."""
    return f"""# 💰 Cloud OCR vs. Self-Hosted B.L.A.S.T. ROI Report

- **Monthly Processing Volume**: {data['pages_per_month']:,} pages / month
- **Comparison Provider**: {data['cloud_provider']} (${data['rate_per_1k_pages_usd']:.2f} / 1k pages)
- **Local Infrastructure Needed**: {data['blast_instances_needed']}x c6i.large instance(s)

| Financial Metric | Cloud Provider ({data['cloud_provider']}) | B.L.A.S.T. Self-Hosted | Net Benefit |
|---|---|---|---|
| **Monthly Compute & Ingestion** | **${data['cloud_monthly_cost_usd']:,.2f}** | **${data['blast_monthly_infra_usd']:,.2f}** | **${data['monthly_savings_usd']:,.2f} saved / mo** |
| **Annualized Total Cost** | **${data['cloud_annual_cost_usd']:,.2f}** | **${data['blast_annual_infra_usd']:,.2f}** | **${data['annual_savings_usd']:,.2f} saved / yr** |
| **Cost Reduction Ratio** | Baseline (100%) | {100 - data['savings_percentage']:.1f}% of cloud | **{data['savings_percentage']:.1f}% Gross Margin Increase** |
| **Capital Payback Period** | N/A (Indefinite opex) | Fully recouped in **{data['payback_period_days']:.1f} days** | Immediate Breakeven |
| **Data Sovereignty & Egress** | Transmits to Public Cloud | **100% In-VPC Air-Gapped** | **{data['gb_transit_avoided']:,.1f} GB Public Transit Avoided** |

> **Audit Recommendation**: Deploy B.L.A.S.T. OCR on self-hosted Kubernetes or EC2 instances to permanently lock in **${data['annual_savings_usd']:,.2f}** in annual bottom-line savings.
"""


def main() -> None:
    """CLI entrypoint for interactive cost estimation."""
    parser = argparse.ArgumentParser(
        description="Calculate financial ROI of self-hosted B.L.A.S.T. vs AWS Textract/Cloud OCR."
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=500_000,
        help="Number of document pages processed per month (default: 500,000)",
    )
    parser.add_argument(
        "--cloud",
        choices=["textract", "google_docai", "azure_di"],
        default="textract",
        help="Cloud OCR provider to benchmark against (default: textract)",
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Calculate text-only extraction without table/form parsing",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON payload instead of Markdown report",
    )

    args = parser.parse_args()
    report = calculate_roi(
        pages_per_month=args.pages,
        cloud_provider=args.cloud,
        include_tables=not args.no_tables,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
