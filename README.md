# Phantom Pay

A secure and efficient payroll management system built with Flask and Google's Generative AI.

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- pip (Python package installer)
- Git

## Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/Dakshmulundkar/Phantom-pay.git
cd Phantom-pay
```

2. Create a virtual environment (recommended):
```bash
# For Windows
python -m venv venv
venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory and add your configuration:
```
FLASK_APP=app.py
FLASK_ENV=development
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

## Running the Application

1. Start the Flask development server:
```bash
flask run
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

## Features

- Secure payroll management
- Employee data management
- Automated calculations
- AI-powered insights
- User authentication and authorization

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

Daksh Mulundkar - [GitHub Profile](https://github.com/Dakshmulundkar)

Project Link: [https://github.com/Dakshmulundkar/Phantom-pay.git](https://github.com/Dakshmulundkar/Phantom-pay.git) 