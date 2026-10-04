// ================= DOM ELEMENTS =================
const burgerBtn = document.getElementById('burger-btn');
const nav = document.getElementById('nav');
const navLinks = document.querySelectorAll('.nav-link');

// Form elements
const leadForm = document.getElementById('lead-form');
const nameInput = document.getElementById('name');
const phoneInput = document.getElementById('phone');
const nameError = document.getElementById('name-error');
const phoneError = document.getElementById('phone-error');
const formSuccess = document.getElementById('form-success');

// ================= MOBILE MENU =================
// Toggle mobile menu visibility
burgerBtn.addEventListener('click', () => {
    nav.classList.toggle('active');
});

// Close mobile menu when a navigation link is clicked
navLinks.forEach(link => {
    link.addEventListener('click', () => {
        nav.classList.remove('active');
    });
});

// ================= FORM VALIDATION =================
// Regex for basic phone validation (allows +, spaces, dashes, parentheses)
const phoneRegex = /^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$/im;

leadForm.addEventListener('submit', (e) => {
    e.preventDefault(); // Prevent page reload
    let isValid = true;

    // Reset previous errors
    nameError.textContent = '';
    phoneError.textContent = '';
    nameInput.style.borderColor = 'var(--border-color)';
    phoneInput.style.borderColor = 'var(--border-color)';
    formSuccess.style.display = 'none';

    // Validate Name (minimum 2 characters)
    if (nameInput.value.trim().length < 2) {
        nameError.textContent = 'Name must be at least 2 characters long.';
        nameInput.style.borderColor = '#ef4444';
        isValid = false;
    }

    // Validate Phone Number
    if (!phoneRegex.test(phoneInput.value.trim())) {
        phoneError.textContent = 'Please enter a valid phone number.';
        phoneInput.style.borderColor = '#ef4444';
        isValid = false;
    }

    // If all fields are valid
    if (isValid) {
        // Show success message
        formSuccess.style.display = 'block';
        
        // Clear input fields
        leadForm.reset();
        
        // Hide success message after 5 seconds
        setTimeout(() => {
            formSuccess.style.display = 'none';
        }, 5000);
    }
});