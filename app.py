from flask import Flask, render_template, redirect, url_for, request, jsonify
import json
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

IHC_SEGMENTS = ['IHC - Company', 'IHC - Apartment', 'IHC - Hotel']
CW_SEGMENTS  = ['Corp Wellness - HR', 'Corp Wellness - Broker', 'Corp Wellness - Insurance']

CALENDAR_PHASES = [
    {'label': 'Prospecting',   'icon': 'search',            'color': '#6366f1', 'months': list(range(1, 13))},
    {'label': 'Cold Outreach', 'icon': 'send',              'color': '#0ea5e9', 'months': list(range(2, 12))},
    {'label': 'Follow-up',     'icon': 'arrow-repeat',      'color': '#f59e0b', 'months': list(range(3, 12))},
    {'label': 'Meeting & Demo','icon': 'people',             'color': '#10b981', 'months': list(range(4, 11))},
    {'label': 'Proposal',      'icon': 'file-earmark-text', 'color': '#f97316', 'months': list(range(5, 11))},
    {'label': 'Closing',       'icon': 'trophy',            'color': '#8b5cf6', 'months': list(range(7, 13))},
    {'label': 'Qtr Review',    'icon': 'clipboard-check',   'color': '#475569', 'months': [3, 6, 9, 12]},
]

MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

VALID_SEGMENTS = set(IHC_SEGMENTS + CW_SEGMENTS)
VALID_STATUSES = {
    'New', 'Researching', 'Contacted', 'Replied', 'Follow Up',
    'Meeting Set', 'Proposal Sent', 'Qualified/ Won',
    'Not a Fit', 'Ghosted', 'Rejected',
}
REQUIRED_FIELDS = {'companyName', 'icpSegment', 'outreachStatus', 'createdTime'}

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')


def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_week_bounds():
    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return (
        monday.replace(hour=0,  minute=0,  second=0,  microsecond=0),
        sunday.replace(hour=23, minute=59, second=59, microsecond=999999),
    )


def _parse_dt(value) -> datetime:
    """Parse any ISO-8601 string and always return a UTC-aware datetime, or None."""
    if not value or not isinstance(value, str):
        return None
    try:
        # Normalise the trailing 'Z' — fromisoformat understands '+00:00' on all Py 3.7+
        dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        # If the string had no offset at all, treat it as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OverflowError):
        return None


def compute_metrics(entries):
    week_start, week_end = get_week_bounds()
    metrics = {'contacted': 0, 'replied': 0, 'meeting_set': 0}
    for e in entries:
        ct = _parse_dt(e.get('createdTime'))
        if ct is None:
            continue
        if week_start <= ct <= week_end:
            s = e.get('outreachStatus', '')
            if s == 'Contacted':
                metrics['contacted'] += 1
            elif s == 'Replied':
                metrics['replied'] += 1
            elif s == 'Meeting Set':
                metrics['meeting_set'] += 1
    return metrics


def shared_context():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return {
        'now_month':   today.month,
        'month_names': MONTH_NAMES,
        'phases':      CALENDAR_PHASES,
        'week_label':  f"{monday.strftime('%d %b')} – {sunday.strftime('%d %b %Y')}",
    }


@app.route('/')
def index():
    return redirect(url_for('ihc'))


@app.route('/ihc')
def ihc():
    data    = load_data()
    entries = [d for d in data if d.get('icpSegment') in IHC_SEGMENTS]
    return render_template(
        'dashboard.html',
        entries=entries,
        metrics=compute_metrics(entries),
        active='ihc',
        title='IHC Dashboard',
        subtitle='IHC - Company · IHC - Apartment · IHC - Hotel',
        accent='#34b6f8',
        **shared_context(),
    )


@app.route('/cw')
def cw():
    data    = load_data()
    entries = [d for d in data if d.get('icpSegment') in CW_SEGMENTS]
    return render_template(
        'dashboard.html',
        entries=entries,
        metrics=compute_metrics(entries),
        active='cw',
        title='Corp Wellness Dashboard',
        subtitle='Corp Wellness - HR · Broker · Insurance',
        accent='#34b6f8',
        **shared_context(),
    )


@app.route('/update-data', methods=['POST'])
def update_data():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return jsonify({'error': 'Request body must be a JSON array of lead objects'}), 400

    errors = []
    for i, entry in enumerate(payload):
        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            errors.append(f'Entry {i} ({entry.get("companyName", "?")!r}): missing {sorted(missing)}')

    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return jsonify({'ok': True, 'saved': len(payload)}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)
