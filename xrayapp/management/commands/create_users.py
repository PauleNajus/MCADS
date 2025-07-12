from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from xrayapp.models import UserProfile

class Command(BaseCommand):
    help = 'Creates default users for the system with roles'

    def handle(self, *args, **kwargs):
        users_data = [
            {
                'username': 'admin',
                'password': 'Qazwsxedc2025!',
                'email': 'admin@gmail.com',
                'first_name': 'Adminfirst',
                'last_name': 'Adminlast',
                'role': 'Administrator',
                'hospital': 'VULSK',
                'is_staff': True,
                'is_superuser': True
            },
            {
                'username': 'paubun',
                'password': 'PauBun2025!',
                'email': 'paubun@gmail.com',
                'first_name': 'Paulius',
                'last_name': 'Bundza',
                'role': 'Radiographer',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'username': 'justri',
                'password': 'JusTri2025!',
                'email': 'justri@gmail.com',
                'first_name': 'Justas',
                'last_name': 'Trinkūnas',
                'role': 'Radiographer',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'username': 'rolber',
                'password': 'RolBer2025!',
                'email': 'rolber@gmail.com',
                'first_name': 'Rolandas',
                'last_name': 'Bėrontas',
                'role': 'Radiographer',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'username': 'technologist',
                'password': 'TechNologist2025!',
                'email': 'technologist@gmail.com',
                'first_name': 'Tech',
                'last_name': 'Nologist',
                'role': 'Technologist',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'username': 'radiologist',
                'password': 'RadioLogist2025!',
                'email': 'radiologist@gmail.com',
                'first_name': 'Radio',
                'last_name': 'Logist',
                'role': 'Radiologist',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            },
            {
                'username': 'guest',
                'password': 'GuestUser2025!',
                'email': 'guestuser@gmail.com',
                'first_name': 'Guest',
                'last_name': 'User',
                'role': 'Radiographer',
                'hospital': 'VULSK',
                'is_staff': False,
                'is_superuser': False
            }
        ]

        with transaction.atomic():
            for user_data in users_data:
                username = user_data.pop('username')
                password = user_data.pop('password')
                role = user_data.pop('role')
                hospital = user_data.pop('hospital')
                
                # Check if user already exists
                if User.objects.filter(username=username).exists():
                    self.stdout.write(self.style.WARNING(f'User {username} already exists. Skipping.'))
                    continue
                
                # Create the user
                user = User.objects.create_user(username=username, **user_data)
                user.set_password(password)
                user.save()
                
                # Create user profile with role and hospital
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'role': role, 'hospital': hospital}
                )
                if not created:
                    profile.role = role
                    profile.hospital = hospital
                    profile.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'User {username} created successfully with role: {role}, hospital: {hospital}')
                )
        
        self.stdout.write(self.style.SUCCESS('All users created successfully.')) 