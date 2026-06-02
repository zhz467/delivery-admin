import os
import re
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

from models import db, User, Role, OrderStatus, Client, Courier, Order, Route, ActivityLog

app = Flask(__name__)

# Настройки базы данных
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME', 'delivery_admin')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============ Вспомогательные функции ============

def has_role_in_current_user(roles):
    for role in roles:
        if current_user.has_role(role):
            return True
    return False

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Пожалуйста, войдите в систему', 'warning')
                return redirect(url_for('login'))
            
            has_access = False
            for role in roles:
                if current_user.has_role(role):
                    has_access = True
                    break
            
            if not has_access:
                flash('У вас недостаточно прав для доступа к этой странице', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_activity(action, entity, entity_id, details=None):
    log = ActivityLog(
        user_id=current_user.id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

# ============ Контекстный процессор ============

@app.context_processor
def utility_processor():
    def has_role(role_name):
        return current_user.is_authenticated and current_user.has_role(role_name)
    return dict(has_role=has_role, now=datetime.now())

# ============ Авторизация и регистрация ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            login_user(user)
            log_activity('login', 'user', user.id, f'Вход пользователя {user.email}')
            flash('Добро пожаловать!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        errors = []
        
        if not email:
            errors.append('Email обязателен')
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Введите корректный email')
        
        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        elif password != confirm_password:
            errors.append('Пароли не совпадают')
        
        if not full_name:
            errors.append('Введите ваше имя')
        
        if phone and not re.match(r'^[\+\d\s\-\(\)]{10,20}$', phone):
            errors.append('Введите корректный номер телефона')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            errors.append('Пользователь с таким email уже существует')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
        else:
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                full_name=full_name,
                phone=phone,
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            
            default_role = Role.query.filter_by(name='user').first()
            if not default_role:
                default_role = Role(name='user', description='Обычный пользователь')
                db.session.add(default_role)
                db.session.commit()
            
            user.roles.append(default_role)
            db.session.commit()
            
            login_user(user)
            log_activity('register', 'user', user.id, f'Зарегистрирован новый пользователь {user.email}')
            
            flash('Регистрация успешно завершена! Добро пожаловать!', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    log_activity('logout', 'user', current_user.id, f'Выход пользователя {current_user.email}')
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

# ============ Dashboard ============

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    total_orders = Order.query.count()
    total_clients = Client.query.count()
    total_couriers = Courier.query.count()
    available_couriers = Courier.query.filter_by(is_available=True).count()
    today_orders = Order.query.filter(db.func.date(Order.created_at) == date.today()).count()
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html',
                         total_orders=total_orders,
                         total_clients=total_clients,
                         total_couriers=total_couriers,
                         available_couriers=available_couriers,
                         today_orders=today_orders,
                         recent_activities=recent_activities,
                         recent_orders=recent_orders)

# ============ Профиль пользователя ============

@app.route('/profile')
@login_required
def profile():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()
    return render_template('profile.html', logs=logs)

@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not full_name:
        flash('ФИО обязательно для заполнения', 'danger')
        return redirect(url_for('profile'))
    
    current_user.full_name = full_name
    current_user.phone = phone
    
    if new_password:
        if len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'danger')
        elif new_password != confirm_password:
            flash('Пароли не совпадают', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_password)
            flash('Пароль успешно изменен', 'success')
    
    db.session.commit()
    log_activity('update_profile', 'user', current_user.id, f'Пользователь {current_user.email} обновил профиль')
    flash('Профиль успешно обновлен', 'success')
    return redirect(url_for('profile'))

# ============ Управление пользователями (только admin) ============

@app.route('/admin/users')
@login_required
@role_required(['admin'])
def users_list():
    users = User.query.all()
    roles = Role.query.all()
    return render_template('users_list.html', users=users, roles=roles)

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def user_create():
    roles = Role.query.all()
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return redirect(url_for('user_create'))
        
        password = request.form.get('password')
        if not password:
            flash('Пароль обязателен', 'danger')
            return redirect(url_for('user_create'))
        
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            full_name=request.form.get('full_name'),
            phone=request.form.get('phone'),
            is_active='is_active' in request.form
        )
        db.session.add(user)
        db.session.commit()
        
        role_ids = request.form.getlist('roles')
        for role_id in role_ids:
            role = Role.query.get(int(role_id))
            if role:
                user.roles.append(role)
        
        db.session.commit()
        log_activity('create', 'user', user.id, f'Создан пользователь {user.email}')
        flash('Пользователь создан', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('user_form.html', user=None, roles=roles)

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def user_edit(id):
    user = User.query.get_or_404(id)
    roles = Role.query.all()
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.is_active = 'is_active' in request.form
        
        password = request.form.get('password')
        if password:
            if len(password) >= 6:
                user.password_hash = generate_password_hash(password)
                flash('Пароль изменен', 'info')
            else:
                flash('Пароль должен быть не менее 6 символов', 'warning')
        
        user.roles.clear()
        role_ids = request.form.getlist('roles')
        for role_id in role_ids:
            role = Role.query.get(int(role_id))
            if role:
                user.roles.append(role)
        
        db.session.commit()
        log_activity('update', 'user', user.id, f'Изменен пользователь {user.email}')
        flash('Пользователь успешно обновлен', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('user_form.html', user=user, roles=roles)

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
@role_required(['admin'])
def user_delete(id):
    if id == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('users_list'))
    
    user = User.query.get_or_404(id)
    log_activity('delete', 'user', user.id, f'Удален пользователь {user.email}')
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('users_list'))

# ============ Заказы (CRUD) ============

@app.route('/admin/orders')
@login_required
def orders_list():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query = Order.query
    if search:
        query = query.join(Client).filter(
            db.or_(
                Client.name.like(f'%{search}%'),
                Order.address.like(f'%{search}%')
            )
        )
    
    orders = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=per_page)
    statuses = OrderStatus.query.all()
    
    return render_template('orders_list.html', orders=orders, statuses=statuses, search=search)

