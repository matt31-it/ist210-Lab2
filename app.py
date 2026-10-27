import os
import time
import math
import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from db import get_db_connection, test_connection, execute_query

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'ist210-secure-crud-dev-key')

# Cache DB status for 60 seconds to avoid redundant Azure round-trips on every request
_db_status_cache = {'timestamp': 0, 'data': (False, 'Not tested', {})}

def get_cached_db_status():
    now = time.time()
    if now - _db_status_cache['timestamp'] > 60:
        _db_status_cache['data'] = test_connection()
        _db_status_cache['timestamp'] = now
    return _db_status_cache['data']

@app.context_processor
def inject_db_status():
    """Inject connection status globally into all templates for navbar display."""
    connected, msg, details = get_cached_db_status()
    return {
        'db_connected': connected,
        'db_status_message': msg,
        'db_details': details
    }

# -------------------------------------------------------------
# READ: Multi-table JOIN Dashboard (with Fast Pagination)
# -------------------------------------------------------------
@app.route('/')
def dashboard():
    """
    Main dashboard displaying operational Credit records joined with
    Student, Person, and Course tables (multi-table SQL JOIN).
    """
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 25
    if page < 1:
        page = 1
    offset = (page - 1) * per_page
    
    # Base multi-table SQL JOIN
    base_sql = """
        SELECT 
            c.StudentId,
            c.CourseId,
            c.Grade,
            c.Attempt,
            p.FirstName,
            p.MiddleInitial,
            p.LastName,
            s.Email,
            co.Name AS CourseName,
            co.Teacher
        FROM Credit c
        INNER JOIN Student s ON c.StudentId = s.StudentId
        INNER JOIN Person p ON s.PersonId = p.PersonId
        INNER JOIN Course co ON c.CourseId = co.CourseId
    """
    
    count_sql = """
        SELECT COUNT(*) AS total
        FROM Credit c
        INNER JOIN Student s ON c.StudentId = s.StudentId
        INNER JOIN Person p ON s.PersonId = p.PersonId
        INNER JOIN Course co ON c.CourseId = co.CourseId
    """
    
    params = []
    count_params = []
    if search_query:
        filter_clause = """
            WHERE p.FirstName LIKE ? 
               OR p.LastName LIKE ? 
               OR co.Name LIKE ? 
               OR s.Email LIKE ?
        """
        base_sql += filter_clause
        count_sql += filter_clause
        like_term = f"%{search_query}%"
        params = [like_term, like_term, like_term, like_term]
        count_params = [like_term, like_term, like_term, like_term]
        
    base_sql += " ORDER BY co.Name, p.LastName, p.FirstName, c.Attempt OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    params.extend([offset, per_page])
    
    try:
        # Fast paginated query
        credits = execute_query(base_sql, params=params, fetch='all')
        total_records_row = execute_query(count_sql, params=count_params, fetch='one')
        total_records = total_records_row['total'] if total_records_row else len(credits)
        total_pages = max(1, math.ceil(total_records / per_page))
        
        # Summary statistics
        student_stat = execute_query('SELECT COUNT(*) AS c FROM Student', fetch='one')
        course_stat = execute_query('SELECT COUNT(*) AS c FROM Course', fetch='one')
        avg_stat = execute_query('SELECT ROUND(AVG(CAST(Grade AS FLOAT)), 2) AS avg_g FROM Credit', fetch='one')
        
        stats = {
            'total_credits': total_records,
            'avg_grade': avg_stat['avg_g'] if avg_stat and avg_stat['avg_g'] is not None else 0.0,
            'students_count': student_stat['c'] if student_stat else 0,
            'courses_count': course_stat['c'] if course_stat else 0
        }
    except Exception as e:
        flash(f'Database query status: {str(e)}', 'warning')
        credits = []
        total_records = 0
        total_pages = 1
        stats = {'total_credits': 0, 'avg_grade': 0.0, 'students_count': 0, 'courses_count': 0}
        
    return render_template(
        'index.html', 
        credits=credits, 
        stats=stats, 
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        total_records=total_records
    )

