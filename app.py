from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory
from models import db, User, Submission, Assignment, Deadline
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os, uuid
import datetime
import fitz  # PyMuPDF

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project_db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'zip', 'rar'}

db.init_app(app)
bcrypt = Bcrypt(app)


# ───────────── HELPER ─────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ───────────── HOME ─────────────
@app.route('/')
def home():
    return render_template('index.html')


# ───────────── REGISTER ─────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        course = request.form.get('course')
        year = request.form.get('year')
        department = request.form.get('department')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        new_user = User(
            username=username,
            email=email,
            password=hashed_pw,
            role=role,
            course=course if role == 'student' else None,
            year=int(year) if (role == 'student' and year) else None,
            department=department if role == 'faculty' else None
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ───────────── LOGIN ─────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            if user.role != role:
                flash(f'You are registered as a {user.role}, not a {role}. Please select the correct role.', 'danger')
                return redirect(url_for('login'))
                
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'faculty':
                return redirect(url_for('faculty_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


# ───────────── LOGOUT ─────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ───────────── STUDENT DASHBOARD ─────────────
@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    assignments_list = Assignment.query.all()

    projects = Submission.query.filter_by(user_id=session['user_id'])\
        .order_by(Submission.submitted_at.desc()).all()

    return render_template(
        'student_dashboard.html',
        assignments_list=assignments_list,
        projects=projects,
        deadline=None
    )


# ───────────── FACULTY DASHBOARD ─────────────
@app.route('/faculty_dashboard')
def faculty_dashboard():
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))
        
    my_assignments = Assignment.query.filter_by(faculty_id=session['user_id']).all()
    my_assignment_ids = [a.id for a in my_assignments]

    submissions = Submission.query.filter(Submission.assignment_id.in_(my_assignment_ids))\
        .order_by(Submission.submitted_at.desc()).all()

    return render_template('faculty_dashboard.html', submissions=submissions, assignments=my_assignments)

# ───────────── CREATE ASSIGNMENT ─────────────
@app.route('/create_assignment', methods=['POST'])
def create_assignment():
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))

    title = request.form.get('title')
    description = request.form.get('description')
    rubric = request.form.get('rubric')

    if not title:
        flash('Title is required.', 'danger')
        return redirect(url_for('faculty_dashboard'))

    new_assign = Assignment(
        title=title,
        description=description,
        rubric=rubric,
        faculty_id=session['user_id']
    )
    db.session.add(new_assign)
    db.session.commit()

    flash('Assignment created successfully!', 'success')
    return redirect(url_for('faculty_dashboard'))


# ───────────── ADMIN DASHBOARD ─────────────
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    users = User.query.all()

    return render_template(
        'admin_dashboard.html',
        users=users,
        students=User.query.filter_by(role='student').count(),
        faculty=User.query.filter_by(role='faculty').count(),
        submissions=Submission.query.count(),
        deadlines=Deadline.query.all()
    )


