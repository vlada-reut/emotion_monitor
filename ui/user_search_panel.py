from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analytics.stats import age_group_to_russian, emotion_to_russian, gender_to_russian
from services.database_service import StoredUser, StoredUserSession, UserDatabaseService


def _build_card(name: str) -> QFrame:
    card = QFrame()
    card.setObjectName(name)
    card.setFrameShape(QFrame.Shape.NoFrame)
    return card


class UserSearchPanel(QWidget):
    def __init__(self, database: UserDatabaseService) -> None:
        super().__init__()
        self.database = database
        self._build_layout()
        self.refresh_results()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = _build_card("userDatabaseCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        title = QLabel("База пользователей")
        title.setObjectName("sectionTitle")

        subtitle = QLabel("Поиск людей, которые уже появлялись в предыдущих сессиях.")
        subtitle.setObjectName("cardMeta")
        subtitle.setWordWrap(True)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Поиск по ID или имени")
        self.search_input.textChanged.connect(self.refresh_results)

        self.gender_filter = QComboBox()
        self.gender_filter.setObjectName("filterCombo")
        self.gender_filter.addItem("Все", "")
        self.gender_filter.addItem("Мужской", "male")
        self.gender_filter.addItem("Женский", "female")
        self.gender_filter.addItem("Неизвестно", "unknown")
        self.gender_filter.currentIndexChanged.connect(self.refresh_results)

        self.age_filter = QComboBox()
        self.age_filter.setObjectName("filterCombo")
        self.age_filter.addItem("Все возрасты", "")
        self.age_filter.addItem("Ребенок", "child")
        self.age_filter.addItem("Подросток", "teen")
        self.age_filter.addItem("Молодой взрослый", "young_adult")
        self.age_filter.addItem("Взрослый", "adult")
        self.age_filter.addItem("Пожилой", "senior")
        self.age_filter.addItem("Неизвестно", "unknown")
        self.age_filter.currentIndexChanged.connect(self.refresh_results)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self.refresh_results)

        search_row.addWidget(self.search_input, stretch=3)
        search_row.addWidget(self.gender_filter, stretch=1)
        search_row.addWidget(self.age_filter, stretch=1)
        search_row.addWidget(self.refresh_button)

        self.results_list = QListWidget()
        self.results_list.setObjectName("usersList")
        self.results_list.setMinimumHeight(170)
        self.results_list.currentItemChanged.connect(self._on_selection_changed)

        rename_row = QHBoxLayout()
        rename_row.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("searchInput")
        self.name_input.setPlaceholderText("Переименовать выбранного пользователя")

        self.save_name_button = QPushButton("Сохранить имя")
        self.save_name_button.setObjectName("primaryButton")
        self.save_name_button.clicked.connect(self.save_display_name)

        self.delete_user_button = QPushButton("Удалить пользователя")
        self.delete_user_button.setObjectName("secondaryButton")
        self.delete_user_button.clicked.connect(self.delete_selected_user)

        rename_row.addWidget(self.name_input, stretch=1)
        rename_row.addWidget(self.save_name_button)
        rename_row.addWidget(self.delete_user_button)

        self.details_text = QTextEdit()
        self.details_text.setObjectName("detailsText")
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(150)
        self.details_text.setPlainText("Выберите пользователя, чтобы посмотреть его историю.")

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(search_row)
        card_layout.addWidget(self.results_list)
        card_layout.addLayout(rename_row)
        card_layout.addWidget(self.details_text)
        layout.addWidget(card)

    def refresh_results(self) -> None:
        selected_user_id = self.selected_user_id
        users = self.database.search_users(
            query=self.search_input.text(),
            gender=str(self.gender_filter.currentData()),
            age_group=str(self.age_filter.currentData()),
        )

        self.results_list.blockSignals(True)
        self.results_list.clear()

        if not users:
            placeholder = QListWidgetItem("Ничего не найдено")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results_list.addItem(placeholder)
            self.results_list.blockSignals(False)
            self.name_input.clear()
            self.details_text.setPlainText("Совпадений пока нет. Попробуйте другой запрос или завершите новую сессию.")
            return

        row_to_select = 0
        for index, user in enumerate(users):
            item = QListWidgetItem(self._build_item_text(user))
            item.setData(Qt.ItemDataRole.UserRole, user.user_id)
            self.results_list.addItem(item)
            if user.user_id == selected_user_id:
                row_to_select = index

        self.results_list.setCurrentRow(row_to_select)
        self.results_list.blockSignals(False)
        self._show_user_details_by_row(row_to_select)

    def save_display_name(self) -> None:
        user_id = self.selected_user_id
        if user_id is None:
            return

        name = self.name_input.text().strip()
        if not name:
            return

        self.database.update_display_name(user_id, name)
        self.refresh_results()

    def delete_selected_user(self) -> None:
        user_id = self.selected_user_id
        if user_id is None:
            return

        user = self.database.get_user(user_id)
        if user is None:
            return

        answer = QMessageBox.question(
            self,
            "Удаление пользователя",
            (
                f"Удалить пользователя \"{user.display_name}\"?\n\n"
                "Запись исчезнет из локальной базы. Связи с сессиями будут удалены, "
                "но файлы в папке logs останутся."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.database.delete_user(user_id)
        self.name_input.clear()
        self.refresh_results()

    @property
    def selected_user_id(self) -> int | None:
        item = self.results_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _on_selection_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        value = current.data(Qt.ItemDataRole.UserRole)
        if value is None:
            return
        self._show_user_details(int(value))

    def _show_user_details_by_row(self, row: int) -> None:
        item = self.results_list.item(row)
        if item is None:
            return
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is None:
            return
        self._show_user_details(int(value))

    def _show_user_details(self, user_id: int) -> None:
        user = self.database.get_user(user_id)
        if user is None:
            self.name_input.clear()
            self.details_text.setPlainText("Пользователь не найден в базе.")
            return

        self.name_input.setText(user.display_name)
        sessions = self.database.get_user_sessions(user_id)
        self.details_text.setPlainText(self._build_details_text(user, sessions))

    def _build_item_text(self, user: StoredUser) -> str:
        return (
            f"{user.display_name}\n"
            f"ID: {user.user_id} · {gender_to_russian(user.dominant_gender)} · "
            f"{age_group_to_russian(user.dominant_age_group)} · "
            f"последний визит: {self._format_timestamp(user.last_seen_at)}"
        )

    def _build_details_text(self, user: StoredUser, sessions: list[StoredUserSession]) -> str:
        lines = [
            f"ID: {user.user_id}",
            f"Имя: {user.display_name}",
            f"Пол: {gender_to_russian(user.dominant_gender)}",
            f"Возрастная группа: {age_group_to_russian(user.dominant_age_group)}",
            f"Первое появление: {self._format_timestamp(user.first_seen_at)}",
            f"Последнее появление: {self._format_timestamp(user.last_seen_at)}",
            f"Сессий в базе: {user.total_sessions}",
            f"Наблюдений: {user.total_observations}",
            f"Последняя доминирующая эмоция: {emotion_to_russian(user.last_emotion)}",
        ]

        if sessions:
            lines.append("")
            lines.append("Последние сессии:")
            for session in sessions:
                lines.append(
                    f"{self._format_timestamp(session.finished_at)} · "
                    f"{emotion_to_russian(session.dominant_emotion)} · "
                    f"наблюдений: {session.observations_count}"
                )

        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(value: str) -> str:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return value
        return dt.strftime("%d.%m.%Y %H:%M")
