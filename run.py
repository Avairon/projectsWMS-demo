from app import create_app
from app.utils import init_database

app = create_app()

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)