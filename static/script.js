// Variables globales
let currentForm = 'login';

document.addEventListener('DOMContentLoaded', function() {
    // checkAuthenticationStatus(); // Eliminado para que no redirija automáticamente
    initializeEventListeners();
    addFormValidation();
});

function initializeEventListeners() {
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('registerForm').addEventListener('submit', handleRegister);
    addRealTimeValidation();
    addVisualEffects();
    document.querySelectorAll('.form-footer a').forEach(link => {
        if (link.textContent.toLowerCase().includes('regístrate')) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                showRegister();
            });
        }
        if (link.textContent.toLowerCase().includes('inicia sesión')) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                showLogin();
            });
        }
    });
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const rememberMe = document.getElementById('rememberMe') ? document.getElementById('rememberMe').checked : false;
    if (!validateEmail(email)) {
        showNotification('Por favor, ingresa un correo electrónico válido', 'error');
        return;
    }
    // El backend valida la longitud de la contraseña, aquí solo validamos que no esté vacía
    if (!password) {
        showNotification('La contraseña es obligatoria', 'error');
        return;
    }
    const submitBtn = e.target.querySelector('.btn-primary');
    showLoading(submitBtn);
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
        });
        const data = await response.json();
        if (data.success) {
            if (rememberMe) {
                localStorage.setItem('rememberedEmail', email);
            }
            showNotification('¡Inicio de sesión exitoso! Redirigiendo al dashboard...', 'success');
            setTimeout(() => { window.location.href = data.redirect || '/dashboard'; }, 1200);
        } else {
            showNotification(data.message || 'Error al iniciar sesión. Verifica tus credenciales.', 'error');
            hideLoading(submitBtn);
        }
    } catch (error) {
        showNotification('Error de conexión. Intenta nuevamente.', 'error');
        hideLoading(submitBtn);
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const formData = {
        firstName: document.getElementById('firstName').value,
        lastName: document.getElementById('lastName').value,
        dni: document.getElementById('dni').value,
        email: document.getElementById('registerEmail').value,
        phone: document.getElementById('phone').value,
        password: document.getElementById('registerPassword').value,
        confirmPassword: document.getElementById('confirmPassword').value,
        acceptTerms: document.getElementById('acceptTerms').checked
    };
    const validation = validateRegistration(formData);
    if (!validation.isValid) {
        showNotification(validation.message, 'error');
        return;
    }
    const submitBtn = e.target.querySelector('.btn-primary');
    showLoading(submitBtn);
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        const data = await response.json();
        if (data.success) {
            showNotification(data.message || '¡Registro exitoso!', 'success');
            setTimeout(() => {
                window.location.href = data.redirect || '/menu';
            }, 1200);
        } else {
            showNotification(data.message || 'Error al registrarse', 'error');
            hideLoading(submitBtn);
        }
    } catch (error) {
        showNotification('Error de conexión. Intenta nuevamente.', 'error');
        hideLoading(submitBtn);
    }
}

function validateRegistration(data) {
    if (!data.firstName.trim()) return { isValid: false, message: 'El nombre es requerido' };
    if (!data.lastName.trim()) return { isValid: false, message: 'El apellido es requerido' };
    if (!data.dni.trim()) return { isValid: false, message: 'El DNI es requerido' };
    if (data.dni.length !== 8 || !/^[0-9]{8}$/.test(data.dni)) return { isValid: false, message: 'El DNI debe tener exactamente 8 dígitos' };
    if (!validateEmail(data.email)) return { isValid: false, message: 'Correo electrónico inválido' };
    if (data.password.length < 8) return { isValid: false, message: 'La contraseña debe tener al menos 8 caracteres' };
    if (data.password !== data.confirmPassword) return { isValid: false, message: 'Las contraseñas no coinciden' };
    if (!data.acceptTerms) return { isValid: false, message: 'Debes aceptar los términos y condiciones' };
    return { isValid: true };
}

function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function addRealTimeValidation() {
    const inputs = document.querySelectorAll('input[type="email"]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value && !validateEmail(this.value)) {
                this.style.borderColor = '#f44336';
                showFieldError(this, 'Correo electrónico inválido');
            } else {
                this.style.borderColor = '#e1e5e9';
                hideFieldError(this);
            }
        });
    });
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        if (input.id === 'confirmPassword') {
            input.addEventListener('input', function() {
                const password = document.getElementById('registerPassword').value;
                if (this.value && this.value !== password) {
                    this.style.borderColor = '#f44336';
                    showFieldError(this, 'Las contraseñas no coinciden');
                } else {
                    this.style.borderColor = '#e1e5e9';
                    hideFieldError(this);
                }
            });
        }
    });
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling;
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

function showLogin() {
    document.getElementById('registerContainer').style.display = 'none';
    document.getElementById('loginContainer').style.display = 'flex';
    currentForm = 'login';
    const rememberedEmail = localStorage.getItem('rememberedEmail');
    if (rememberedEmail) {
        document.getElementById('loginEmail').value = rememberedEmail;
        document.getElementById('rememberMe').checked = true;
    }
}

function showRegister() {
    document.getElementById('loginContainer').style.display = 'none';
    document.getElementById('registerContainer').style.display = 'flex';
    currentForm = 'register';
}

function clearRegisterForm() {
    const form = document.getElementById('registerForm');
    if (form) {
        form.reset();
        document.querySelectorAll('.field-error').forEach(error => error.remove());
        document.querySelectorAll('.form-group input, .form-group select').forEach(input => {
            input.style.borderColor = '#e1e5e9';
        });
    }
}

function showNotification(message, type = 'success') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');
    setTimeout(() => { notification.classList.remove('show'); }, 4000);
}

function showLoading(button) {
    if (button) {
        button.classList.add('loading');
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Procesando...';
    }
}

function hideLoading(button) {
    if (button) {
        button.classList.remove('loading');
        button.disabled = false;
        if (currentForm === 'login') {
            button.innerHTML = '<i class="fas fa-sign-in-alt"></i> Iniciar Sesión';
        } else {
            button.innerHTML = '<i class="fas fa-user-plus"></i> Registrarse';
        }
    }
}

function addVisualEffects() {}
function addFormValidation() {}
function showFieldError(input, message) {}
function hideFieldError(input) {}
