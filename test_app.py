import unittest
from unittest.mock import patch, MagicMock
import pyodbc
from app import app

class TestLab2App(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_routes_status_codes(self):
        """Verify all core GET endpoints respond with 200 OK."""
        routes = ['/', '/enroll/new', '/students', '/students/new', '/courses', '/courses/new', '/verification', '/db-status']
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, f"Route {route} failed with {response.status_code}")

    def test_enroll_validation_grade_bounds(self):
        """Verify business logic rejects invalid grades (>100 or <0)."""
        response = self.client.post('/enroll/new', data={
            'student_id': '1',
            'course_id': '1',
            'grade': '105.00',
            'attempt': '1'
        }, follow_redirects=True)
        self.assertIn(b'Grade must be between 0.00 and 100.00', response.data)

        response_neg = self.client.post('/enroll/new', data={
            'student_id': '1',
            'course_id': '1',
            'grade': '-5.00',
            'attempt': '1'
        }, follow_redirects=True)
        self.assertIn(b'Grade must be between 0.00 and 100.00', response_neg.data)

    def test_enroll_validation_attempt_bounds(self):
        """Verify attempt must be at least 1."""
        response = self.client.post('/enroll/new', data={
            'student_id': '1',
            'course_id': '1',
            'grade': '85.00',
            'attempt': '0'
        }, follow_redirects=True)
        self.assertIn(b'Attempt must be at least 1', response.data)

    @patch('app.execute_query')
    def test_referential_integrity_student_delete(self, mock_execute):
        """Verify foreign key constraint (ON DELETE NO ACTION) raises friendly flash on Error 547."""
        # 1st call: SELECT PersonId returns person ID 10
        # 2nd call: DELETE FROM Student raises pyodbc.IntegrityError 547
        mock_execute.side_effect = [
            {'PersonId': 10},
            pyodbc.IntegrityError('23000', '[23000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]The DELETE statement conflicted with the REFERENCE constraint "FK__Credit__StudentI". The conflict occurred in database "ist-210-work", table "dbo.Credit", column \'StudentId\'. (547)')
        ]

        response = self.client.post('/students/delete/1', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'REFERENTIAL INTEGRITY ENFORCED', response.data)
        self.assertIn(b'Credit table', response.data)

    @patch('app.execute_query')
    def test_referential_integrity_course_delete(self, mock_execute):
        """Verify foreign key constraint on Course delete raises friendly flash on Error 547."""
        mock_execute.side_effect = pyodbc.IntegrityError('23000', '[23000] (547) DELETE conflict with Credit')

        response = self.client.post('/courses/delete/1', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'REFERENTIAL INTEGRITY ENFORCED', response.data)

    def test_security_parameterized_queries(self):
        """Inspect app.py source to ensure NO raw string interpolation / f-strings are used for SQL execution."""
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        with open('db.py', 'r', encoding='utf-8') as f_db:
            db_content = f_db.read()
            
        # Ensure execute_query calls pass parameter tuples
        self.assertIn('cursor.execute(sql, params)', db_content)
        # Ensure no f-string or % query injections
        self.assertNotIn('execute_query(f"SELECT', content)
        self.assertNotIn('execute_query(f"INSERT', content)
        self.assertNotIn('execute_query(f"UPDATE', content)
        self.assertNotIn('execute_query(f"DELETE', content)

if __name__ == '__main__':
    unittest.main()
