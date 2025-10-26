import datetime
import calendar
import config
import os
import yaml
from flask import Flask, render_template, jsonify, redirect, url_for, request, session, flash
from apscheduler.schedulers.background import BackgroundScheduler

import holter
import move_holters
from data import get_daily_metadata


app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this to a random secret key
scheduler = BackgroundScheduler()

# Load config including users
with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)


@app.before_request
def check_config_access():
    try:
        config.get()
    except Exception as e:
        return render_template("config_error.html", error_message=str(e)), 500


# ------ Authentication operations ------

def require_auth(is_admin=False):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            if is_admin and not session.get('is_admin', False):
                return render_template("404.html"), 404
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_user(username):
    for user in CONFIG.get('users', []):
        if user['username'] == username:
            return user
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)
        if user and user['password'] == password:
            session['username'] = username
            session['is_admin'] = user['is_admin']
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------ Statistics ------

class Cell:
    def __init__(self, value, link=None):
        self.value = value
        self.link = link

    def __str__(self):
        return str(self.value)


@app.route("/<int:year>/<int:month>/")
@require_auth(is_admin=False)
def monthly_stats(year, month):
    # Daily stats for given month and year
    daily_metadata = get_daily_metadata(year=year, month=month)

    # Initialize dates as all possible days (integers) of the current month
    num_days = calendar.monthrange(year, month)[1]
    headers = ["Doctor \\ Date"] + list(range(1, num_days + 1)) + ["Total"]

    data = []
    summary_row = ["Daily total"] + [0] * num_days
    for doctor, doctor_metadata in daily_metadata.items():
        row = [doctor]
        row_count = 0
        for day in range(1, num_days + 1):
            date_ = datetime.date(year, month, day)
            count = doctor_metadata.get(date_, 0)
            row_count += count
            link = url_for('daily_doctor_stats', year=year, month=month, day=day, doctor=doctor)
            row.append(Cell(count, link=link))
            summary_row[day] += count
        row.append(row_count)
        data.append(row)
    summary_row = summary_row[:1] + [
        Cell(value, link=url_for('daily_stats', year=year, month=month, day=day))
        for day, value in zip(range(1, num_days + 1), summary_row[1:])
    ]
    summary_row.append(sum([cell.value for cell in summary_row[1:]]))
    data.append(summary_row)

    previous_year = year - 1 if month == 1 else year
    previous_month = 12 if month == 1 else month - 1
    previous_month_link = url_for('monthly_stats', year=previous_year, month=previous_month)

    next_year = year + 1 if month == 12 else year
    next_month = 1 if month == 12 else month + 1
    next_month_link = url_for('monthly_stats', year=next_year, month=next_month)

    return render_template(
        "stats.html",
        name=f"Stats for {month:02d}/{year}",
        headers=headers,
        data=data,
        previous_month_link=previous_month_link,
        next_month_link=next_month_link,
    )


def _get_daily_data(year, month, day, doctor):
    path = os.path.join(
        config.get()["output_path"], doctor, '{:02d}.{:02d}.{}'.format(day, month, year)
    )
    data = []
    if os.path.exists(path):
        file_names = holter.get_in_folder(path)
        for file_name in file_names:
            patient_data = holter.get_patient_data(file_name)
            row = [
                os.path.basename(file_name),
                patient_data['name'],
            ]
            data.append(row)
    return data


@app.route("/<int:year>/<int:month>/<int:day>/<string:doctor>/")
@require_auth(is_admin=False)
def daily_doctor_stats(year, month, day, doctor):
    data = _get_daily_data(year, month, day, doctor)
    headers = ["File Name", "Name"]
    name = f"Stats for {doctor} on {day:02d}.{month:02d}.{year}"
    return render_template(
        "daily_stats.html",
        name=name,
        headers=headers,
        data=data,
    )

@app.route("/<int:year>/<int:month>/<int:day>/")
@require_auth(is_admin=False)
def daily_stats(year, month, day):
    doctors = get_daily_metadata(year=year, month=month).keys()
    data = []
    for doctor in doctors:
        doctor_data = _get_daily_data(year, month, day, doctor)
        doctor_data = [[doctor] + row for row in doctor_data]
        data += doctor_data
    headers = ["Doctor", "File Name", "Name"]
    name = f"Stats for {day:02d}.{month:02d}.{year}"
    return render_template(
        "daily_stats.html",
        name=name,
        headers=headers,
        data=data,
    )


@app.route("/stats/")
@require_auth(is_admin=False)
def stats():
    now = datetime.datetime.now()
    return redirect(url_for('monthly_stats', year=now.year, month=now.month))

# ------ Config ------

@require_auth(is_admin=False)
def edit_config():
    return render_template("edit_config.html", config=config.get())

@app.route("/")
@require_auth(is_admin=False)
def home():
    return render_template("config.html", config=config.get(), is_admin=session['is_admin'])


def _distribute_holters_task():
    move_holters.distribute_holters()


def _start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            func=_distribute_holters_task,
            trigger="interval",
            seconds=5,
            id="distribute-holters-task",
            replace_existing=True,
        )
        scheduler.start()
        print("Scheduler started.")


@app.route("/scheduler/start", methods=["POST"])
@require_auth(is_admin=True)
def scheduler_start():
    if not scheduler.get_job("distribute-holters-task"):
        scheduler.add_job(
            func=_distribute_holters_task,
            trigger="interval",
            seconds=5,
            id="distribute-holters-task",
            replace_existing=True,
        )
        print("Scheduler job added.")
    return jsonify({"status": "Job is running ✅"})


@app.route("/scheduler/stop", methods=["POST"])
@require_auth(is_admin=True)
def scheduler_stop():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        scheduler.remove_job("distribute-holters-task")
        print("Scheduler job removed.")
    return jsonify({"status": "Job is not running ❌"})


@app.route("/scheduler/status", methods=["GET"])
@require_auth(is_admin=True)
def scheduler_status():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        return jsonify({"status": "Job is running ✅"})
    else:
        return jsonify({"status": "Job is not running ❌"})


# ------ Error Handlers ------

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors with custom template showing ASCII doctor."""
    return render_template('404.html'), 404


if __name__ == "__main__":
    _start_scheduler()
    app.run(debug=True)  # PAVEL-TODO: remove debug=True for production
