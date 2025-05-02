from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Public paths that don't require authentication
        public_paths = [
            '/accounts/login/',
            '/accounts/logout/',
            '/admin/login/',
            '/favicon.ico',
            '/static/',
            '/media/',
        ]
        
        # Check if the path is public or if user is already authenticated
        is_public = any(request.path.startswith(path) for path in public_paths)
        
        # If the path is not public and the user is not authenticated, redirect to login
        if not is_public and not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
            
        response = self.get_response(request)
        return response 