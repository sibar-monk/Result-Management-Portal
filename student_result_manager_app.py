"""Local Flask Student Result Manager using SQLite and CSV."""
import csv
import hashlib
import os
import secrets
import sqlite3
from contextlib import closing, contextmanager
from functools import wraps
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, g, has_request_context, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

SUBJECTS = ("Bangla", "English", "Mathematics", "Science", "ICT")
MAX_MARK = 100
PASS_MARK = 33
PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "students.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    bangla INTEGER NOT NULL CHECK (bangla BETWEEN 0 AND 100),
    english INTEGER NOT NULL CHECK (english BETWEEN 0 AND 100),
    mathematics INTEGER NOT NULL CHECK (mathematics BETWEEN 0 AND 100),
    science INTEGER NOT NULL CHECK (science BETWEEN 0 AND 100),
    ict INTEGER NOT NULL CHECK (ict BETWEEN 0 AND 100)
)
"""


class Student:
    """Store and calculate the result for one student."""

    def __init__(self, student_id, name, marks):
        self.student_id = student_id.strip()
        self.name = name.strip()
        self.marks = tuple(marks)
        if not self.student_id or not self.name:
            raise ValueError("Student ID and name are required.")
        if len(self.marks) != len(SUBJECTS) or any(
            type(mark) is not int or not 0 <= mark <= MAX_MARK
            for mark in self.marks
        ):
            raise ValueError("Enter five whole-number marks from 0 to 100.")

    def total(self):
        return sum(self.marks)

    def average(self):
        return self.total() / len(SUBJECTS)

    def percentage(self):
        return self.total() / (len(SUBJECTS) * MAX_MARK) * 100

    def passed(self):
        return all(mark >= PASS_MARK for mark in self.marks)

    def grade(self):
        if not self.passed():
            return "F"
        for minimum, grade in ((80, "A+"), (70, "A"), (60, "A-"),
                               (50, "B"), (40, "C")):
            if self.percentage() >= minimum:
                return grade
        return "D"


class ResultManager:
    """Read and write student records using SQLite and CSV."""

    def __init__(self, db_path=DATA_FILE):
        self.db_path = Path(db_path)
        self.csv_lock = Lock()
        with self.connection() as connection, connection:
            connection.execute(SCHEMA)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS student_accounts (
                    student_id TEXT NOT NULL PRIMARY KEY REFERENCES students(student_id),
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mark_corrections (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT NOT NULL REFERENCES students(student_id),
                    subject TEXT NOT NULL,
                    old_mark INTEGER NOT NULL,
                    new_mark INTEGER NOT NULL,
                    changed_by TEXT NOT NULL,
                    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def open_connection(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def connection(self):
        """Reuse one connection per web request, or close it after a CLI operation."""
        if has_request_context():
            if "results_db" not in g:
                g.results_db = self.open_connection()
            yield g.results_db
        else:
            with closing(self.open_connection()) as connection:
                yield connection

    def add_student(self, student, username, password):
        password_hash = generate_password_hash(password)
        with self.connection() as connection, connection:
            connection.execute(
                """
                INSERT INTO students
                    (student_id, name, bangla, english, mathematics, science, ict)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student.student_id, student.name, *student.marks),
            )
            self.insert_account(connection, student.student_id, username, password_hash)

    def add_account(self, student_id, username, password):
        password_hash = generate_password_hash(password)
        with self.connection() as connection, connection:
            self.insert_account(connection, student_id, username, password_hash)

    @staticmethod
    def insert_account(connection, student_id, username, password_hash):
        connection.execute(
            """
            INSERT INTO student_accounts (student_id, username, password_hash)
            VALUES (?, ?, ?)
            """,
            (student_id, username, password_hash),
        )

    def find_account(self, username):
        with self.connection() as connection:
            return connection.execute(
                "SELECT student_id, password_hash FROM student_accounts WHERE username = ?",
                (username,),
            ).fetchone()

    def student_password_hash(self, student_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT password_hash FROM student_accounts WHERE student_id = ?",
                (student_id,),
            ).fetchone()
        return row[0] if row else None

    def change_student_password(self, student_id, current_password, new_password):
        old_hash = self.student_password_hash(student_id)
        if not old_hash or not check_password_hash(old_hash, current_password):
            raise ValueError("The current password is incorrect.")
        if current_password == new_password:
            raise ValueError("Choose a password different from your current password.")

        new_hash = generate_password_hash(new_password)
        with self.connection() as connection, connection:
            updated = connection.execute(
                """
                UPDATE student_accounts SET password_hash = ?
                WHERE student_id = ? AND password_hash = ?
                """,
                (new_hash, student_id, old_hash),
            ).rowcount
            if updated != 1:
                raise ValueError("The password changed elsewhere. Sign in again.")

    def find_student(self, student_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (student_id.strip(),),
            ).fetchone()
        if row is None:
            return None
        return Student(row[0], row[1], row[2:])

    def correct_mark(self, student_id, subject, new_mark, admin_username):
        if subject not in SUBJECTS:
            raise ValueError("Select one of the five subjects.")
        if type(new_mark) is not int or not 0 <= new_mark <= MAX_MARK:
            raise ValueError("Enter a whole-number mark from 0 to 100.")

        # The column comes from the fixed subject list, not directly from the form.
        column = SUBJECTS[SUBJECTS.index(subject)].lower()
        with self.connection() as connection, connection:
            # Reserve the write before reading the old mark so the history is accurate.
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT {column} FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
            if row is None:
                abort(404)
            old_mark = row[0]
            if old_mark == new_mark:
                return False
            connection.execute(
                f"UPDATE students SET {column} = ? WHERE student_id = ?",
                (new_mark, student_id),
            )
            connection.execute(
                """
                INSERT INTO mark_corrections
                    (student_id, subject, old_mark, new_mark, changed_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, subject, old_mark, new_mark, admin_username),
            )
        return True

    def mark_history(self, student_id):
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.row_factory = sqlite3.Row
            return cursor.execute(
                """
                SELECT subject, old_mark, new_mark, changed_by, changed_at
                FROM mark_corrections
                WHERE student_id = ?
                ORDER BY id DESC
                """,
                (student_id,),
            ).fetchall()

    def list_students(self):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM students ORDER BY student_id"
            ).fetchall()
        return [Student(row[0], row[1], row[2:]) for row in rows]

    def save_csv(self):
        """Write a CSV copy of all records currently saved in SQLite."""
        csv_path = self.db_path.with_suffix(".csv")
        temporary_file = csv_path.with_suffix(".csv.tmp")

        # Keep two requests from writing the same temporary file at once.
        with self.csv_lock:
            students = self.list_students()
            with temporary_file.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Student ID", "Name", *SUBJECTS])
                for student in students:
                    writer.writerow([student.student_id, student.name, *student.marks])
            temporary_file.replace(csv_path)

    @staticmethod
    def score_extremes(students):
        if not students:
            return [], []
        totals = [student.total() for student in students]
        highest, lowest = max(totals), min(totals)
        return (
            [student for student in students if student.total() == highest],
            [student for student in students if student.total() == lowest],
        )

    @staticmethod
    def class_summary(students):
        count = len(students)
        if not count:
            return None
        passed = sum(student.passed() for student in students)
        return {
            "count": count,
            "passed": passed,
            "failed": count - passed,
            "pass_rate": passed / count * 100,
            "average_percentage": sum(
                student.percentage() for student in students
            ) / count,
        }


def read_marks(form):
    marks = []
    for number, subject in enumerate(SUBJECTS):
        try:
            marks.append(int(form.get(f"mark_{number}", "")))
        except ValueError:
            raise ValueError(f"Enter a whole-number mark for {subject}.") from None
    return marks


def read_credentials():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    return username, password


def validate_credentials(username, password):
    if not 1 <= len(username) <= 64 or any(char.isspace() for char in username):
        raise ValueError("Enter a username of up to 64 characters without spaces.")
    if not 12 <= len(password) <= 128:
        raise ValueError("Enter a password of 12 to 128 characters.")


def require_role(role):
    def decorate(view):
        @wraps(view)
        def protected(*args, **kwargs):
            current_role = session.get("role")
            if current_role is None:
                return redirect(url_for(f"{role}_login"))
            if current_role != role:
                abort(403)
            return view(*args, **kwargs)

        return protected

    return decorate


def password_version(password_hash):
    return hashlib.sha256(password_hash.encode()).hexdigest()


def create_app(data_file=DATA_FILE):
    load_dotenv(PROJECT_DIR / ".env", interpolate=False)
    secret_key = os.environ.get("SECRET_KEY", "")
    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if len(secret_key) < 32:
        raise RuntimeError("Set SECRET_KEY in .env using the command in README.md.")
    validate_credentials(admin_username, admin_password)
    admin_hash = generate_password_hash(admin_password)
    dummy_student_hash = generate_password_hash(secrets.token_hex(32))

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    manager = ResultManager(data_file)

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop("results_db", None)
        if connection is not None:
            connection.close()

    @app.before_request
    def expire_old_student_sessions():
        if session.get("role") == "student":
            password_hash = manager.student_password_hash(session["student_id"])
            # A new password changes this fingerprint, expiring old sessions.
            if not password_hash or session.get("password_version") != password_version(password_hash):
                session.clear()
                return redirect(url_for("student_login"), code=303)

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            token = session.get("csrf_token", "")
            submitted = request.form.get("csrf_token", "")
            if not token or not secrets.compare_digest(token.encode(), submitted.encode()):
                abort(400, "Invalid form token. Reload the page and try again.")

    @app.context_processor
    def form_token():
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return {"csrf_token": token}

    @app.after_request
    def prevent_result_caching(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(sqlite3.Error)
    def handle_database_error(error):
        app.logger.error("Database operation failed: %s", error)
        return render_template(
            "message.html", title="Database error",
            message="The database operation could not be completed.",
        ), 500

    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            username, password = read_credentials()
            if check_password_hash(admin_hash, password) and username == admin_username:
                session.clear()
                session["role"] = "admin"
                return redirect(url_for("admin_dashboard"), code=303)
            return render_template("admin_login.html", error=True), 401
        return render_template("admin_login.html")

    @app.route("/student/login", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            username, password = read_credentials()
            account = manager.find_account(username)
            password_hash = account[1] if account else dummy_student_hash
            if check_password_hash(password_hash, password) and account:
                session.clear()
                session["role"] = "student"
                session["student_id"] = account[0]
                session["password_version"] = password_version(password_hash)
                return redirect(url_for("student_result"), code=303)
            return render_template("student_login.html", error=True), 401
        return render_template("student_login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"), code=303)

    @app.get("/admin")
    @require_role("admin")
    def admin_dashboard():
        students = manager.list_students()
        highest, lowest = manager.score_extremes(students)
        return render_template(
            "admin_dashboard.html", summary=manager.class_summary(students),
            highest=highest, lowest=lowest,
        )

    @app.route("/admin/students/add", methods=["GET", "POST"])
    @require_role("admin")
    def admin_add_student():
        error = None
        if request.method == "POST":
            try:
                username, password = read_credentials()
                validate_credentials(username, password)
                student = Student(
                    request.form.get("student_id", ""), request.form.get("name", ""),
                    read_marks(request.form),
                )
                manager.add_student(student, username, password)
            except ValueError as problem:
                error = str(problem)
            except sqlite3.IntegrityError:
                error = "That student ID or username is already in use."
            else:
                try:
                    manager.save_csv()
                except (OSError, sqlite3.Error, csv.Error):
                    app.logger.exception("Could not update the CSV file.")
                    flash("Student and login saved, but the CSV copy could not be updated.")
                else:
                    flash("Student, login, and CSV copy saved.")
                return redirect(url_for("admin_search", student_id=student.student_id),
                                code=303)
        return render_template(
            "admin_add_student.html", subjects=SUBJECTS, error=error, form=request.form,
        ), 400 if error else 200

    @app.get("/admin/students/search")
    @require_role("admin")
    def admin_search():
        student_id = request.args.get("student_id", "").strip()
        student = manager.find_student(student_id) if student_id else None
        return render_template(
            "admin_search.html", student_id=student_id, student=student,
            subjects=SUBJECTS,
            has_account=bool(student and manager.student_password_hash(student.student_id)),
        ), 404 if student_id and student is None else 200

    @app.route("/admin/students/correct-mark", methods=["GET", "POST"])
    @require_role("admin")
    def admin_correct_mark():
        student_id = request.args.get("student_id", "").strip()
        student = manager.find_student(student_id)
        if student is None:
            abort(404)

        error = None
        subject = request.form.get("subject", "")
        if request.method == "POST":
            try:
                try:
                    new_mark = int(request.form.get("new_mark", ""))
                except ValueError:
                    raise ValueError("Enter a whole-number mark from 0 to 100.") from None
                changed = manager.correct_mark(student_id, subject, new_mark, admin_username)
            except ValueError as problem:
                error = str(problem)
            else:
                try:
                    manager.save_csv()
                except (OSError, sqlite3.Error, csv.Error):
                    app.logger.exception("Could not update the CSV file.")
                    if changed:
                        flash("Correction saved in SQLite, but the CSV copy could not be updated.")
                    else:
                        flash("No mark changed. The CSV copy could not be updated.")
                else:
                    if changed:
                        flash("Mark corrected, history saved, and CSV updated.")
                    else:
                        flash("No mark changed. The CSV copy was refreshed.")
                return redirect(url_for("admin_correct_mark", student_id=student_id), code=303)
        return render_template(
            "admin_correct_mark.html", student=student, subjects=SUBJECTS,
            history=manager.mark_history(student_id), error=error, selected=subject,
            new_mark=request.form.get("new_mark", ""),
        ), 400 if error else 200

    @app.post("/admin/students/account")
    @require_role("admin")
    def admin_add_account():
        student_id = request.args.get("student_id", "").strip()
        if manager.find_student(student_id) is None:
            abort(404)
        username, password = read_credentials()
        try:
            validate_credentials(username, password)
            manager.add_account(student_id, username, password)
        except ValueError as problem:
            flash(str(problem))
        except sqlite3.IntegrityError:
            flash("This student already has an account, or that username is in use.")
        else:
            flash("Student login created.")
        return redirect(url_for("admin_search", student_id=student_id), code=303)

    @app.get("/student/result")
    @require_role("student")
    def student_result():
        entered_id = request.args.get("student_id")
        student = None
        error = None
        if entered_id is not None:
            # Only search the ID linked to the signed-in account.
            own_id = session["student_id"]
            if entered_id.strip() == own_id:
                student = manager.find_student(own_id)
            if student is None:
                error = "Enter the student ID linked to your account."
        return render_template(
            "student_result.html", student=student, subjects=SUBJECTS,
            entered_id=entered_id or "", error=error,
        ), 400 if error else 200

    @app.route("/student/change-password", methods=["GET", "POST"])
    @require_role("student")
    def student_change_password():
        error = None
        if request.method == "POST":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirmation = request.form.get("confirm_password", "")
            if not 12 <= len(new) <= 128:
                error = "Enter a new password of 12 to 128 characters."
            elif new != confirmation:
                error = "The new passwords do not match."
            else:
                try:
                    manager.change_student_password(session["student_id"], current, new)
                except ValueError as problem:
                    error = str(problem)
                else:
                    session.clear()
                    flash("Password changed. Log in with your new password.")
                    return redirect(url_for("student_login"), code=303)
        return render_template("student_change_password.html", error=error), 400 if error else 200

    return app


if __name__ == "__main__":
    create_app().run()
