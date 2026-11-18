"""Report layer: typed ``FactorReport`` and a self-contained HTML renderer."""

from factordesk.report.render_html import render_report_html, write_report
from factordesk.report.schema import (
    FACTOR_NAMES,
    SCHEMA_VERSION,
    FactorReport,
    dump_report,
    load_report,
    report_json_schema,
)

__all__ = [
    "FACTOR_NAMES",
    "SCHEMA_VERSION",
    "FactorReport",
    "dump_report",
    "load_report",
    "render_report_html",
    "report_json_schema",
    "write_report",
]
