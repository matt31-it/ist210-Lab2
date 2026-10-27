import sys
from db import get_db_connection, test_connection

def seed_database():
    print("Testing connection to Azure SQL Database...")
    success, msg, details = test_connection()
    if not success:
        print(f"Database connection failed: {msg}")
        print("Please update the DB_PASSWORD in .env before running seed_data.py.")
        return False
        
    db_name = details.get("database", "Azure SQL")
    server_name = details.get("server", "Azure")
    print(f"Connected successfully to {db_name} on {server_name}!")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ensure tables exist (matching Microsoft Learn Lab 1 specification)
    print("Verifying schema...")
    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Person')
    BEGIN
        CREATE TABLE Person (
            PersonId INT IDENTITY(1,1) PRIMARY KEY,
            FirstName NVARCHAR(128) NOT NULL,
            MiddleInitial NVARCHAR(10),
            LastName NVARCHAR(128) NOT NULL,
            DateOfBirth DATE NOT NULL
        );
        PRINT 'Created table Person';
    END
    """)
    conn.commit()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Student')
    BEGIN
        CREATE TABLE Student (
            StudentId INT IDENTITY(1,1) PRIMARY KEY,
            PersonId INT FOREIGN KEY REFERENCES Person(PersonId),
            Email NVARCHAR(256)
        );
        PRINT 'Created table Student';
    END
    """)
    conn.commit()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Course')
    BEGIN
        CREATE TABLE Course (
            CourseId INT IDENTITY(1,1) PRIMARY KEY,
            Name NVARCHAR(50) NOT NULL,
            Teacher NVARCHAR(256) NOT NULL
        );
        PRINT 'Created table Course';
    END
    """)
    conn.commit()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Credit')
    BEGIN
        CREATE TABLE Credit (
            StudentId INT FOREIGN KEY REFERENCES Student(StudentId),
            CourseId INT FOREIGN KEY REFERENCES Course(CourseId),
            Grade DECIMAL(5, 2) CHECK (Grade <= 100.00),
            Attempt TINYINT,
            CONSTRAINT [UQ_studentgrades] UNIQUE CLUSTERED (StudentId, CourseId, Grade, Attempt)
        );
        PRINT 'Created table Credit';
    END
    """)
    conn.commit()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Verification')
    BEGIN
        CREATE TABLE Verification (
            FullName VARCHAR(100),
            CourseCode VARCHAR(20),
            TimeStamp DATETIME
        );
        PRINT 'Created table Verification';
    END
    """)
    conn.commit()

    # Check current row counts
    cursor.execute("SELECT COUNT(*) FROM Course")
    course_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Person")
    person_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Student")
    student_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM Credit")
    credit_count = cursor.fetchone()[0]
    
    print(f"Current database status: {person_count} persons, {student_count} students, {course_count} courses, {credit_count} enrollments.")

    if course_count == 0:
        print("Inserting default courses...")
        courses = [
            ("IST 210: Organization of Data", "Dr. Lee"),
            ("IST 220: Networking & Telecom", "Prof. Vance"),
            ("STAT 200: Elementary Statistics", "Dr. Garcia"),
            ("CMPSC 131: Programming Concepts", "Prof. Bennett")
        ]
        cursor.executemany("INSERT INTO Course (Name, Teacher) VALUES (?, ?)", courses)
        conn.commit()

    if person_count == 0:
        print("Inserting default persons and students...")
        people = [
            ("Matt", "A", "Hildebrandt", "2003-05-14", "mah6236@psu.edu"),
            ("Alex", "J", "Taylor", "2002-11-20", "ajt501@psu.edu"),
            ("Jordan", "M", "Rivera", "2004-03-08", "jmr612@psu.edu"),
            ("Samantha", "K", "Chen", "2003-08-25", "skc884@psu.edu")
        ]
        for fn, mi, ln, dob, email in people:
            cursor.execute(
                "INSERT INTO Person (FirstName, MiddleInitial, LastName, DateOfBirth) VALUES (?, ?, ?, ?)",
                (fn, mi, ln, dob)
            )
            cursor.execute("SELECT SCOPE_IDENTITY()")
            person_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO Student (PersonId, Email) VALUES (?, ?)", (person_id, email))
        conn.commit()

    # Refresh counts
    cursor.execute("SELECT COUNT(*) FROM Credit")
    credit_count = cursor.fetchone()[0]
    
    if credit_count == 0:
        print("Inserting initial credit enrollment records...")
        cursor.execute("SELECT StudentId FROM Student ORDER BY StudentId")
        students = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT CourseId FROM Course ORDER BY CourseId")
        courses = [row[0] for row in cursor.fetchall()]
        
        sample_credits = [
            (students[0], courses[0], 96.50, 1),
            (students[0], courses[1], 91.00, 1),
            (students[1], courses[0], 88.25, 1),
            (students[1], courses[2], 94.00, 1),
            (students[2], courses[1], 82.50, 1),
            (students[2], courses[3], 79.00, 1),
            (students[3], courses[0], 98.00, 1),
            (students[3], courses[2], 92.00, 1),
        ]
        cursor.executemany("INSERT INTO Credit (StudentId, CourseId, Grade, Attempt) VALUES (?, ?, ?, ?)", sample_credits)
        conn.commit()

    # Verification ping
    cursor.execute("""
    INSERT INTO Verification (FullName, CourseCode, TimeStamp)
    VALUES (?, ?, GETDATE())
    """, ("Matt Hildebrandt (Lab 2 Live Sync)", "IST 210"))
    conn.commit()

    print("Seed process completed successfully!")
    cursor.close()
    conn.close()
    return True

if __name__ == '__main__':
    seed_database()
