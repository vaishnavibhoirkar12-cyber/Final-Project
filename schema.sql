CREATE TABLE Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) CHECK (role IN ('student', 'faculty', 'admin')) NOT NULL
);

CREATE TABLE Students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    course VARCHAR(100),
    year INTEGER
);

CREATE TABLE Faculty (
    faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES Users(user_id) ON DELETE CASCADE,
    department VARCHAR(100)
);

CREATE TABLE Projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    student_id INTEGER REFERENCES Students(student_id) ON DELETE CASCADE,
    faculty_id INTEGER REFERENCES Faculty(faculty_id) ON DELETE SET NULL
);

CREATE TABLE Submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES Projects(project_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER REFERENCES Submissions(submission_id) ON DELETE CASCADE,
    faculty_id INTEGER REFERENCES Faculty(faculty_id) ON DELETE CASCADE,
    grade VARCHAR(10),
    comments TEXT
);

CREATE TABLE Deadlines (
    deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course VARCHAR(100) NOT NULL,
    last_date TIMESTAMP NOT NULL
);
