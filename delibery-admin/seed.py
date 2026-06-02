from app import app, db
from models import User, Role, OrderStatus, Client, Courier, Order, Route
from werkzeug.security import generate_password_hash
from datetime import datetime, date, time

def seed_database():
    with app.app_context():
        print("=" * 50)
        print("Заполнение базы данных...")
        print("=" * 50)
        
        # Очистка существующих данных
        db.drop_all()
        db.create_all()
        print("✓ Таблицы созданы")
        
        # 1. Создание ролей
        roles = [
            Role(name='admin', description='Полный доступ ко всем функциям'),
            Role(name='manager', description='Управление заказами, клиентами, курьерами'),
            Role(name='courier_viewer', description='Только просмотр своих маршрутов'),
            Role(name='user', description='Обычный пользователь с базовыми правами')
        ]
        for role in roles:
            db.session.add(role)
        db.session.commit()
        print("✓ Роли созданы (admin, manager, courier_viewer, user)")
        
        # 2. Создание пользователей
        users = [
            User(
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                full_name='Администратор Системы',
                phone='+7 (999) 111-22-33',
                is_active=True
            ),
            User(
                email='manager@example.com',
                password_hash=generate_password_hash('manager123'),
                full_name='Иван Петров',
                phone='+7 (999) 222-33-44',
                is_active=True
            ),
            User(
                email='courier@example.com',
                password_hash=generate_password_hash('courier123'),
                full_name='Алексей Смирнов',
                phone='+7 (999) 333-44-55',
                is_active=True
            ),
            User(
                email='user@example.com',
                password_hash=generate_password_hash('user123'),
                full_name='Обычный Пользователь',
                phone='+7 (999) 444-55-66',
                is_active=True
            )
        ]
        for user in users:
            db.session.add(user)
        db.session.commit()
        print("✓ Пользователи созданы")
        
        # Назначение ролей
        users[0].roles.append(roles[0])  # admin
        users[1].roles.append(roles[1])  # manager
        users[2].roles.append(roles[2])  # courier_viewer
        users[3].roles.append(roles[3])  # user
        db.session.commit()
        print("✓ Роли назначены")
        
        # 3. Создание статусов заказов
        statuses = [
            OrderStatus(name='Новый', color='primary', sort_order=1),
            OrderStatus(name='Подтвержден', color='info', sort_order=2),
            OrderStatus(name='В пути', color='warning', sort_order=3),
            OrderStatus(name='Доставлен', color='success', sort_order=4),
            OrderStatus(name='Отменен', color='danger', sort_order=5)
        ]
        for status in statuses:
            db.session.add(status)
        db.session.commit()
        print("✓ Статусы заказов созданы")
        
        # 4. Создание клиентов
        clients = [
            Client(name='ООО "Ромашка"', phone='+7 (495) 111-11-11', email='info@romashka.ru', address='г. Москва, ул. Ленина, 10'),
            Client(name='ИП Иванов', phone='+7 (495) 222-22-22', email='ivanov@mail.ru', address='г. Москва, ул. Пушкина, 5'),
            Client(name='ЗАО "ТехноСервис"', phone='+7 (495) 333-33-33', email='info@tehno.ru', address='г. Москва, пр. Мира, 15'),
            Client(name='ООО "Продукты-24"', phone='+7 (495) 444-44-44', email='zakaz@product24.ru', address='г. Москва, ул. Тверская, 20'),
            Client(name='ИП Сидорова', phone='+7 (495) 555-55-55', email='sidorova@mail.ru', address='г. Москва, ул. Арбат, 7')
        ]
        for client in clients:
            db.session.add(client)
        db.session.commit()
        print(f"✓ Создано {len(clients)} клиентов")
        
        # 5. Создание курьеров
        couriers = [
            Courier(user_id=users[2].id, phone='+7 (999) 333-44-55', vehicle_type='Автомобиль', license_plate='А123ВС77', is_available=True),
            Courier(user_id=None, phone='+7 (999) 444-55-66', vehicle_type='Велосипед', license_plate='', is_available=True),
            Courier(user_id=None, phone='+7 (999) 555-66-77', vehicle_type='Мотоцикл', license_plate='М456НЕ77', is_available=False)
        ]
        for courier in couriers:
            db.session.add(courier)
        db.session.commit()
        print(f"✓ Создано {len(couriers)} курьеров")
        
        # 6. Создание заказов
        orders_data = [
            (clients[0], couriers[0], statuses[0], 12500.00, 'г. Москва, ул. Ленина, 10', 'Срочная доставка'),
            (clients[1], couriers[0], statuses[2], 3400.00, 'г. Москва, ул. Пушкина, 5', ''),
            (clients[2], couriers[1], statuses[3], 8900.00, 'г. Москва, пр. Мира, 15', 'Осторожно, хрупкое'),
            (clients[3], couriers[1], statuses[1], 2300.00, 'г. Москва, ул. Тверская, 20', ''),
            (clients[4], couriers[2], statuses[4], 6700.00, 'г. Москва, ул. Арбат, 7', 'Отменен'),
            (clients[0], couriers[0], statuses[0], 15400.00, 'г. Москва, ш. Энтузиастов, 25', ''),
            (clients[2], couriers[1], statuses[2], 11200.00, 'г. Москва, пр. Мира, 15', '')
        ]
        
        for client, courier, status, total, address, notes in orders_data:
            order = Order(
                client_id=client.id,
                courier_id=courier.id if courier else None,
                status_id=status.id,
                total=total,
                address=address,
                notes=notes
            )
            db.session.add(order)
        db.session.commit()
        print(f"✓ Создано {len(orders_data)} заказов")
        
        # 7. Создание маршрутов
        routes_data = [
            (couriers[0], date.today(), time(9, 0), time(13, 0), 45.5, 'Утренний маршрут'),
            (couriers[0], date.today(), time(14, 0), time(18, 0), 38.2, 'Вечерний маршрут'),
            (couriers[1], date.today(), time(10, 0), time(15, 0), 25.0, 'Маршрут по центру')
        ]
        
        for courier, route_date, start_time, end_time, distance, notes in routes_data:
            route = Route(
                courier_id=courier.id,
                date=route_date,
                start_time=start_time,
                end_time=end_time,
                total_distance=distance,
                notes=notes
            )
            db.session.add(route)
        db.session.commit()
        print(f"✓ Создано {len(routes_data)} маршрутов")
        
        print("\n" + "=" * 50)
        print("✅ БАЗА ДАННЫХ УСПЕШНО ЗАПОЛНЕНА!")
        print("=" * 50)
        print("\n📋 ТЕСТОВЫЕ ПОЛЬЗОВАТЕЛИ:")
        print("  🔑 admin@example.com / admin123 (Администратор)")
        print("  🔑 manager@example.com / manager123 (Менеджер)")
        print("  🔑 courier@example.com / courier123 (Курьер)")
        print("  🔑 user@example.com / user123 (Обычный пользователь)")
        print("\n🚀 Запустите приложение: python app.py")
        print("🌐 Откройте в браузере: http://localhost:5000")

if __name__ == '__main__':
    seed_database()