# ───────────── ADMIN ROUTES ─────────────
@app.route('/set_deadline', methods=['POST'])
def set_deadline():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    course = request.form.get('course')
    last_date_str = request.form.get('last_date')
    if course and last_date_str:
        try:
            dt = datetime.datetime.strptime(last_date_str, '%Y-%m-%dT%H:%M')
            dl = Deadline(course=course, last_date=dt)
            db.session.add(dl)
            db.session.commit()
            flash('Deadline saved successfully', 'success')
        except Exception as e:
            flash(f"Error saving deadline: {e}", "danger")

    return redirect(url_for('admin_dashboard'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    if user:
        if user.id == session.get('user_id'):
            flash("Cannot delete your own admin account.", "danger")
        else:
            db.session.delete(user)
            db.session.commit()
            flash('User deleted successfully', 'success')
    return redirect(url_for('admin_dashboard'))


# ───────────── UPLOAD PROJECT ─────────────
@app.route('/upload', methods=['POST'])
def upload():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    assignment_id = request.form.get('assignment_id')
    file = request.files.get('file')

    if not assignment_id or not file:
        flash('All fields are required.', 'danger')
        return redirect(url_for('student_dashboard'))

    if not allowed_file(file.filename):
        flash('Invalid file type.', 'danger')
        return redirect(url_for('student_dashboard'))
        
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        flash('Invalid assignment.', 'danger')
        return redirect(url_for('student_dashboard'))

    # Duplicate check
    existing = Submission.query.filter_by(
        user_id=session['user_id'],
        assignment_id=assignment.id
    ).first()

    if existing:
        flash('You have already submitted for this assignment.', 'danger')
        return redirect(url_for('student_dashboard'))

    original = secure_filename(file.filename)
    unique = f"{uuid.uuid4().hex}_{original}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique)
    
    file.save(filepath)

    # Keyword Based Evaluation Logic
    auto_score = None
    auto_feedback = None
    
    try:
        if original.lower().endswith('.pdf') and assignment.rubric:
            doc = fitz.open(filepath)
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            
            # Case-insensitive block
            text_lower = text_content.lower()
            
            # Parse keywords
            raw_keywords = [k.strip() for k in assignment.rubric.split(',')]
            keywords = [k for k in raw_keywords if k] # filter empty
            
            if keywords:
                found_keywords = []
                missing_keywords = []
                
                for kw in keywords:
                    if kw.lower() in text_lower:
                        found_keywords.append(kw)
                    else:
                        missing_keywords.append(kw)
                
                total = len(keywords)
                found_count = len(found_keywords)
                percentage = int((found_count / total) * 100)
                
                auto_score = f"{percentage}% Match"
                
                feedback_lines = []
                feedback_lines.append(f"Keyword Score: {found_count}/{total} required terms found.")
                
                if found_keywords:
                    feedback_lines.append("\n✔️ Found: " + ", ".join(found_keywords))
                if missing_keywords:
                    feedback_lines.append("\n❌ Missing: " + ", ".join(missing_keywords))
                
                auto_feedback = "\n".join(feedback_lines)
            else:
                auto_score = "0% Match"
                auto_feedback = "No keywords defined in rubric."
    except Exception as e:
        auto_feedback = f"Keyword Evaluation failed: {str(e)}"
        auto_score = "Error"

    submission = Submission(
        filename=unique,
        original_filename=original,
        user_id=session['user_id'],
        assignment_id=assignment.id,
        auto_score=auto_score,
        auto_feedback=auto_feedback
    )

    db.session.add(submission)
    db.session.commit()

    flash('Project submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))


# ───────────── DOWNLOAD ─────────────
@app.route('/download/<int:submission_id>')
def download_file(submission_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))

    sub = Submission.query.get_or_404(submission_id)

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        sub.filename,
        as_attachment=True,
        download_name=sub.original_filename
    )


# ───────────── DELETE SUBMISSION ─────────────
@app.route('/delete_submission/<int:submission_id>', methods=['POST'])
def delete_submission(submission_id):
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))

    sub = Submission.query.get(submission_id)
    if not sub:
        flash('Submission not found.', 'danger')
        return redirect(url_for('faculty_dashboard'))
    
    # Try to delete the actual file from storage
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], sub.filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except BaseException:
            pass
            
    db.session.delete(sub)
    db.session.commit()

    flash('Submission permanently removed.', 'success')
    return redirect(url_for('faculty_dashboard'))


# ───────────── GRADE ─────────────
@app.route('/grade', methods=['POST'])
def grade():
    if session.get('role') != 'faculty':
        return redirect(url_for('login'))

    sub = Submission.query.get(request.form.get('submission_id'))

    if not sub:
        flash('Submission not found.', 'danger')
        return redirect(url_for('faculty_dashboard'))

    sub.grade = request.form.get('grade')
    sub.comments = request.form.get('comments')

    db.session.commit()

    flash('Evaluation submitted!', 'success')
    return redirect(url_for('faculty_dashboard'))


# ───────────── RUN ─────────────
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=10000)
