from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta, timezone
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from sqlalchemy import func


app = Flask(__name__)
app.config['SECRET_KEY'] = 'the-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///student.db'

#Configure Login
db=SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


#Database models
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignments = db.relationship('Assignment', backref='course', cascade="all, delete-orphan")

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    completed = db.Column(db.Boolean, default = False)
    priority = db.Column(db.String, default = 'Medium')#options: Low, Medium, High


class User(db.Model, UserMixin):
    id=db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable = False)
    password_hash = db.Column(db.String)
    courses = db.relationship('Course', backref='user', cascade="all, delete-orphan")
    current_streak = db.Column(db.Integer, default = 0)
    longest_streak = db.Column(db.Integer, default = 0)
    last_session_date = db.Column(db.Date, nullable = True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def update_streak(self):
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        if not self.last_session_date:  # First ever session
            self.current_streak = 1
            self.last_session_date = today
        elif self.last_session_date == today:
            # Already updated today, no change needed
            return
        elif self.last_session_date == yesterday:
            # Continue streak from yesterday
            self.current_streak += 1
            self.last_session_date = today
        else:
            # Gap in sessions, reset streak
            self.current_streak = 1
            self.last_session_date = today

        # Update longest streak if needed
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak


    def check_and_reset(self):
        if not self.last_session_date:
            return
        today=date.today()
        yesterday = today -timedelta(days=1)

        if self.last_session_date<yesterday:
            self.current_streak=0



class PomodoroSession(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)
    date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    worktime = db.Column(db.Integer)
    breaktime = db.Column(db.Integer)
    cycles = db.Column(db.Integer)

#User Loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Chart Functions
def prepare_chart_data(user_id):
    seven_days_ago = datetime.now(timezone.utc)-timedelta(days=7)

    recent_sessions = PomodoroSession.query.filter(PomodoroSession.user_id == user_id, PomodoroSession.date>=seven_days_ago).order_by(PomodoroSession.date).all()

    chart_data = {
        'daily_minutes': prepare_daily_mins(recent_sessions),    # Fixed key name
        'work_vs_break': prepare_work_v_break(recent_sessions),  # Fixed key name
        'cycles_over_time': prepare_cycles_over_time(recent_sessions)
    }

    return chart_data

def prepare_daily_mins(sessions):
    daily_data = defaultdict(int)

    today = date.today()
    date_labels = []
    for i in range(6,-1,-1):
        day = today-timedelta(days=i)
        date_labels.append(day.strftime('%m/%d'))
        daily_data[day.strftime('%m/%d')] = 0

    for session in sessions:
        day_key = session.date.strftime('%m/%d')
        daily_data[day_key] += session.worktime

    return {'labels':date_labels,'data':[daily_data[label] for label in date_labels]}

def prepare_work_v_break(sessions):
    total_worktime = sum(session.worktime for session in sessions)
    total_breaktime = sum(session.breaktime for session in sessions)

    return {
        'labels': ['Work Time', 'Break Time'], 'data':[total_worktime,total_breaktime]
    }

def prepare_cycles_over_time(sessions):
    cycles_by_date = defaultdict(int)

    for session in sessions:
        day_key = session.date.strftime('%m/%d')
        cycles_by_date[day_key] += session.cycles
    
    sorted_dates = sorted(cycles_by_date.keys())
    return {'labels': sorted_dates, 'data':[cycles_by_date[date] for date in sorted_dates]}

#Recommendation function
def recommend_assignments(user_id):
    today = date.today()
    two_week = today+timedelta(days=14)
    
    assignments = Assignment.query.join(Course).filter(
    Course.user_id == user_id,
    Assignment.due_date <= two_week,
    Assignment.completed == False).all()

    recommended = []

    for assignment in assignments:
        priority=1
        if assignment.due_date<=(today+timedelta(days=1)):
            priority+=5
        elif assignment.due_date<=(today+timedelta(days=2)):
            priority+=4
        elif assignment.due_date<=(today+timedelta(days=4)):
            priority+=3
        elif assignment.due_date<=(today+timedelta(days=7)):
            priority+=2
        else:
            priority+=1

        if assignment.priority == 'High':
            priority+=5
        elif assignment.priority == 'Medium':
            priority+=3
        else:
            priority+=1
        
        recommended.append(priority)

    recommmended_item = max(recommended)
    index=recommended.index(recommmended_item)

    

    if recommended:
        return assignments[index]
    else:
        return 'Nothing Immediate. Take a break!'
    

        
        


#_____________________________________ROUTES_____________________________________________

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

#Main Routes
@app.route('/view')
@login_required
def view():
    courses = current_user.courses     # can also use Course.query.filter_by(user_id = current_user.id).all()
    today = date.today()
    end_of_week = today+ timedelta(days=7)

    week_assignments = Assignment.query.join(Course).filter(Assignment.due_date>=today, Assignment.due_date<=end_of_week, Course.user_id == current_user.id).all()

    grouped = {}

    for i in range(7):
        target = today+timedelta(days=i)
        day_name = target.strftime('%A')
        grouped[day_name] = []

    for assignment in week_assignments:
        day_name = assignment.due_date.strftime('%A')
        grouped[day_name].append(assignment)


    for course in courses:
        course.assignments.sort(key=lambda a: a.due_date or date.max)

    recommended = recommend_assignments(current_user.id)
    name = current_user.username

    return render_template('view.html', courses=courses, grouped=grouped, recommended=recommended, name=name)



@app.route('/add_course', methods=['GET', 'POST'])
@login_required
def add_course():
    if request.method == 'POST':
        name = request.form['course']
        new_course = Course(name=name, user_id = current_user.id)
        db.session.add(new_course)
        db.session.commit()
        return redirect(url_for('view'))
    return render_template('add_course.html')

@app.route('/add_assignment', methods=['GET', 'POST'])
@login_required
def add_assignment():
    courses = Course.query.filter_by(user_id = current_user.id).all()
    if not courses:
        return render_template(
            'add_assignment.html',
            courses=[],
            message="You need to add a course before creating an assignment."
        )

    if request.method == 'POST':
        name = request.form['assignment']
        course_id = request.form['course_id']
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        priority = request.form.get('priority', 'Medium')

        course = Course.query.filter_by(id = course_id, user_id = current_user.id).first()
        if not course:
            return redirect(url_for('add_assignment'))


        new_assignment = Assignment(name=name, course_id=course_id, due_date=due_date, priority=priority)
        db.session.add(new_assignment)
        db.session.commit()
        return redirect(url_for('view'))
    
    
    return render_template('add_assignment.html', courses=courses)

@app.route('/toggle/<int:id>', methods = ['POST'])
@login_required
def toggle_assignment(id):
    assignment = Assignment.query.join(Course).filter(Assignment.id == id, Course.user_id == current_user.id).first_or_404()

    recommended = recommend_assignments(current_user.id)
    assignment.completed = not assignment.completed
    db.session.commit()
    return redirect(url_for('view'))

@app.route('/delete/<int:id>', methods = ['POST'])
@login_required
def delete_assignment(id):
    assignment = Assignment.query.join(Course).filter(Assignment.id == id, Course.user_id == current_user.id).first_or_404()

    db.session.delete(assignment)
    db.session.commit()

    return redirect(url_for('view'))

@app.route('/edit/<int:id>', methods = ['GET','POST'])
@login_required
def edit_assignment(id):
    assignment = Assignment.query.join(Course).filter(Assignment.id == id, Course.user_id == current_user.id).first_or_404()
    if request.method == 'POST':
        assignment_name = request.form.get('name')
        assignment.name = assignment_name

        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        assignment.due_date = due_date

        assignment.priority = request.form.get('priority', 'Medium')

        new_course_id = request.form.get('course_id')
        if new_course_id:
            assignment.course_id = int(new_course_id)

        db.session.commit()
        return redirect(url_for("view"))
    courses = Course.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_assignment.html', assignment=assignment, courses=courses)
        

@app.route('/edit_course/<int:id>', methods = ['GET','POST'])
@login_required
def edit_course(id):
    course = Course.query.filter(Course.id == id, Course.user_id == current_user.id).first_or_404()

    if request.method == 'POST':
        new_name = request.form.get('name')
        print("Edit course form submitted. New name:", new_name)

        course.name = new_name
        db.session.commit()

        return redirect(url_for('view'))

    return render_template('edit_course.html', course=course)


@app.route('/delete_course/<int:id>', methods = ['POST'])
@login_required
def delete_course(id):
    course = Course.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(course)
    db.session.commit()

    return redirect(url_for('view'))


@app.route('/remove_completed', methods = ['POST'])
@login_required
def remove_completed():
    completed_assignments = Assignment.query.join(Course).filter(Assignment.completed == True, Course.user_id == current_user.id).all()

    for assignment in completed_assignments:
        db.session.delete(assignment)
    db.session.commit()

    return redirect(url_for('view'))

#Authentication Routes
@app.route('/signup', methods = ['GET','POST'])#Signup page
def signup():
    if request.method == 'POST':
        username = request.form["username"]
        email = request.form['email']
        password = request.form['password']

        # Check if email exists
        returning_user = User.query.filter_by(email=email).first()
        if returning_user:
            return render_template('signup.html', error='That email is already in use.')

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        return redirect("/login")
        
    return render_template('signup.html')

@app.route('/login', methods = ['GET','POST'])#LOGIN PAGE
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect("/view")
        else:
            return render_template('login.html', error='Invalid email or password')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('dashboard'))


#Dashboard
@login_required
@app.route('/work', methods = ['GET', 'POST'])
def work():
    current_user.check_and_reset()
    db.session.commit()

    page = request.args.get('page', 1, type=int)
    per_page = 4

    sessions_pagination = PomodoroSession.query.filter(PomodoroSession.user_id == current_user.id).order_by(PomodoroSession.date.desc()).paginate(page = page, per_page=per_page, error_out=False)
    courses = Course.query.filter_by(user_id = current_user.id).all()
    assignments = Assignment.query.join(Course).filter(Course.user_id == current_user.id).all()
    
    chart_data = prepare_chart_data(current_user.id)

    return render_template('work.html', courses=courses, assignments = assignments, sessions_pagination=sessions_pagination, current_user = current_user, chart_data=chart_data)

@login_required
@app.route('/log_session', methods = ['POST'])
def log_session():
    data = request.get_json()
    work_time = data.get('worktime')
    break_time = data.get('breaktime')
    work_cycles = data.get('cycles')
    new_session = PomodoroSession(user_id = current_user.id, worktime = work_time, breaktime = break_time, cycles = work_cycles)
    db.session.add(new_session)

    current_user.update_streak()

    db.session.commit()

    return {'status': 'success'}, 200



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)