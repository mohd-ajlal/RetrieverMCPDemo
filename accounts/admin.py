from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Use default User admin; profile is registered in organizations.
admin.site.unregister(User)
admin.site.register(User, BaseUserAdmin)
