// DOM Elements
const employeeForm = document.getElementById('employeeForm');
const employeeList = document.getElementById('employeeList');

// Fetch all employees
async function fetchEmployees() {
    try {
        const response = await fetch('/api/employees');
        const employees = await response.json();
        displayEmployees(employees);
    } catch (error) {
        showAlert('Error fetching employees', 'error');
    }
}

// Display employees in the table
function displayEmployees(employees) {
    employeeList.innerHTML = '';
    employees.forEach(employee => {
        const row = document.createElement('tr');
        row.className = 'fade-in';
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${employee.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${employee.position}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${employee.department}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">$${employee.salary.toLocaleString()}</td>
        `;
        employeeList.appendChild(row);
    });
}

// Add new employee
async function addEmployee(employeeData) {
    try {
        const response = await fetch('/api/employees', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(employeeData)
        });

        if (!response.ok) {
            throw new Error('Failed to add employee');
        }

        showAlert('Employee added successfully', 'success');
        employeeForm.reset();
        fetchEmployees();
    } catch (error) {
        showAlert('Error adding employee', 'error');
    }
}

// Show alert message
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} fade-in`;
    alertDiv.textContent = message;

    const main = document.querySelector('main');
    main.insertBefore(alertDiv, main.firstChild);

    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

// Form submission handler
employeeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(employeeForm);
    const employeeData = {
        name: formData.get('name'),
        position: formData.get('position'),
        department: formData.get('department'),
        salary: parseFloat(formData.get('salary'))
    };

    await addEmployee(employeeData);
});

// Initialize the page
document.addEventListener('DOMContentLoaded', () => {
    fetchEmployees();
}); 