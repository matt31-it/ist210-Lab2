# IST 210 Lab 2: Azure SQL Relational Database CRUD Web Application

A production-ready, secure web application bridging relational database architecture (Azure SQL Database) with modern software engineering. Built for Penn State University **IST 210 (Organization of Data) &mdash; Lab 2**.

---

## 🎯 Lab 2 Core Objectives & Traceability Matrix

| Core Objective | Implementation in this Application | File Reference |
| :--- | :--- | :--- |
| **Cloud Database Integration** | Connects to Azure SQL Database (ist210.database.windows.net, db: ist-210-work) via Microsoft ODBC Driver 18 for SQL Server with credentials loaded securely from .env. | db.py, .env |
| **AI-Assisted Scaffolding** | Full-stack scaffolding including routes, dynamic Jinja2 views, responsive Bootstrap 5 UI, and database interaction logic. | pp.py, 	emplates/ |
| **Security by Design** | Strict parameterized SQL queries (cursor.execute(sql, (param1, param2))) eliminating all SQL injection attack vectors. | pp.py, db.py |
| **Referential Integrity** | Validates parent-child foreign keys on insert/update and handles ON DELETE NO ACTION foreign key constraint violations (Error 547) safely with user alerts. | pp.py, 	emplates/students.html, 	emplates/courses.html |

---

## 🗄️ Relational Schema & Entity Relationships

The application operates against the Azure SQL schema created in Lab 1 (Microsoft Learn module):

- **Person**: Base table for individuals (PersonId, FirstName, MiddleInitial, LastName, DateOfBirth).
- **Student**: Child table referencing Person via PersonId (StudentId, PersonId, Email).
- **Course**: Master table for academic course catalog (CourseId, Name, Teacher).
- **Credit**: Primary operational junction table mapping students to courses with academic grades and attempts (StudentId, CourseId, Grade, Attempt).
- **Verification**: Cross-lab audit table (FullName, CourseCode, TimeStamp).

### Referential Action Rules:
- Foreign keys FK_Credit_Student and FK_Credit_Course are defined with default ON DELETE NO ACTION.
- Deleting an operational Credit row succeeds safely (leaf record).
- Attempting to delete a Student or Course with existing dependent Credit records triggers a Foreign Key constraint violation. The application intercepts this violation and presents an educational explanation rather than an unhandled 500 error.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.13 tested)
- Microsoft ODBC Driver 18 for SQL Server
- Azure SQL Database instance (ist210.database.windows.net)

### 2. Configure Environment Variables
Copy .env.example to .env (already created in the project):
`ash
cp .env.example .env
`
Open .env and set your Azure SQL database password:
`env
DB_SERVER=ist210.database.windows.net
DB_DATABASE=ist-210-work
DB_USER=CloudSA3b984a23
DB_PASSWORD=YourAzureSqlPasswordHere
DB_DRIVER={ODBC Driver 18 for SQL Server}
DB_TRUST_SERVER_CERTIFICATE=yes
SECRET_KEY=ist210-super-secret-key-2026
`

> **Azure Firewall Reminder**: In the Azure Portal, navigate to your SQL Server (ist210) > **Networking** > **Firewall rules** and ensure **\"Add your client IPv4 address\"** is checked and saved.

### 3. Install Dependencies
`powershell
pip install -r requirements.txt
`

### 4. (Optional) Seed Sample Academic Records
If your database is newly initialized and you wish to populate sample courses, students, and credit records:
`powershell
python seed_data.py
`

### 5. Launch the Web Application
`powershell
python app.py
`
Open your browser to: **[http://localhost:5000](http://localhost:5000)**

---

## 📋 CRUD Operations & Live Demonstration Guide

Use this walkthrough to record your screen or take screenshots for the Lab 2 submission:

### 1. Read (Multi-Table JOIN Dashboard)
- Navigate to http://localhost:5000/.
- **Demonstration**: Show the main table displaying student names, PSU emails, course titles, instructors, attempts, and color-coded grades.
- **SQL Behind the Scene**: Executes an INNER JOIN across Credit, Student, Person, and Course.

### 2. Create (Operational Record Insertion)
- Click **\"New Enrollment\"** in the top navigation or on the dashboard.
- Select a student from the dropdown (foreign key StudentId).
- Select a course from the dropdown (foreign key CourseId).
- Enter a Grade (e.g. 94.50) and Attempt number (1).
- Click **\"Create Record\"**.
- **Demonstration**: Show the new record appearing at the top of the dashboard.

### 3. Update (Parameter Modification)
- Locate an enrollment record on the dashboard and click the **\"Edit\"** button.
- Modify the **Grade** (e.g., change from 85.00 to 92.00).
- Click **\"Save Changes\"**.
- **Demonstration**: Confirm the success alert and the updated grade on the dashboard.

### 4. Delete & Referential Integrity (Safe vs. Blocked Removal)
- **Safe Delete (Operational Record)**:
  - On the dashboard, click the trash icon next to an enrollment. Confirm the modal.
  - The record is safely removed because Credit has no child dependencies.
- **Referential Integrity Enforcement (ON DELETE NO ACTION)**:
  - Navigate to **Students** (/students) or **Courses** (/courses).
  - Attempt to delete a student or course that has active enrollment records in Credit.
  - Confirm the modal attempt.
  - **Demonstration**: Show the red alert banner:
    > [REFERENTIAL INTEGRITY ENFORCED]: Cannot delete Student ID X! Foreign key constraint violation (ON DELETE NO ACTION). Active records exist in the Credit table that depend on this student.

### 5. Lab 1 Cross-Verification
- Navigate to **Lab 1 Verification** (/verification).
- Review the historical verification records from Lab 1 (dbo.Verification).
- Click **\"Write Verification Ping\"** to insert a fresh verification entry live into Azure SQL.