@app.route('/admin/orders/create', methods=['GET', 'POST'])
@login_required
def order_create():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    clients = Client.query.all()
    couriers = Courier.query.all()
    statuses = OrderStatus.query.all()
    
    if request.method == 'POST':
        try:
            order = Order(
                client_id=int(request.form.get('client_id')),
                courier_id=int(request.form.get('courier_id')) if request.form.get('courier_id') else None,
                status_id=int(request.form.get('status_id')),
                total=float(request.form.get('total')),
                address=request.form.get('address'),
                notes=request.form.get('notes')
            )
            db.session.add(order)
            db.session.commit()
            log_activity('create', 'order', order.id, f'Создан заказ #{order.id}')
            flash('Заказ создан', 'success')
            return redirect(url_for('orders_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('order_form.html', clients=clients, couriers=couriers, statuses=statuses, order=None)

@app.route('/admin/orders/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def order_edit(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    order = Order.query.get_or_404(id)
    clients = Client.query.all()
    couriers = Courier.query.all()
    statuses = OrderStatus.query.all()
    
    if request.method == 'POST':
        try:
            order.client_id = int(request.form.get('client_id'))
            order.courier_id = int(request.form.get('courier_id')) if request.form.get('courier_id') else None
            order.status_id = int(request.form.get('status_id'))
            order.total = float(request.form.get('total'))
            order.address = request.form.get('address')
            order.notes = request.form.get('notes')
            order.updated_at = datetime.now()
            
            db.session.commit()
            log_activity('update', 'order', order.id, f'Изменен заказ #{order.id}')
            flash('Заказ обновлен', 'success')
            return redirect(url_for('orders_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('order_form.html', order=order, clients=clients, couriers=couriers, statuses=statuses)

@app.route('/admin/orders/delete/<int:id>', methods=['POST'])
@login_required
def order_delete(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    order = Order.query.get_or_404(id)
    log_activity('delete', 'order', order.id, f'Удален заказ #{order.id}')
    db.session.delete(order)
    db.session.commit()
    flash('Заказ удален', 'success')
    return redirect(url_for('orders_list'))

# ============ Клиенты (CRUD) ============

@app.route('/admin/clients')
@login_required
def clients_list():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return render_template('clients_list.html', clients=clients)

@app.route('/admin/clients/create', methods=['GET', 'POST'])
@login_required
def client_create():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    if request.method == 'POST':
        try:
            client = Client(
                name=request.form.get('name'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address')
            )
            db.session.add(client)
            db.session.commit()
            log_activity('create', 'client', client.id, f'Создан клиент {client.name}')
            flash('Клиент создан', 'success')
            return redirect(url_for('clients_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('client_form.html', client=None)

@app.route('/admin/clients/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def client_edit(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    client = Client.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            client.name = request.form.get('name')
            client.phone = request.form.get('phone')
            client.email = request.form.get('email')
            client.address = request.form.get('address')
            db.session.commit()
            log_activity('update', 'client', client.id, f'Изменен клиент {client.name}')
            flash('Клиент обновлен', 'success')
            return redirect(url_for('clients_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('client_form.html', client=client)

@app.route('/admin/clients/delete/<int:id>', methods=['POST'])
@login_required
def client_delete(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    client = Client.query.get_or_404(id)
    log_activity('delete', 'client', client.id, f'Удален клиент {client.name}')
    db.session.delete(client)
    db.session.commit()
    flash('Клиент удален', 'success')
    return redirect(url_for('clients_list'))

# ============ Курьеры (CRUD) ============

@app.route('/admin/couriers')
@login_required
def couriers_list():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    couriers = Courier.query.all()
    return render_template('couriers_list.html', couriers=couriers)

@app.route('/admin/couriers/create', methods=['GET', 'POST'])
@login_required
def courier_create():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    users = User.query.all()
    
    if request.method == 'POST':
        try:
            courier = Courier(
                user_id=int(request.form.get('user_id')) if request.form.get('user_id') else None,
                phone=request.form.get('phone'),
                vehicle_type=request.form.get('vehicle_type'),
                license_plate=request.form.get('license_plate'),
                is_available='is_available' in request.form
            )
            db.session.add(courier)
            db.session.commit()
            log_activity('create', 'courier', courier.id, 'Создан курьер')
            flash('Курьер создан', 'success')
            return redirect(url_for('couriers_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('courier_form.html', courier=None, users=users)

@app.route('/admin/couriers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def courier_edit(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    courier = Courier.query.get_or_404(id)
    users = User.query.all()
    
    if request.method == 'POST':
        try:
            courier.user_id = int(request.form.get('user_id')) if request.form.get('user_id') else None
            courier.phone = request.form.get('phone')
            courier.vehicle_type = request.form.get('vehicle_type')
            courier.license_plate = request.form.get('license_plate')
            courier.is_available = 'is_available' in request.form
            db.session.commit()
            log_activity('update', 'courier', courier.id, 'Изменен курьер')
            flash('Курьер обновлен', 'success')
            return redirect(url_for('couriers_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('courier_form.html', courier=courier, users=users)

@app.route('/admin/couriers/delete/<int:id>', methods=['POST'])
@login_required
def courier_delete(id):
    if not has_role_in_current_user(['admin']):
        abort(403)
    
    courier = Courier.query.get_or_404(id)
    log_activity('delete', 'courier', courier.id, 'Удален курьер')
    db.session.delete(courier)
    db.session.commit()
    flash('Курьер удален', 'success')
    return redirect(url_for('couriers_list'))

# ============ Маршруты (CRUD) - ИСПРАВЛЕНО ============

@app.route('/admin/routes')
@login_required
def routes_list():
    if not has_role_in_current_user(['admin', 'manager', 'courier_viewer']):
        abort(403)
    
    # Для курьеров показываем только их маршруты
    if current_user.has_role('courier_viewer') and not has_role_in_current_user(['admin', 'manager']):
        courier = Courier.query.filter_by(user_id=current_user.id).first()
        if courier:
            routes = Route.query.filter_by(courier_id=courier.id).all()
        else:
            routes = []
    else:
        routes = Route.query.all()
    
    return render_template('routes_list.html', routes=routes)

@app.route('/admin/routes/create', methods=['GET', 'POST'])
@login_required
def route_create():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    couriers = Courier.query.all()
    
    if request.method == 'POST':
        try:
            route = Route(
                courier_id=int(request.form.get('courier_id')),
                date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
                start_time=datetime.strptime(request.form.get('start_time'), '%H:%M').time() if request.form.get('start_time') else None,
                end_time=datetime.strptime(request.form.get('end_time'), '%H:%M').time() if request.form.get('end_time') else None,
                total_distance=float(request.form.get('total_distance')) if request.form.get('total_distance') else None,
                notes=request.form.get('notes')
            )
            db.session.add(route)
            db.session.commit()
            log_activity('create', 'route', route.id, f'Создан маршрут #{route.id}')
            flash('Маршрут успешно создан', 'success')
            return redirect(url_for('routes_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании маршрута: {str(e)}', 'danger')
    
    return render_template('route_form.html', route=None, couriers=couriers)

@app.route('/admin/routes/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def route_edit(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    route = Route.query.get_or_404(id)
    couriers = Courier.query.all()
    
    if request.method == 'POST':
        try:
            route.courier_id = int(request.form.get('courier_id'))
            route.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            
            route.start_time = datetime.strptime(start_time, '%H:%M').time() if start_time else None
            route.end_time = datetime.strptime(end_time, '%H:%M').time() if end_time else None
            route.total_distance = float(request.form.get('total_distance')) if request.form.get('total_distance') else None
            route.notes = request.form.get('notes')
            
            db.session.commit()
            log_activity('update', 'route', route.id, f'Изменен маршрут #{route.id}')
            flash('Маршрут успешно обновлен', 'success')
            return redirect(url_for('routes_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении маршрута: {str(e)}', 'danger')
    
    return render_template('route_form.html', route=route, couriers=couriers)

@app.route('/admin/routes/delete/<int:id>', methods=['POST'])
@login_required
def route_delete(id):
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    route = Route.query.get_or_404(id)
    try:
        log_activity('delete', 'route', route.id, f'Удален маршрут #{route.id}')
        db.session.delete(route)
        db.session.commit()
        flash('Маршрут успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении маршрута: {str(e)}', 'danger')
    
    return redirect(url_for('routes_list'))

# ============ Журнал действий ============

@app.route('/admin/activity-log')
@login_required
def activity_log():
    if not has_role_in_current_user(['admin', 'manager']):
        abort(403)
    
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).all()
    return render_template('activity_log.html', logs=logs)

# ============ Обработка ошибок ============

@app.errorhandler(403)
def forbidden(error):
    return render_template('access_denied.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('access_denied.html', message='Страница не найдена'), 404

# ============ Запуск приложения ============

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)