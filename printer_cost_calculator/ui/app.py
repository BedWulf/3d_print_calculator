"""Каркас веб-интерфейса (Flask). Вкладки реализуются на следующем этапе.

Запуск:  python run.py  ->  http://127.0.0.1:5000
"""

from flask import Flask, render_template

from ..db.repository import Repository

app = Flask(__name__)


def create_app(db_path=None) -> Flask:
    if db_path:
        app.config["DB_PATH"] = db_path
    return app


@app.route("/")
def index():
    """Главная страница-заглушка со списком будущих вкладок."""
    tabs = [
        ("calc", "Калькулятор — расчёт цены печати"),
        ("printers", "БД принтеров — ЭЛ, амортизация"),
        ("materials", "БД материалов — плотность, катушки, цены"),
        ("consumables", "БД расходников — салфетки, смазка, сопло, клей"),
        ("settings", "Настройки — тариф за кВт·ч"),
    ]
    return render_template("index.html", tabs=tabs)


# ---------------------------------------------------------------------------
# Заготовки маршрутов API (реализация -- следующий этап)
# ---------------------------------------------------------------------------
# Принтеры:
#   GET/POST   /api/printers          список / добавление
#   PUT/DELETE /api/printers/<id>     изменение / удаление
# Материалы:
#   GET/POST   /api/materials
#   PUT/DELETE /api/materials/<id>
# Расходники:
#   GET/POST   /api/consumables
#   PUT/DELETE /api/consumables/<id>
# Настройки:
#   GET/PUT    /api/settings
# Расчёт:
#   POST       /api/calculate         вход: CalcInput (JSON), выход: CalcResult (JSON)


if __name__ == "__main__":
    app.run(debug=True)