# -------------------------------------------------------------
# CREATE: Operational Record (Credit / Enrollment)
# -------------------------------------------------------------
@app.route('/enroll/new', methods=['GET', 'POST'])
def enroll_create():
    """Form interface to insert a new Credit enrollment record."""
    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        course_id = request.form.get('course_id', type=int)
        grade = request.form.get('grade', type=float)
        attempt = request.form.get('attempt', type=int, default=1)
        
        if not student_id or not course_id or grade is None or attempt is None:
            flash('All fields are required.', 'warning')
            return redirect(url_for('enroll_create'))
            
        if grade < 0 or grade > 100:
            flash('Grade must be between 0.00 and 100.00 according to CHECK constraint.', 'warning')
            return redirect(url_for('enroll_create'))
            
        if attempt < 1:
            flash('Attempt must be at least 1.', 'warning')
            return redirect(url_for('enroll_create'))
            
        try:
            sql = """
                INSERT INTO Credit (StudentId, CourseId, Grade, Attempt)
                VALUES (?, ?, ?, ?)
            """
            execute_query(sql, (student_id, course_id, grade, attempt), fetch='commit')
            flash('Enrollment record created successfully!', 'success')
            return redirect(url_for('dashboard'))
        except pyodbc.IntegrityError as e:
            err_msg = str(e)
            if 'UQ_studentgrades' in err_msg or '2627' in err_msg or '2601' in err_msg:
                flash('Constraint Error: An identical record with this student, course, grade, and attempt already exists (UQ_studentgrades).', 'danger')
            elif '547' in err_msg:
                flash('Referential Integrity Error: Invalid StudentId or CourseId. The referenced master record does not exist.', 'danger')
            else:
                flash(f'Referential Integrity / Database Constraint Error: {err_msg}', 'danger')
        except Exception as e:
            flash(f'Error creating record: {str(e)}', 'danger')
            
    # Load master records for dropdowns
    students = []
    courses = []
    try:
        students = execute_query("""
            SELECT TOP 100 s.StudentId, p.FirstName, p.LastName, s.Email 
            FROM Student s 
            INNER JOIN Person p ON s.PersonId = p.PersonId 
            ORDER BY p.LastName, p.FirstName
        """, fetch='all')
        
        courses = execute_query("""
            SELECT CourseId, Name, Teacher 
            FROM Course 
            ORDER BY Name
        """, fetch='all')
    except Exception as e:
        flash(f'Unable to load master lists: {str(e)}', 'warning')
    
    return render_template('enroll_form.html', students=students, courses=courses, is_edit=False)

# -------------------------------------------------------------
# UPDATE: Operational Record (Credit / Enrollment)
# -------------------------------------------------------------
@app.route('/enroll/edit/<int:student_id>/<int:course_id>/<int:attempt>', methods=['GET', 'POST'])
def enroll_edit(student_id, course_id, attempt):
    """Edit interface modifying operational parameters for existing Credit records."""
    current_grade_param = request.args.get('grade', type=float)
    
    if request.method == 'POST':
        new_grade = request.form.get('grade', type=float)
        new_attempt = request.form.get('attempt', type=int)
        orig_grade = request.form.get('orig_grade', type=float)
        
        if new_grade is None or new_attempt is None:
            flash('Grade and Attempt values are required.', 'warning')
            return redirect(request.url)
            
        if new_grade < 0 or new_grade > 100:
            flash('Grade must be between 0.00 and 100.00.', 'warning')
            return redirect(request.url)
            
        if new_attempt < 1:
            flash('Attempt must be at least 1.', 'warning')
            return redirect(request.url)
            
        try:
            sql = """
                UPDATE Credit 
                SET Grade = ?, Attempt = ?
                WHERE StudentId = ? AND CourseId = ? AND Attempt = ? AND Grade = ?
            """
            rows_updated = execute_query(sql, (new_grade, new_attempt, student_id, course_id, attempt, orig_grade), fetch='commit')
            
            if rows_updated > 0:
                flash('Enrollment record updated successfully!', 'success')
            else:
                flash('Record could not be found or was not modified.', 'warning')
            return redirect(url_for('dashboard'))
        except pyodbc.IntegrityError as e:
            flash(f'Constraint Error: {str(e)}', 'danger')
        except Exception as e:
            flash(f'Update Error: {str(e)}', 'danger')
            
    sql = """
        SELECT c.StudentId, c.CourseId, c.Grade, c.Attempt,
               p.FirstName, p.LastName, s.Email,
               co.Name AS CourseName, co.Teacher
        FROM Credit c
        INNER JOIN Student s ON c.StudentId = s.StudentId
        INNER JOIN Person p ON s.PersonId = p.PersonId
        INNER JOIN Course co ON c.CourseId = co.CourseId
        WHERE c.StudentId = ? AND c.CourseId = ? AND c.Attempt = ?
    """
    params = [student_id, course_id, attempt]
    if current_grade_param is not None:
        sql += " AND c.Grade = ?"
        params.append(current_grade_param)
        
    record = execute_query(sql, params, fetch='one')
    if not record:
        flash('Enrollment record not found.', 'danger')
        return redirect(url_for('dashboard'))
        
    return render_template('enroll_form.html', record=record, is_edit=True)

