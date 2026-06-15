from flask import Flask, render_template, request, redirect, url_for, session
from models import db, Booking, Admin
from werkzeug.security import check_password_hash

from flask import Flask, render_template, request, redirect, url_for, session, send_file
from models import db, Booking, Admin, User, OTP
from werkzeug.security import check_password_hash
from utils.excel_export import generate_excel
from utils.otp import generate_otp, send_otp
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'change-this-to-a-random-secret-key'  # needed for sessions

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# ---------- CUSTOMER ROUTES ----------

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        new_booking = Booking(
            user_id=session.get('user_id'),  # links booking to logged-in user (if any)
            name=request.form['name'],
            contact=request.form['contact'],
            service_type=request.form['service_type'],
            preferred_time=request.form['preferred_time'],
            notes=request.form['notes']
        )
        db.session.add(new_booking)
        db.session.commit()
        return redirect(url_for('confirmation'))

    preselected_service = request.args.get('service', '')
    # Pre-fill contact number if user is logged in
    user_mobile = session.get('user_mobile', '')
    return render_template('booking.html', preselected_service=preselected_service, user_mobile=user_mobile)

@app.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form['mobile']

        # Generate and "send" OTP
        otp_code = generate_otp()
        send_otp(mobile, otp_code)

        # Save OTP to database
        new_otp = OTP(mobile=mobile, otp_code=otp_code)
        db.session.add(new_otp)
        db.session.commit()

        # Store mobile in session temporarily for verification step
        session['otp_mobile'] = mobile

        return redirect(url_for('verify_otp'))

    return render_template('login.html')


@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    mobile = session.get('otp_mobile')

    if not mobile:
        return redirect(url_for('login'))

    if request.method == 'POST':
        entered_otp = request.form['otp']

        # Get the most recent OTP for this mobile
        otp_record = OTP.query.filter_by(mobile=mobile).order_by(OTP.created_at.desc()).first()

        # Check if OTP matches and is within 5 minutes
        if otp_record and otp_record.otp_code == entered_otp:
            time_diff = datetime.utcnow() - otp_record.created_at
            if time_diff < timedelta(minutes=5):
                # OTP valid - find or create user
                user = User.query.filter_by(mobile=mobile).first()
                if not user:
                    user = User(mobile=mobile)
                    db.session.add(user)
                    db.session.commit()

                # Log the user in
                session['user_logged_in'] = True
                session['user_mobile'] = mobile
                session['user_id'] = user.id

                # Clean up temporary session data
                session.pop('otp_mobile', None)

                return redirect(url_for('home'))
            else:
                return render_template('verify_otp.html', mobile=mobile, error="OTP expired. Please request a new one.")
        else:
            return render_template('verify_otp.html', mobile=mobile, error="Invalid OTP. Please try again.")

    return render_template('verify_otp.html', mobile=mobile)


@app.route('/logout')
def logout():
    session.pop('user_logged_in', None)
    session.pop('user_mobile', None)
    session.pop('user_id', None)
    return redirect(url_for('home'))
# ---------- ADMIN ROUTES ----------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            session['admin_username'] = admin.username
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin/admin_login.html', error="Invalid username or password")

    return render_template('admin/admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    # Get filter values from URL query parameters
    search_query = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    service_filter = request.args.get('service', '')

    # Start with all bookings
    query = Booking.query

    # Apply search (matches name or contact)
    if search_query:
        query = query.filter(
            (Booking.name.contains(search_query)) |
            (Booking.contact.contains(search_query))
        )

    # Apply status filter
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    # Apply service type filter
    if service_filter:
        query = query.filter(Booking.service_type == service_filter)

    all_bookings = query.order_by(Booking.created_at.desc()).all()

    # For stats cards - use all bookings (unfiltered)
    total_bookings = Booking.query.all()

    return render_template('admin/dashboard.html',
                          bookings=all_bookings,
                          total_bookings=total_bookings,
                          search_query=search_query,
                          status_filter=status_filter,
                          service_filter=service_filter)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin/update_status/<int:booking_id>', methods=['POST'])
def update_status(booking_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form['status']
    booking.status = new_status
    db.session.commit()

    return redirect(url_for('admin_dashboard'))
if __name__ == '__main__':
    app.run(debug=True)
