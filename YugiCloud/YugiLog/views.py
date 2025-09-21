from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User

def login_user(request):
	if request.method == 'POST':
		username = request.method.POST.get('username')
		password = request.method.POST.get('password')
		user = authenticate(request, username=username, password=password)

		if user is not None:
			login(request, user)
			return redirect("YugiWeb:index")
		else:
			return render(request, 'YugiLog:login', {'error_message': 'Nom d\'utilisateur incorrect ou mot de passe !!'})
		
	else:
		return render(request, 'YugiLog:login', {'error_message': 'Method Error'})

def logout_user(request):
	logout(request)
	return redirect('YugiWeb:accueil')

def register_user(request):
	if request.method == 'POST':
		username = request.method.POST.get('username')
		password = request.method.POST.get('password')
		rep_password = request.method.POST.get('rep_password')
		if rep_password == password:
			User.objects.create_user(username, password=password)
			return redirect('YugiLog:login')
		else:
			return render(request, 'YugiLog:register', {'error_message': 'Les mots de passes ne sont pas identiques !'})
	else:
		return render(request, 'YugiLog:login', {'error_message': 'Method Error'})