# -------------------------------------------------------------
# DELETE: Operational Record (Credit / Enrollment)
# -------------------------------------------------------------
@app.route('/enroll/delete/<int:student_id>/<int:course_id>/<int:attempt>', methods=['POST'])
def enroll_delete(student_id, course_id, attempt):
    """Safe removal of an operational Credit record."""
    grade = request.form.get('grade', type=float)
    try:
        sql = """
            DELETE FROM Credit 
            WHERE StudentId = ? AND CourseId = ? AND Attempt = ? AND Grade = ?
        """
        rows = execute_query(sql, (student_id, course_id, attempt, grade), fetch='commit')
        if rows > 0:
            flash('Enrollment record removed successfully.', 'info')
        else:
            flash('No matching record found to delete.', 'warning')
    except Exception as e:
        flash(f'Error deleting record: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))

# -------------------------------------------------------------
# STUDENTS: Master Table View & Foreign Key Demonstration
# -------------------------------------------------------------
@app.route('/students')
def students_list():
    """Display all students with joined Person attributes and enrollment counts."""
    sql = """
        SELECT TOP 100
            s.StudentId, 
            s.Email, 
            p.PersonId, 
            p.FirstName, 
            p.MiddleInitial, 
            p.LastName, 
            p.DateOfBirth,
            COUNT(c.CourseId) AS EnrollmentCount
        FROM Student s
        INNER JOIN Person p ON s.PersonId = p.PersonId
        LEFT JOIN Credit c ON s.StudentId = c.StudentId
        GROUP BY s.StudentId, s.Email, p.PersonId, p.FirstName, p.MiddleInitial, p.LastName, p.DateOfBirth
        ORDER BY p.LastName, p.FirstName
    """
    students = []
    try:
        students = execute_query(sql, fetch='all')
    except Exception as e:
        flash(f'Error fetching students: {str(e)}', 'warning')
        
    return render_template('students.html', students=students)

@app.route('/students/new', methods=['GET', 'POST'])
def student_create():
    """Create Person and Student records together in a single operation."""
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        middle_initial = request.form.get('middle_initial', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob = request.form.get('dob', '').strip()
        email = request.form.get('email', '').strip()
        
        if not first_name or not last_name or not dob or not email:
            flash('First name, last name, date of birth, and email are required.', 'warning')
            return redirect(url_for('student_create'))
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth)
                VALUES (?, ?, ?, ?)
            """, (first_name, middle_initial if middle_initial else None, last_name, dob))
            
            cursor.execute("SELECT SCOPE_IDENTITY()")
            person_id = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO Student (PersonId, Email)
                VALUES (?, ?)
            """, (person_id, email))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash(f'Student {first_name} {last_name} created successfully!', 'success')
            return redirect(url_for('students_list'))
        except Exception as e:
            flash(f'Error creating student: {str(e)}', 'danger')
            
    return render_template('student_form.html', is_edit=False)

@app.route('/students/delete/<int:student_id>', methods=['POST'])
def student_delete(student_id):
    """
    REFERENTIAL INTEGRITY ENFORCEMENT:
    Demonstrates parent-child constraint enforcement (ON DELETE NO ACTION).
    """
    try:
        row = execute_query("SELECT PersonId FROM Student WHERE StudentId = ?", (student_id,), fetch='one')
        if not row:
            flash('Student not found.', 'warning')
            return redirect(url_for('students_list'))
            
        person_id = row['PersonId']
        
        execute_query("DELETE FROM Student WHERE StudentId = ?", (student_id,), fetch='commit')
        execute_query("DELETE FROM Person WHERE PersonId = ?", (person_id,), fetch='commit')
        
        flash(f'Student ID {student_id} and associated person profile successfully deleted.', 'info')
    except pyodbc.IntegrityError as e:
        err_msg = str(e)
        if '547' in err_msg or 'FK' in err_msg or 'Credit' in err_msg:
            flash(
                f"[REFERENTIAL INTEGRITY ENFORCED]: Cannot delete Student ID {student_id}! "
                f"Foreign key constraint violation (ON DELETE NO ACTION). Active records exist in the Credit table "
                f"that depend on this student. You must remove the student's enrollments before deleting the student.",
                'danger'
            )
        else:
            flash(f'Integrity Error: {err_msg}', 'danger')
    except Exception as e:
        flash(f'Delete Error: {str(e)}', 'danger')
        
    return redirect(url_for('students_list'))

# -------------------------------------------------------------
# COURSES: Master Table View & Operations
# -------------------------------------------------------------
@app.route('/courses')
def courses_list():
    """Display courses with instructor and enrollment counts."""
    sql = """
        SELECT 
            co.CourseId, 
            co.Name, 
            co.Teacher, 
            COUNT(c.StudentId) AS EnrollmentCount
        FROM Course co
        LEFT JOIN Credit c ON co.CourseId = c.CourseId
        GROUP BY co.CourseId, co.Name, co.Teacher
        ORDER BY co.Name
    """
    courses = []
    try:
        courses = execute_query(sql, fetch='all')
    except Exception as e:
        flash(f'Error fetching courses: {str(e)}', 'warning')
        
    return render_template('courses.html', courses=courses)

