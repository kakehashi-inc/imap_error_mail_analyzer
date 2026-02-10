"""Generate Bootstrap 5 HTML bounce reports from JSON data."""

import json
import logging
import re
from datetime import datetime
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

_RE_REPORT_FILE = re.compile(r"^\d{8}_(.+)_(target|excluded)\.json$")

_CSS = """\
.bounce-table th, .bounce-table td { vertical-align: top; }
.bounce-table .col-date { white-space: nowrap; }
.bounce-table .col-detail { min-width: 18em; }
.bounce-table .col-addr { min-width: 10em; word-break: break-all; }
.bounce-table .col-subject { min-width: 10em; }
.bounce-table .col-body { white-space: nowrap; }
.detail-category { font-weight: 600; }
.detail-error { margin-top: .4em; color: #555; font-size: .9em; }
.detail-error-label { font-weight: 600; }
"""


def generate_html_report(log_dir, report_dir, date_str=None):
    """Read JSON reports for the given date and generate an HTML report.

    Parameters
    ----------
    log_dir : str
        Directory containing JSON report files.
    report_dir : str
        Directory to write the HTML report to.
    date_str : str or None
        Date in ``YYYYMMDD`` format.  Defaults to today.

    Returns
    -------
    str
        Path to the generated HTML file, or empty string if no data found.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    accounts = _collect_report_data(Path(log_dir), date_str)
    if not accounts:
        logger.debug("No report data for %s; skipping HTML generation.", date_str)
        return ""

    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"report_{date_str}.html"

    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    html = _build_html(display_date, accounts)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(out_path)


def _collect_report_data(log_dir, date_str):
    """Read JSON files and group records by account and type.

    Returns
    -------
    dict[str, dict[str, list]]
        ``{account_name: {"target": [...], "excluded": [...]}}``
    """
    accounts = {}
    for path in sorted(log_dir.glob(f"{date_str}_*_*.json")):
        match = _RE_REPORT_FILE.match(path.name)
        if not match:
            continue
        account_name = match.group(1)
        report_type = match.group(2)
        try:
            with open(path, encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            continue
        if account_name not in accounts:
            accounts[account_name] = {"target": [], "excluded": []}
        accounts[account_name][report_type] = records
    return accounts


def _build_html(display_date, accounts):
    """Build the full HTML document string."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = []
    for account_name in sorted(accounts):
        data = accounts[account_name]
        sections.append(_build_account_section(account_name, data))

    return f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bounce Report {escape(display_date)}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"\
 rel="stylesheet" crossorigin="anonymous">
<style>{_CSS}</style>
</head>
<body>
<div class="container-fluid py-4">
<h1>Bounce Report <small class="text-muted">{escape(display_date)}</small></h1>
<p class="text-muted">Generated: {escape(generated)}</p>
{"".join(sections)}
</div>
<div class="modal fade" id="bodyModal" tabindex="-1">
<div class="modal-dialog modal-lg">
<div class="modal-content">
<div class="modal-header">
<h5 class="modal-title">Body</h5>
<button type="button" class="btn-close" data-bs-dismiss="modal"></button>
</div>
<div class="modal-body">
<pre id="bodyContent" class="mb-0" style="white-space:pre-wrap;word-break:break-word;"></pre>
</div>
</div>
</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"\
 crossorigin="anonymous"></script>
<script>
document.getElementById("bodyModal").addEventListener("show.bs.modal",function(e){{
document.getElementById("bodyContent").textContent=e.relatedTarget.getAttribute("data-body");
}});
</script>
</body>
</html>"""


def _build_account_section(account_name, data):
    """Build HTML for a single account card."""
    target = data.get("target", [])
    excluded = data.get("excluded", [])

    target_html = _build_table(target) if target else '<p class="text-muted">No records</p>'
    excluded_html = _build_table(excluded) if excluded else '<p class="text-muted">No records</p>'

    return f"""\
<div class="card mb-4">
<div class="card-header"><h2 class="mb-0">{escape(account_name)}</h2></div>
<div class="card-body">
<h3>Target <span class="badge bg-danger">{len(target)}</span></h3>
{target_html}
<h3 class="mt-4">Excluded <span class="badge bg-secondary">{len(excluded)}</span></h3>
{excluded_html}
</div>
</div>"""


def _build_table(records):
    """Build an HTML table from a list of record dicts."""
    rows = []
    for rec in records:
        row = _build_row(rec)
        rows.append(row)

    return f"""\
<div class="table-responsive">
<table class="table table-sm table-hover bounce-table">
<thead><tr>\
<th class="col-date">Date</th>\
<th class="col-detail">Detail</th>\
<th class="col-addr">From</th>\
<th class="col-addr">To</th>\
<th class="col-subject">Subject</th>\
<th class="col-body">Body</th>\
</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>"""


def _build_row(rec):
    """Build a single ``<tr>`` element for a bounce record."""
    date_val = escape(str(rec.get("date", "")))
    error_code = escape(str(rec.get("error_code", "")))
    error_msg = escape(str(rec.get("error_message", "")))
    category = escape(str(rec.get("ai_responsible_party", "")))
    reason = escape(str(rec.get("ai_reason", "")))
    from_addr = escape(str(rec.get("from_addr", "")))
    to_addr = escape(str(rec.get("to_addr", "")))
    subject = escape(str(rec.get("subject", "")))

    # Date: split "yyyy-MM-dd HH:mm:ss" into date line + time line
    date_cell = "<br>".join(date_val.split(" ", 1)) if " " in date_val else date_val

    # Detail: category + reason + error code/message
    detail_cell = (
        f'<span class="detail-category">{category}</span><br>{reason}'
        f'<div class="detail-error">'
        f'<span class="detail-error-label">Error Code:</span> {error_code}<br>'
        f"{error_msg}</div>"
    )

    body = rec.get("body_plain") or rec.get("body_html") or ""
    if body:
        btn = (
            '<button class="btn btn-sm btn-outline-secondary" '
            'data-bs-toggle="modal" data-bs-target="#bodyModal" '
            f'data-body="{escape(body, quote=True)}">View</button>'
        )
    else:
        btn = ""

    return (
        f"<tr>"
        f'<td class="col-date">{date_cell}</td>'
        f'<td class="col-detail">{detail_cell}</td>'
        f'<td class="col-addr">{from_addr}</td>'
        f'<td class="col-addr">{to_addr}</td>'
        f'<td class="col-subject">{subject}</td>'
        f'<td class="col-body">{btn}</td>'
        f"</tr>"
    )
