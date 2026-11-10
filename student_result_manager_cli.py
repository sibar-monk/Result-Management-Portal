"""Run the Student Result Manager from a terminal."""
import csv
import os
import sqlite3
from getpass import getpass
from secrets import compare_digest

from dotenv import load_dotenv

from student_result_manager_app import (
    MAX_MARK, PROJECT_DIR, SUBJECTS, ResultManager, Student, validate_credentials,
)


def add_student(manager):
    student_id = input("Student ID: ")
    name = input("Student name: ")
    marks = []
    for subject in SUBJECTS:
        while True:
            try:
                mark = int(input(f"{subject} (0-{MAX_MARK}): "))
            except ValueError:
                print("Enter a whole number.")
                continue
            if 0 <= mark <= MAX_MARK:
                marks.append(mark)
                break
            print(f"Enter a mark from 0 to {MAX_MARK}.")

    student = Student(student_id, name, marks)
    username = input("Student login username: ").strip()
    password = getpass("Student login password (12-128 characters): ")
    validate_credentials(username, password)
    try:
        manager.add_student(student, username, password)
    except sqlite3.IntegrityError:
        print("That student ID or username is already in use.")
        return

    try:
        manager.save_csv()
    except (OSError, sqlite3.Error, csv.Error):
        print("Student saved in SQLite, but students.csv could not be updated.")
    else:
        print("Student saved and students.csv updated.")


def show_result(manager):
    student = manager.find_student(input("Student ID: "))
    if student is None:
        print("Student ID not found.")
        return
    print(f"\n{student.name} ({student.student_id})")
    for subject, mark in zip(SUBJECTS, student.marks):
        print(f"{subject}: {mark}/{MAX_MARK}")
    print(f"Total: {student.total()}/{len(SUBJECTS) * MAX_MARK}")
    print(f"Average: {student.average():.2f}/{MAX_MARK}")
    print(f"Percentage: {student.percentage():.2f}%")
    print(f"Grade: {student.grade()}")
    print("Status:", "Pass" if student.passed() else "Fail")


def show_extremes(manager):
    highest, lowest = manager.score_extremes(manager.list_students())
    if not highest:
        print("No students have been added yet.")
        return
    for label, group in (("Highest", highest), ("Lowest", lowest)):
        print(f"{label} total: {group[0].total()}/{len(SUBJECTS) * MAX_MARK}")
        for student in group:
            print(f"  {student.name} ({student.student_id})")


def show_summary(manager):
    summary = manager.class_summary(manager.list_students())
    if summary is None:
        print("No students have been added yet.")
        return
    print(f"Students: {summary['count']}")
    print(f"Passed: {summary['passed']} | Failed: {summary['failed']}")
    print(f"Pass rate: {summary['pass_rate']:.2f}%")
    print(f"Class average: {summary['average_percentage']:.2f}%")


def run_menu(manager):
    while True:
        print("\n=== Student Result Manager ===")
        print("1. Add student\n2. Search by ID\n3. Highest and lowest scores")
        print("4. Class performance\n5. Exit")
        choice = input("Choose an option: ").strip()
        try:
            if choice == "1":
                add_student(manager)
            elif choice == "2":
                show_result(manager)
            elif choice == "3":
                show_extremes(manager)
            elif choice == "4":
                show_summary(manager)
            elif choice == "5":
                return
            else:
                print("Choose a number from 1 to 5.")
        except (ValueError, sqlite3.Error) as error:
            print(f"Could not complete the action: {error}")


def main():
    load_dotenv(PROJECT_DIR / ".env", interpolate=False)
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    try:
        validate_credentials(username, password)
    except ValueError:
        print("Set ADMIN_USERNAME and ADMIN_PASSWORD in .env first. See README.md.")
        return 1

    try:
        entered_user = input("Admin username: ").strip()
        entered_password = getpass("Admin password: ")
        if entered_user != username or not compare_digest(
            entered_password.encode(), password.encode()
        ):
            print("Invalid admin credentials.")
            return 1
        run_menu(ResultManager())
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
    except sqlite3.Error as error:
        print(f"Could not open the student database: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
