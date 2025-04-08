from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    national_id = db.Column(db.String(10), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    discount_code = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"User('{self.first_name}', '{self.last_name}', '{self.phone}')"

class DiscountCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    discount_percent = db.Column(db.Integer, default=32)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"DiscountCode('{self.code}', '{self.is_used}')"

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Admin('{self.username}')"

def initialize_database():
    """تابع مقداردهی اولیه دیتابیس"""
    with app.app_context():
        # ایجاد جداول در صورت عدم وجود
        db.create_all()
        
        try:
            # اضافه کردن کدهای تخفیف اولیه اگر وجود ندارند
            if DiscountCode.query.count() == 0:
                initial_codes = [
                    "identendo48153", "identendo65738", "identendo41786", 
                    "identendo86139", "identendo35262"
                ]
                for code in initial_codes:
                    if not DiscountCode.query.filter_by(code=code).first():
                        new_code = DiscountCode(
                            code=code,
                            is_used=False,
                            discount_percent=32
                        )
                        db.session.add(new_code)
                db.session.commit()
            
            # ایجاد ادمین پیشفرض اگر وجود ندارد
            if Admin.query.count() == 0:
                admin = Admin(
                    username='administrator',
                    password=generate_password_hash('Loc@R@2')
                )
                db.session.add(admin)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"خطا در مقداردهی اولیه دیتابیس: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        national_id = request.form.get('national_id')
        phone = request.form.get('phone')
        
        # اعتبارسنجی فیلدهای ورودی
        if not all([first_name, last_name, national_id, phone]):
            flash('لطفا تمام فیلدها را پر کنید', 'danger')
            return redirect(url_for('login'))
        
        if len(national_id) != 10 or not national_id.isdigit():
            flash('کد ملی باید 10 رقمی باشد', 'danger')
            return redirect(url_for('login'))
        
        if not phone.startswith('09') or len(phone) != 11 or not phone.isdigit():
            flash('شماره تماس باید با 09 شروع شود و 11 رقمی باشد', 'danger')
            return redirect(url_for('login'))

        try:
            # بررسی وجود کاربر
            existing_user = User.query.filter(
                (User.national_id == national_id) | (User.phone == phone)
            ).first()
            
            if existing_user:
                existing_user.first_name = first_name
                existing_user.last_name = last_name
                db.session.commit()
                user = existing_user
                flash('اطلاعات شما با موفقیت به‌روزرسانی شد', 'info')
            else:
                user = User(
                    first_name=first_name,
                    last_name=last_name,
                    national_id=national_id,
                    phone=phone
                )
                db.session.add(user)
                db.session.commit()
                flash('ثبت نام شما با موفقیت انجام شد', 'success')

            # اختصاص کد تخفیف در صورت نداشتن
            discount_code = None
            if not user.discount_code:
                discount = DiscountCode.query.filter_by(is_used=False).first()
                if discount:
                    discount.is_used = True
                    user.discount_code = discount.code
                    db.session.commit()
                    discount_code = discount.code
                else:
                    flash('کد تخفیف در دسترس نیست', 'warning')
            else:
                discount_code = user.discount_code

            return render_template('login.html', user=user, discount_code=discount_code)
        
        except Exception as e:
            db.session.rollback()
            flash('خطایی در ثبت اطلاعات رخ داد. لطفا مجددا تلاش کنید', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/assign_discount/<int:user_id>')
def assign_discount(user_id):
    try:
        user = User.query.get_or_404(user_id)
        
        if user.discount_code:
            flash('شما قبلاً کد تخفیف دریافت کرده‌اید', 'warning')
            return redirect(url_for('login'))
        
        # پیدا کردن اولین کد تخفیف استفاده نشده
        discount = DiscountCode.query.filter_by(is_used=False).first()
        
        if discount:
            discount.is_used = True
            user.discount_code = discount.code
            db.session.commit()
            flash('کد تخفیف با موفقیت برای شما فعال شد', 'success')
        else:
            flash('متاسفانه کد تخفیفی موجود نیست', 'danger')
        
        return redirect(url_for('login'))
    
    except Exception as e:
        db.session.rollback()
        flash('خطایی در اختصاص کد تخفیف رخ داد', 'danger')
        return redirect(url_for('login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('لطفا نام کاربری و رمز عبور را وارد کنید', 'danger')
            return redirect(url_for('admin_login'))
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and check_password_hash(admin.password, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            flash('نام کاربری یا رمز عبور اشتباه است', 'danger')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    users_with_discount = User.query.filter(User.discount_code.isnot(None)).all()
    total_users = User.query.count()
    total_discounts = DiscountCode.query.count()
    used_discounts = DiscountCode.query.filter_by(is_used=True).count()
    
    return render_template(
        'admin_dashboard.html',
        users=users_with_discount,
        total_users=total_users,
        total_discounts=total_discounts,
        used_discounts=used_discounts
    )

@app.route('/admin/discount-codes')
def admin_discount_codes():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    discount_codes = DiscountCode.query.order_by(DiscountCode.is_used, DiscountCode.created_at).all()
    return render_template('admin_discount_codes.html', discount_codes=discount_codes)

@app.route('/admin/add-discount-codes', methods=['POST'])
def add_discount_codes():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        codes = request.form.get('codes')
        if not codes:
            flash('لطفا کدهای تخفیف را وارد کنید', 'danger')
            return redirect(url_for('admin_discount_codes'))
        
        code_list = [code.strip() for code in codes.split('\n') if code.strip()]
        added = 0
        exists = 0
        
        try:
            for code in code_list:
                if not DiscountCode.query.filter_by(code=code).first():
                    discount = DiscountCode(
                        code=code,
                        is_used=False,
                        discount_percent=32
                    )
                    db.session.add(discount)
                    added += 1
                else:
                    exists += 1
            
            db.session.commit()
            flash(f'{added} کد تخفیف جدید اضافه شد. {exists} کد تکراری بود.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'خطا در اضافه کردن کدهای تخفیف: {str(e)}', 'danger')
    
    return redirect(url_for('admin_discount_codes'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('با موفقیت خارج شدید', 'success')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    initialize_database()
    app.run(host='192.168.140.143',port=5000)