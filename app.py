#!/usr/bin/env python3
"""Flask web application for job search management.

Provides web interface to:
- View and filter job listings
- View job details
- Update job status
- View profile information

Usage:
    python app.py
    # Then visit http://localhost:5000
"""

from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify
from db.connection import get_db
from db.jobs import list_jobs, get_job, update_status, update_score
from db.profile import get_all_meta, list_job_history, list_skills

app = Flask(__name__)


def is_recent_job(posted_date_str):
    """Check if job was posted in the last 24 hours."""
    if not posted_date_str:
        return False
    
    try:
        # Parse posted_date (format: YYYY-MM-DD or datetime string)
        if 'T' in posted_date_str:
            posted_date = datetime.fromisoformat(posted_date_str.split('T')[0])
        else:
            posted_date = datetime.fromisoformat(posted_date_str)
        
        # Check if within last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        return posted_date.date() >= cutoff.date()
    except (ValueError, AttributeError):
        return False


# Make helper function available in templates
app.jinja_env.globals.update(is_recent_job=is_recent_job)


@app.route('/')
def index():
    """Job list page with filtering and sorting."""
    # Get filter parameters from query string
    status_filter = request.args.get('status', '')
    source_filter = request.args.get('source', '')
    min_score = request.args.get('min_score', type=float)
    order_by = request.args.get('order_by', 'posted_date DESC')
    
    # Build query parameters
    kwargs = {}
    if status_filter:
        kwargs['status'] = status_filter
    if source_filter:
        kwargs['source'] = source_filter
    if min_score is not None:
        kwargs['min_score'] = min_score
    kwargs['order_by'] = order_by
    
    # Get jobs from database
    jobs = list_jobs(**kwargs)
    
    # Get unique sources for filter dropdown
    conn = get_db()
    sources = [row[0] for row in conn.execute(
        "SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL ORDER BY source"
    ).fetchall()]
    
    # Get job counts by status
    status_counts = {}
    for row in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall():
        status_counts[row[0]] = row[1]
    
    return render_template(
        'index.html',
        jobs=jobs,
        sources=sources,
        status_filter=status_filter,
        source_filter=source_filter,
        min_score=min_score,
        order_by=order_by,
        status_counts=status_counts,
    )


@app.route('/job/<int:job_id>')
def job_detail(job_id):
    """Job detail page."""
    job = get_job(job_id)
    if not job:
        return "Job not found", 404
    
    return render_template('job_detail.html', job=job)


@app.route('/job/<int:job_id>/status', methods=['POST'])
def update_job_status(job_id):
    """Update job status via AJAX."""
    new_status = request.form.get('status')
    if not new_status:
        return jsonify({'error': 'Status required'}), 400
    
    job = update_status(job_id, new_status)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({'status': job.status})


@app.route('/job/<int:job_id>/score', methods=['POST'])
def update_job_score(job_id):
    """Update job score via AJAX."""
    try:
        score = float(request.form.get('score'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid score'}), 400
    
    rationale = request.form.get('rationale', '')
    
    job = update_score(job_id, score, rationale)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({'score': job.score, 'rationale': job.score_rationale})


@app.route('/profile')
def profile():
    """Profile page showing user information."""
    profile_meta = get_all_meta()
    job_history = list_job_history()
    skills = list_skills()
    
    return render_template(
        'profile.html',
        profile=profile_meta,
        job_history=job_history,
        skills=skills,
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
