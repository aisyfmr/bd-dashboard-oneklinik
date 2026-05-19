import json
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import (Flask, Response, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

# ── Directories ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# ══════════════════════════════════════════════════════════════════════════════
# Existing IHC / CW BD dashboard (keep unchanged)
# ══════════════════════════════════════════════════════════════════════════════
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
VALID_STATUSES = {
    'New', 'Researching', 'Contacted', 'Replied', 'Follow Up',
    'Meeting Set', 'Proposal Sent', 'Qualified/ Won',
    'Not a Fit', 'Ghosted', 'Rejected',
}
REQUIRED_FIELDS = {'companyName', 'icpSegment', 'outreachStatus', 'createdTime'}


def _load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def _parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OverflowError):
        return None


def _week_bounds():
    today = datetime.now(timezone.utc)
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return (monday.replace(hour=0, minute=0, second=0, microsecond=0),
            sunday.replace(hour=23, minute=59, second=59, microsecond=999999))


def _compute_metrics(entries):
    ws, we = _week_bounds()
    m = {'contacted': 0, 'replied': 0, 'meeting_set': 0}
    for e in entries:
        ct = _parse_dt(e.get('createdTime'))
        if ct and ws <= ct <= we:
            s = e.get('outreachStatus', '')
            if s == 'Contacted':     m['contacted'] += 1
            elif s == 'Replied':     m['replied'] += 1
            elif s == 'Meeting Set': m['meeting_set'] += 1
    return m


def _shared_ctx():
    today = datetime.now()
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6)
    return {
        'now_month':   today.month,
        'month_names': MONTH_NAMES,
        'phases':      CALENDAR_PHASES,
        'week_label':  f"{mon.strftime('%d %b')} – {sun.strftime('%d %b %Y')}",
    }


@app.route('/health')
def health():
    return 'OK', 200


@app.route('/')
def index():
    return redirect(url_for('ihc'))


@app.route('/ihc')
def ihc():
    data = _load_data()
    entries = [d for d in data if d.get('icpSegment') in IHC_SEGMENTS]
    return render_template('dashboard.html', entries=entries,
                           metrics=_compute_metrics(entries), active='ihc',
                           title='IHC Dashboard',
                           subtitle='IHC - Company · IHC - Apartment · IHC - Hotel',
                           accent='#34b6f8', **_shared_ctx())


@app.route('/cw')
def cw():
    data = _load_data()
    entries = [d for d in data if d.get('icpSegment') in CW_SEGMENTS]
    return render_template('dashboard.html', entries=entries,
                           metrics=_compute_metrics(entries), active='cw',
                           title='Corp Wellness Dashboard',
                           subtitle='Corp Wellness - HR · Broker · Insurance',
                           accent='#34b6f8', **_shared_ctx())


@app.route('/update-data', methods=['POST'])
def update_data():
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return jsonify({'error': 'Request body must be a JSON array'}), 400
    errors = []
    for i, entry in enumerate(payload):
        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            errors.append(f'Entry {i} ({entry.get("companyName","?")!r}): missing {sorted(missing)}')
    if errors:
        return jsonify({'error': 'Validation failed', 'details': errors}), 400
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True, 'saved': len(payload)}), 200


# ══════════════════════════════════════════════════════════════════════════════
# Ops Dashboard
# ══════════════════════════════════════════════════════════════════════════════

MONTHS_ID = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Ags','Sep','Okt','Nov','Des']


def _prev_week_monday():
    """Return the Monday of the previous completed week."""
    today = datetime.now()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7)


def _prev_week_label():
    """Display label for the previous week, e.g. 'Week 20  |  11–15 Mei 2026'."""
    mon = _prev_week_monday()
    fri = mon + timedelta(days=4)
    week_num = mon.isocalendar()[1]
    start = f"{mon.day} {MONTHS_ID[mon.month-1]}"
    end   = f"{fri.day} {MONTHS_ID[fri.month-1]} {fri.year}"
    return f"Week {week_num}  |  {start}–{end}"


def _prev_week_filename():
    """Filesystem-safe PDF filename for the previous week (no | character)."""
    mon = _prev_week_monday()
    fri = mon + timedelta(days=4)
    week_num = mon.isocalendar()[1]
    date_range = f"{mon.day}-{fri.day} {MONTHS_ID[mon.month-1]} {fri.year}"
    return f"Week {week_num} - {date_range} - Ops Weekly Report.pdf"


def _prev_week_display_filename():
    """Display filename with | separator for Content-Disposition header."""
    mon = _prev_week_monday()
    fri = mon + timedelta(days=4)
    week_num = mon.isocalendar()[1]
    date_range = f"{mon.day}-{fri.day} {MONTHS_ID[mon.month-1]} {fri.year}"
    return f"Week {week_num} | {date_range} - Ops Weekly Report.pdf"


def _current_gen_date():
    today = datetime.now()
    days_id = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu']
    months_id = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Ags','Sep','Okt','Nov','Des']
    return f"{days_id[today.weekday()]}, {today.day} {months_id[today.month-1]} {today.year}"