@app.route('/courses/new', methods=['GET', 'POST'])
def course_create():
    """Insert a new Course record."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        teacher = request.form.get('teacher', '').strip()
        
        if not name or not teacher:
            flash('Course Name and Instructor are required.', 'warning')
            return redirect(url_for('course_create'))
            
        try:
            sql = "INSERT INTO Course (Name, Teacher) VALUES (?, ?)"
            execute_query(sql, (name, teacher), fetch='commit')
            flash(f'Course "{name}" created successfully!', 'success')
            return redirect(url_for('courses_list'))
        except Exception as e:
            flash(f'Error creating course: {str(e)}', 'danger')
            
    return render_template('course_form.html', is_edit=False)

@app.route('/courses/edit/<int:course_id>', methods=['GET', 'POST'])
def course_edit(course_id):
    """Update course parameters."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        teacher = request.form.get('teacher', '').strip()
        
        if not name or not teacher:
            flash('Course Name and Instructor are required.', 'warning')
            return redirect(request.url)
            
        try:
            sql = "UPDATE Course SET Name = ?, Teacher = ? WHERE CourseId = ?"
            execute_query(sql, (name, teacher, course_id), fetch='commit')
            flash('Course updated successfully!', 'success')
            return redirect(url_for('courses_list'))
        except Exception as e:
            flash(f'Error updating course: {str(e)}', 'danger')
            
    course = execute_query("SELECT * FROM Course WHERE CourseId = ?", (course_id,), fetch='one')
    if not course:
        flash('Course not found.', 'danger')
        return redirect(url_for('courses_list'))
        
    return render_template('course_form.html', course=course, is_edit=True)

@app.route('/courses/delete/<int:course_id>', methods=['POST'])
def course_delete(course_id):
    """
    REFERENTIAL INTEGRITY ENFORCEMENT:
    Demonstrates parent-child constraint enforcement (ON DELETE NO ACTION) on Course table.
    """
    try:
        execute_query("DELETE FROM Course WHERE CourseId = ?", (course_id,), fetch='commit')
        flash(f'Course ID {course_id} removed successfully.', 'info')
    except pyodbc.IntegrityError as e:
        err_msg = str(e)
        if '547' in err_msg or 'FK' in err_msg or 'Credit' in err_msg:
            flash(
                f"[REFERENTIAL INTEGRITY ENFORCED]: Cannot delete Course ID {course_id}! "
                f"Active student enrollment records in the Credit table reference this course (ON DELETE NO ACTION). "
                f"All enrollments for this course must be removed before the course can be deleted.",
                'danger'
            )
        else:
            flash(f'Integrity Error: {err_msg}', 'danger')
    except Exception as e:
        flash(f'Delete Error: {str(e)}', 'danger')
        
    return redirect(url_for('courses_list'))

# -------------------------------------------------------------
# VERIFICATION & SYSTEM STATUS (Lab 1 Cross-Verification)
# -------------------------------------------------------------
@app.route('/verification', methods=['GET', 'POST'])
def verification():
    """Read and insert verification timestamps matching Lab 1 dbo.Verification."""
    if request.method == 'POST':
        full_name = request.form.get('full_name', 'Matt Hildebrandt').strip()
        course_code = request.form.get('course_code', 'IST 210').strip()
        try:
            sql = "INSERT INTO dbo.Verification (FullName, CourseCode, TimeStamp) VALUES (?, ?, GETDATE())"
            execute_query(sql, (full_name, course_code), fetch='commit')
            flash('Verification audit record inserted live into Azure SQL Database!', 'success')
            return redirect(url_for('verification'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            
    verifications = []
    try:
        verifications = execute_query("SELECT FullName, CourseCode, TimeStamp FROM dbo.Verification ORDER BY TimeStamp DESC", fetch='all')
    except Exception as e:
        flash(f'Could not query Verification table: {str(e)}', 'warning')
        
    return render_template('verification.html', verifications=verifications)

@app.route('/db-status')
def db_status():
    """API endpoint returning diagnostic connection info for test automation."""
    connected, msg, details = test_connection()
    return jsonify({
        'status': 'connected' if connected else 'disconnected',
        'message': msg,
        'details': details
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')
    print(f'Starting IST 210 Lab 2 Web Application on http://localhost:{port} ...')
    app.run(host='0.0.0.0', port=port, debug=debug)
