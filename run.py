"""Точка входа: python run.py"""

from printer_cost_calculator.ui.app import create_app, app

if __name__ == "__main__":
    create_app()
    app.run(debug=True)