def _list_reports():
    """Return REPORTS dict { 'YYYY-MM': [{name, range, file}, ...] } from the reports/ dir."""
    result = {}
    if not os.path.isdir(REPORTS_DIR):
        return result
    for fname in sorted(os.listdir(REPORTS_DIR), reverse=True):
        if not fname.endswith('.pdf'):
            continue
        # Try to parse month from filename prefix e.g. "05-09May2026-..."
        try:
            # Look for a 4-digit year in the filename
            year_idx = next(i for i, c in enumerate(fname) if c.isdigit() and fname[i:i+4].isdigit() and int(fname[i:i+4]) > 2000)
            year = fname[year_idx:year_idx+4]
            # Find month abbreviation right before the year
            month_abbrs = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec',
                           'Mei','Ags','Okt','Nov','Des']
            month_num = None
            for abbr in month_abbrs:
                if abbr in fname:
                    abbr_months = {
                        'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Mei':5,'Jun':6,
                        'Jul':7,'Aug':8,'Ags':8,'Sep':9,'Oct':10,'Okt':10,
                        'Nov':11,'Dec':12,'Des':12
                    }
                    month_num = abbr_months.get(abbr)
                    break
            if not month_num:
                month_num = datetime.now().month
            key = f"{year}-{month_num:02d}"
            result.setdefault(key, []).append({
                'name': fname.replace('.pdf', '').replace('-', ' ').replace('_', ' '),
                'range': fname.replace('.pdf', ''),
                'file': fname,
            })
        except StopIteration:
            continue
    return result


@app.route('/ops')
def ops():
    return render_template('ops_dashboard.html')


@app.route('/api/ops/data')
def ops_data():
    """Fetch all live data from Notion and return as JSON for the dashboard."""
    from notion.bd_pipeline import fetch_bd_pipeline, compute_funnel
    from notion.marketing_calendar import fetch_marketing_calendar, format_for_dashboard
    from notion.weekly_update import fetch_all_dept_updates

    try:
        leads = fetch_bd_pipeline()
    except Exception as e:
        leads = []; print(f"BD pipeline error: {e}")

    try:
        cal_events = fetch_marketing_calendar()
        cal_data   = format_for_dashboard(cal_events)
    except Exception as e:
        cal_data = {}; print(f"Calendar error: {e}")

    try:
        dept_updates = fetch_all_dept_updates()
    except Exception as e:
        dept_updates = {}; print(f"Dept updates error: {e}")

    try:
        from notion.marketing_hub import fetch_marketing_projects
        mktg_projects = fetch_marketing_projects()
    except Exception as e:
        mktg_projects = {}; print(f"Marketing projects error: {e}")

    funnel  = compute_funnel(leads)
    reports = _list_reports()

    return jsonify({
        'ok': True,
        'sync_time': datetime.now().strftime('%d %b %Y %H:%M'),
        'week_label': _prev_week_label(),
        'leads': leads,
        'funnel': funnel,
        'calendar': cal_data,
        'dept_updates':   dept_updates,
        'mktg_projects':  mktg_projects,
        'reports':        reports,
    })


@app.route('/api/ops/generate-pdf', methods=['POST'])
def ops_generate_pdf():
    """Fetch live Notion data, generate a PDF, save to reports/, return JSON with preview URL."""
    from notion.bd_pipeline import fetch_bd_pipeline, build_pipeline_for_pdf
    from notion.weekly_update import fetch_all_dept_updates
    from pdf.generator import generate_weekly_report

    week_label = _prev_week_label()
    gen_date   = _current_gen_date()

    # Fetch live data
    try:
        leads = fetch_bd_pipeline()
    except Exception:
        leads = []

    try:
        dept_updates = fetch_all_dept_updates()
    except Exception:
        dept_updates = {}

    pipeline_rows = build_pipeline_for_pdf(leads)

    # Build the data dict for the generator
    def _dept(key):
        d = dept_updates.get(key, {})
        return {
            'highlights': d.get('highlights') or [('Update', 'No data available from Notion.')],
            'issues':     d.get('issues', []),
            'actions':    d.get('actions', []),
            'dar':        d.get('dar'),
        }

    bd_dept = _dept('bd')
    bd_dept['pipeline'] = pipeline_rows

    data = {
        'week_label':  week_label,
        'gen_date':    gen_date,
        'logo_path':   os.environ.get('LOGO_PATH',
                       os.path.join(BASE_DIR, 'static', 'logo_transparent.png')),
        'departments': {
            'marketing': _dept('marketing'),
            'finance':   _dept('finance'),
            'ga':        _dept('ga'),
            'am':        _dept('am'),
            'hr':        _dept('hr'),
            'bd':        bd_dept,
        },
        'projects': {'homecare': [], 'oneklinik': []},
    }

    # Output filename — filesystem-safe (no | character for Windows local dev)
    fs_filename      = _prev_week_filename()
    display_filename = _prev_week_display_filename()
    output_path      = os.path.join(REPORTS_DIR, fs_filename)

    try:
        generate_weekly_report(data, output_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Upload reference to Notion project-progress page (non-fatal)
    try:
        from notion.client import append_pdf_link_to_page
        append_pdf_link_to_page(
            page_id='33ac88be4d3c8050a4afd516bc034799',
            section_heading='Ops PDF Report',
            filename=display_filename,
            week_label=week_label,
            gen_date=gen_date,
        )
    except Exception as e:
        print(f"Notion PDF upload note failed (non-fatal): {e}")

    return jsonify({
        'ok':               True,
        'filename':         fs_filename,
        'display_filename': display_filename,
        'view_url':         f'/api/ops/view/{fs_filename}',
        'download_url':     f'/api/ops/download/{fs_filename}',
    })


@app.route('/api/ops/reports')
def ops_reports():
    return jsonify({'ok': True, 'reports': _list_reports()})


@app.route('/api/ops/view/<path:filename>')
def ops_view(filename):
    """Serve a PDF inline (for preview iframe)."""
    return send_from_directory(REPORTS_DIR, filename,
                               as_attachment=False,
                               mimetype='application/pdf')


@app.route('/api/ops/download/<path:filename>')
def ops_download(filename):
    return send_from_directory(REPORTS_DIR, filename,
                               as_attachment=True,
                               mimetype='application/pdf')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
