# Student Result Manager

Course project for **Advance Python and Cybersecurity with Freelancing**.

The Flask web app lets an admin enter and correct marks, search by ID, and
view class performance. Students sign in to see their own results. The
terminal menu covers the original assignment workflow and shares the
same Python classes and SQLite database. Each subject is out of 100, and
a student must score at least 33 in every subject to pass.

|Technology|Role in this project|
|-|-|
|Python|Validates marks and calculates totals, grades, and reports|
|Flask|Handles web routes, forms, and sign-in|
|SQL (SQLite)|Saves, searches, and updates results and correction history|
|HTML and Jinja|Render pages and display results|
|CSS|Styles the pages using `static/student\_results\_style.css`|

## How results are calculated

Five subjects are worth 100 marks each. Total is the sum of the five
marks. Average is total divided by five. Percentage is total divided by
500, multiplied by 100. Here the average and percentage have the same
numeric value because every subject is out of 100.

|Condition|Grade|
|-|-|
|Any subject below 33|F|
|All subjects passed and percentage is 80–100|A+|
|All subjects passed and percentage is at least 70 and below 80|A|
|All subjects passed and percentage is at least 60 and below 70|A-|
|All subjects passed and percentage is at least 50 and below 60|B|
|All subjects passed and percentage is at least 40 and below 50|C|
|All subjects passed and percentage is below 40|D|

## Set up in VS Code on Windows

Use Python 3.11 or later. Extract the ZIP and open the folder containing
`student\_result\_manager\_app.py` in VS Code. In the PowerShell terminal run:

```powershell
py -m venv project\_venv
.\\project\_venv\\Scripts\\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\\project\_venv\\Scripts\\python.exe -c "import secrets; print(secrets.token\_hex(32))"
```

If you already created a virtual environment, reuse it and rerun the install
command to add python-dotenv. If you already created .env, edit it in place.

Paste the printed key after `SECRET\_KEY=` in .env. Set `ADMIN\_USERNAME` and
`ADMIN\_PASSWORD` in that file. Use a unique admin password of 12–128
characters and a username of up to 64 characters without spaces. Quote the
password if it contains spaces or a #. The application reads the .env beside
the Python file. Shell environment values with the same names take precedence.

```powershell
.\\project\_venv\\Scripts\\python.exe student\_result\_manager\_app.py
```

Open http://127.0.0.1:5000/. Stop with Ctrl+C. The project is designed for
a local classroom demo. On macOS or Linux, use `python3 -m venv project\_venv`,
`project\_venv/bin/python` in the Python commands, and `cp .env.example .env`.

## Run the terminal menu

After setting up the same environment and .env, run:

```powershell
.\\project\_venv\\Scripts\\python.exe student\_result\_manager\_cli.py
```

Sign in with the admin credentials from .env. The menu repeats until you
choose Exit. It supports adding a student, searching by ID, showing the
highest and lowest totals including ties, and displaying the class summary.
Use the Flask interface to correct marks and view correction history.

## Storage and code organization

* `Student` validates marks and calculates the total, average, percentage,
grade, and pass status.
* `ResultManager` uses SQLite to save and retrieve students, compute class
summaries, and maintain correction history.
* Flask reuses a SQLite connection through `g` during a request and closes
it at teardown. The terminal opens and closes its own connection for
each database operation.
* `student\_result\_manager\_cli.py` uses a loop, functions, and conditions to
run the terminal menu. The Flask routes and templates handle the web interface.
* `students.db` is the primary storage and is read when the program restarts.
After a successful addition in either interface, or a mark correction in Flask,
the app writes the current roster to `students.csv`. The CSV remains on disk
when the program closes.

For the local demo, close one interface before writing records in the other.

## Try both accounts

1. Open **Admin login** and enter your .env username and password.
2. Open **Add a student**. Enter a fictional student ID and name, five marks,
and a student username and password of 12–128 characters. The result and
account save in one SQLite transaction, then the app updates students.csv.
3. Use **Search by ID** for any result and **Class performance** for class
counts, pass rate, average, and score extremes.
4. Log out. Open **Student login** and sign in with the student's credentials.
On **My result**, enter the ID assigned to that account and select
**Show result**. Entering any other ID displays the same error whether
the ID exists or is missing.

|Route|Access|
|-|-|
|/|Public entry page|
|/admin/login|Admin sign-in|
|/admin|Admin class performance|
|/admin/students/add|Admin only, add a student, marks, and login|
|/admin/students/search|Admin only, search any result by ID|
|/admin/students/correct-mark|Admin only, correct one mark and view its history|
|/admin/students/account|Admin only, create a login for a saved student|
|/student/login|Student sign-in|
|/student/result|Student only, search for own result by ID|
|/student/change-password|Student only, change own password|
|/logout|POST to end the session|

