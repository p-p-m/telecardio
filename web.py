import datetime
import calendar
import config
import os
from flask import Flask, render_template, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

import holter
import move_holters
from data import get_daily_metadata


app = Flask(__name__)
scheduler = BackgroundScheduler()


@app.before_request
def check_config_access():
    try:
        config.get()
    except Exception as e:
        return render_template("config_error.html", error_message=str(e)), 500


class Cell:
    def __init__(self, value, link=None):
        self.value = value
        self.link = link

    def __str__(self):
        return str(self.value)


@app.route("/<int:year>/<int:month>/")
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

@app.route("/")
def home():
    now = datetime.datetime.now()
    return redirect(url_for('monthly_stats', year=now.year, month=now.month))


@app.route("/edit-config")
def edit_config():
    return render_template("edit_config.html", config=config.get())


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
    return jsonify({"status": "Job is running"})


@app.route("/scheduler/stop", methods=["POST"])
def scheduler_stop():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        scheduler.remove_job("distribute-holters-task")
        print("Scheduler job removed.")
    return jsonify({"status": "Job is not running"})


@app.route("/scheduler/status", methods=["GET"])
def scheduler_status():
    job = scheduler.get_job("distribute-holters-task")
    if job:
        return jsonify({"status": "Job is running"})
    else:
        return jsonify({"status": "Job is not running"})


if __name__ == "__main__":
    _start_scheduler()
    app.run(debug=False)