## Correct a mark

As admin, open **Search by ID**, find the student, and select **Correct a mark or
view correction history**. Choose the subject, enter the revised whole-number
mark (0–100), and save. SQLite saves the revision and its history entry in one
transaction. The history shows the subject, previous mark, revised mark, admin
username, and time in UTC. The app rebuilds the CSV from the current marks.
The student result and class report use the revised mark immediately.

If a CSV write fails, the page reports that the SQLite correction was saved.
After fixing the file access issue, submit the same mark again to refresh the
CSV without adding another history entry.

When upgrading, stop Flask, extract the ZIP to a new folder, and copy your
existing .env and students.db into it. SQLite creates the history table on
startup. Copy the existing students.csv too if you want to retain it until the
next successful save.

## Change your student password

From **My result**, choose **Change password**. Enter the current password,
a different new password of 12–128 characters, and the new password again.
After saving, sign in with the new password. Other sessions for that student
also expire. Existing student accounts work with the same database and .env.
Students signed in before this update will need to sign in again.

## Existing data and GitHub

To reuse records, stop the app and copy the previous SQLite version's
`students.db` beside the new Python file before startup. The new
`student\_accounts` table is created automatically. As admin, search for an
existing student and choose **Create login**. The next successful addition
rewrites students.csv with all saved records. Student usernames and password
hashes are excluded from that CSV. The project uses one local Flask process.

Commit `.env.example`, `requirements.txt`, and the source files. Keep the
real `.env`, SQLite database, and CSV private. The included .gitignore
excludes them. Werkzeug comes with Flask. The app uses it for password hashing.

### GitHub submission

1. Put this project folder inside the repository, keeping its files and
subfolders together. Include the README and screenshots.
2. Check the files listed for commit. Confirm that `.env`, the database, CSV,
and virtual environment are excluded.
3. Push the project to your GitHub repository. Open the project folder on
GitHub and check that the README and screenshot links render. Submit the
repository link to your mentor.

## Demonstration for evaluation

1. In the Flask admin view, add fictional student **001** with marks
**90, 85, 95, 80, 100** and student **002** with five marks of **80**.
2. Search for **001**. The total is **450/500**, the grade is **A+**, and
the status is **Pass**. Try entering **101** as a corrected mark to
show the validation.
3. Correct **001**’s Bangla mark from **90 to 30**. The total becomes
**390/500** and the grade becomes **F** because Bangla is below 33.
The history shows **90 → 30**. In Class performance, **002** has the
highest total, the class average is **79.00%**, and the pass rate is
**50.00%**.
4. Sign out and sign in as student **001**. Search for **002** to see the
access error, then search for **001** to show the revised result.
5. Open `students.csv` in VS Code and show the revised Bangla mark. Stop
Flask, run the terminal menu, and search for **001** to demonstrate that
the record was saved and both interfaces use it.

## Manual testing checklist

Use fictional records in a fresh demo database. The demonstration above
provides the marks for students `001` and `002`.

|Check|What to try|Expected result|
|-|-|-|
|Valid entry|Add `001` and search for it|Total 255/500, grade B, and Pass appear above the subject marks|
|Duplicate ID|Try adding `001` again with a different login username|An error appears and the original result stays unchanged|
|Invalid mark|Enter `101` on the correction form|The form rejects the mark and the saved result stays unchanged|
|Role restriction|Sign in as student `001`, open `/admin`, and try `002` in **My result**|Admin access is denied. Searching for `002` reveals no result. Searching for `001` shows the student's own result|
|Mark correction|As admin, change `001`'s Bangla mark from 30 to 32, then to 35|The result shows 255/500, Fail replacing by Pass and Percentage and Average changes too.|
|Persistence|Stop Flask, restart it, and search for `001`|SQLite reloads the revised result and `students.csv` still exists|

## 

Notes: 



* `Student` represents one student. Its methods calculate the result from
the five marks whenever the result is displayed.
* `ResultManager` uses SQL to add and search records. When adding a student,
the result and login are saved together in one transaction.
* `run\_menu()` uses a loop to keep prompting for the next action. Flask uses
separate routes and HTML templates to handle web actions.
* `require\_role()` uses `wraps` to protect routes while preserving the
original view function's name. The student search compares the entered ID
with the ID in the signed session before reading a result.
* `Path(\_\_file\_\_).resolve().parent` locates the project folder even when the
program starts from another folder. A context processor makes the form
token available to templates, and the server checks it on each POST.

## Screenshots

Screenshots from a local run with fictional student records



1.Viewing Homepage (by Admin access)



2.Add a student (by Admin access)



3.Viewing Class performance (by Admin access)



4.Viewing Correction history (by Admin access)



5\. Viewing only self result (by Student access)



